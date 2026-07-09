"""Opencode HTTP client -- proxy-pool based, no API keys."""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.candidate import Candidate, make_id
from src.core.errors import PlatformError
from src.logger import get_logger
from .constants import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    FILTER_PAID_MODELS,
    MAX_RETRIES,
    MODELS,
    MODELS_PATH,
    PROXY_FETCH_ENABLED,
    PROXY_POOL_PERSIST_PATH,
    PROXY_REFRESH_INTERVAL,
    PROXY_SCORE_PERSIST_PATH,
)
from .headers import build_headers
from .payloads import build_payload
from .proxypool import ProxyInfo, ProxyPool, fetch_all_proxies
from .proxyscore import DIRECT, ProxyPoolSelector
from .sse import parse_sse_line

# accounts.py is gitignored; import at runtime with fallback
try:
    from src.platforms.opencode.accounts import LOCAL_PROXIES
except ImportError:
    LOCAL_PROXIES: list = []

logger = get_logger(__name__)


class OpencodeClient:
    """Opencode HTTP client.

    Instead of API keys, each proxy in the pool becomes a Candidate.
    A ProxyPoolSelector (TAS-like) picks the best proxy per request, and
    the pool is refreshed every 24 hours from proxy.scdn.io.
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._pool: ProxyPool = ProxyPool()
        self._selector: ProxyPoolSelector = ProxyPoolSelector(PROXY_SCORE_PERSIST_PATH)
        self._models: List[str] = list(MODELS)
        self._refresh_task: Optional[asyncio.Task] = None
        self._proxy_lock: asyncio.Lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """Store session and load cached proxy pool -- non-blocking."""
        self._session = session

        # Only load from persistent file when PROXY_FETCH_ENABLED is True
        if PROXY_FETCH_ENABLED:
            pool = await self._load_pool_from_disk()
            if pool is None:
                pool = ProxyPool()
        else:
            pool = ProxyPool()

        # Always inject LOCAL_PROXIES
        self._inject_local_proxies(pool)
        if pool.count > 0:
            self._pool = pool
            self._selector.update_pool(pool.to_address_list())
        logger.debug(
            "opencode client init_immediate done, %d cached proxies",
            self._pool.count,
        )

    async def background_setup(self) -> None:
        """Fetch fresh proxy pool (in executor) and start background refresh."""
        if not PROXY_FETCH_ENABLED:
            logger.debug("opencode proxy fetch disabled, using local proxies only")
            return

        try:
            loop = asyncio.get_running_loop()
            pool = await loop.run_in_executor(None, self._do_proxy_fetch)
            await self._apply_pool(pool)
        except Exception as e:
            logger.warning("opencode background proxy fetch failed: %s", e)

        self._refresh_task = asyncio.ensure_future(self._bg_refresh_proxy())

    # ------------------------------------------------------------------
    # Proxy pool management
    # ------------------------------------------------------------------

    @staticmethod
    def _do_proxy_fetch() -> ProxyPool:
        """Synchronous proxy fetch (called from executor)."""
        return fetch_all_proxies()

    async def _apply_pool(self, pool: ProxyPool) -> None:
        """Apply a freshly fetched pool under lock, merging local proxies."""
        self._inject_local_proxies(pool)
        async with self._proxy_lock:
            self._pool = pool
            self._selector.update_pool(pool.to_address_list())
            await self._save_pool_to_disk(pool)
            logger.debug(
                "Proxy pool refreshed: %d proxies, fetch_time=%s",
                pool.count,
                pool.fetch_time,
            )

    @staticmethod
    def _inject_local_proxies(pool: ProxyPool) -> None:
        """Merge LOCAL_PROXIES from accounts.py into the pool."""
        for addr in LOCAL_PROXIES:
            addr = addr.strip()
            if not addr or ":" not in addr:
                continue
            parts = addr.rsplit(":", 1)
            try:
                ip, port = parts[0], int(parts[1])
            except (ValueError, IndexError):
                continue
            pool.add(ProxyInfo(
                ip=ip, port=port, protocol="http",
                country="local",
            ))

    async def _bg_refresh_proxy(self) -> None:
        """Periodically refresh the proxy pool."""
        if not PROXY_FETCH_ENABLED:
            return

        try:
            while True:
                await asyncio.sleep(PROXY_REFRESH_INTERVAL)
                try:
                    loop = asyncio.get_running_loop()
                    pool = await loop.run_in_executor(None, self._do_proxy_fetch)
                    await self._apply_pool(pool)
                except Exception as e:
                    logger.warning("opencode periodic proxy refresh failed: %s", e)
        except asyncio.CancelledError:
            raise

    async def _load_pool_from_disk(self) -> Optional[ProxyPool]:
        """Deserialize cached ProxyPool from JSON."""
        path = Path(PROXY_POOL_PERSIST_PATH)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            return ProxyPool.from_dict(data)
        except Exception as e:
            logger.warning("Failed to load proxy pool from %s: %s", path, e)
            return None

    async def _save_pool_to_disk(self, pool: ProxyPool) -> None:
        """Atomically persist ProxyPool to JSON."""
        path = Path(PROXY_POOL_PERSIST_PATH)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(pool.to_dict(), indent=2), encoding="utf-8"
            )
            os.replace(str(tmp), str(path))
        except Exception as e:
            logger.warning("Failed to save proxy pool to %s: %s", path, e)

    # ------------------------------------------------------------------
    # Candidate management
    # ------------------------------------------------------------------

    async def candidates(self) -> List[Candidate]:
        """Return a single candidate -- proxy selection is handled internally."""
        if self._pool.count == 0:
            return []
        return [
            Candidate(
                id=make_id("opencode"),
                platform="opencode",
                resource_id="proxy-pool",
                models=list(self._models),
                context_length=None,
                meta={"proxy_addr": "", "proxy_protocol": ""},
                **CAPS,
            )
        ]

    async def ensure_candidates(self, count: int) -> int:
        """Ensure the single candidate is available (proxy pool non-empty)."""
        if self._pool.count == 0 and PROXY_FETCH_ENABLED:
            try:
                loop = asyncio.get_running_loop()
                pool = await loop.run_in_executor(None, self._do_proxy_fetch)
                await self._apply_pool(pool)
            except Exception as e:
                logger.warning("opencode ensure_candidates fetch failed: %s", e)
        return 1 if self._pool.count > 0 else 0

    # ------------------------------------------------------------------
    # Chat completion
    # ------------------------------------------------------------------

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Execute chat completion with retry (up to MAX_RETRIES attempts).

        Each retry selects a different proxy via TAS scoring.  The first
        attempt uses the gateway-provided candidate.  On failure the proxy
        is recorded, a new proxy (or direct) is chosen, and the candidate
        meta is updated before the next attempt.

        Stops immediately when the remote side actively disconnects or
        truncates the response.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            if PROXY_FETCH_ENABLED:
                # TAS-select a proxy for every attempt (first included)
                pool_addrs = self._pool.to_address_list()
                # Exclude the last failed proxy on retries
                if attempt > 0:
                    pool_addrs = [
                        a for a in pool_addrs
                        if a != candidate.meta.get("proxy_addr", "")
                    ]
                chosen = self._selector.select(pool_addrs)
                if chosen == DIRECT or chosen is None:
                    new_addr = ""
                else:
                    new_addr = chosen
            else:
                new_addr = ""
            candidate.meta["proxy_addr"] = new_addr
            candidate.meta["proxy_protocol"] = "proxy" if new_addr else "direct"

            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream, **kw
                ):
                    yield chunk
                return  # success
            except PlatformError:
                raise
            except Exception as e:
                last_exc = e
                proxy_addr = candidate.meta.get("proxy_addr", "")
                selector_key = proxy_addr if proxy_addr else DIRECT
                self._selector.record_failure(selector_key)
                logger.warning(
                    "opencode retry %d/%d (proxy=%s failed): %s",
                    attempt + 1, MAX_RETRIES, selector_key, e,
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(1.0)
        if last_exc:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """Execute a single HTTP request through the candidate's proxy or direct."""
        proxy_addr = candidate.meta.get("proxy_addr", "")
        # Selector key: DIRECT sentinel for direct connection, proxy_addr otherwise
        selector_key = proxy_addr if proxy_addr else DIRECT

        headers = build_headers(proxy_addr)
        payload = build_payload(messages, model, stream=stream, **kw)
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        # Build request kwargs -- only difference is the proxy= kwarg
        request_kwargs: Dict[str, Any] = dict(
            headers=headers,
            json=payload,
            ssl=False,
            timeout=aiohttp.ClientTimeout(
                connect=10,
                total=600 if stream else 120,
            ),
        )
        if proxy_addr:
            request_kwargs["proxy"] = "http://{}".format(proxy_addr)

        t0 = time.time()
        _request_ok = False
        try:
            async with self._session.post(
                url,
                **request_kwargs,
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    self._selector.record_failure(selector_key)
                    if resp.status == 429:
                        raise RuntimeError(
                            "opencode rate limited (429): {}".format(body[:200])
                        )
                    raise PlatformError(
                        "opencode HTTP{}: {}".format(resp.status, body[:200])
                    )

                if not stream:
                    data = await resp.json()
                    _request_ok = True
                    choice = (data.get("choices") or [{}])[0]
                    msg = choice.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        yield content
                    tc = msg.get("tool_calls")
                    if tc:
                        yield {"tool_calls": tc}
                    usage = data.get("usage")
                    if usage:
                        yield {"usage": {
                            "prompt_tokens": usage.get("prompt_tokens", 0),
                            "completion_tokens": usage.get("completion_tokens", 0),
                        }}
                else:
                    _tc_accumulator: Dict[int, Dict[str, Any]] = {}
                    async for line in resp.content:
                        text = line.decode("utf-8", errors="replace").strip()
                        if not text or not text.startswith("data:"):
                            continue
                        data_str = text[5:].strip()
                        if data_str == "[DONE]":
                            break
                        parsed = parse_sse_line(data_str)
                        if parsed is None:
                            continue
                        if isinstance(parsed, dict) and "tool_calls" in parsed:
                            for tc_delta in parsed["tool_calls"]:
                                idx = tc_delta.get("index", 0)
                                if idx not in _tc_accumulator:
                                    _tc_accumulator[idx] = {
                                        "id": "",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""},
                                    }
                                acc = _tc_accumulator[idx]
                                if tc_delta.get("id"):
                                    acc["id"] = tc_delta["id"]
                                if tc_delta.get("type"):
                                    acc["type"] = tc_delta["type"]
                                fn = tc_delta.get("function") or {}
                                if fn.get("name"):
                                    acc["function"]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    acc["function"]["arguments"] += fn["arguments"]
                        else:
                            yield parsed
                    if _tc_accumulator:
                        tool_calls = [
                            v for _, v in sorted(_tc_accumulator.items())
                        ]
                        yield {"tool_calls": tool_calls}
                    _request_ok = True

        except PlatformError:
            raise
        except Exception as e:
            self._selector.record_failure(selector_key)
            raise
        finally:
            if _request_ok:
                latency_ms = (time.time() - t0) * 1000.0
                self._selector.record_success(selector_key, latency_ms)

    # ------------------------------------------------------------------
    # Remote models
    # ------------------------------------------------------------------

    async def fetch_remote_models(self) -> List[str]:
        """Fetch available models from the remote API (direct connection).

        Returns:
            Model ID list, empty on failure.
        """
        if not self._session:
            return []

        url = "{}{}".format(BASE_URL, MODELS_PATH)

        try:
            async with self._session.get(
                url,
                ssl=False,
                timeout=aiohttp.ClientTimeout(connect=10, total=30),
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "opencode fetch models failed, HTTP%s", resp.status
                    )
                    return []
                data = await resp.json()
                model_data = data.get("data", [])
                if isinstance(model_data, list):
                    all_models = [
                        m.get("id", "")
                        for m in model_data
                        if isinstance(m, dict) and m.get("id")
                    ]
                    if FILTER_PAID_MODELS:
                        return [m for m in all_models if m.endswith("-free")]
                    return all_models
                return []
        except Exception as e:
            logger.warning("opencode fetch models exception: %s", e)
            return []

    # ------------------------------------------------------------------
    # Model list management
    # ------------------------------------------------------------------

    def get_available_models(self) -> List[str]:
        """Return current model list."""
        return list(self._models)

    def update_models(self, models: List[str]) -> None:
        """Replace the model list."""
        self._models = list(models)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Cancel background tasks."""
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                logger.debug("opencode proxy refresh task cancelled")
