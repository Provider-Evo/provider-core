"""Zen HTTP客户端（代理池模式）-- 基于代理池，无需API密钥。"""
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
from src.foundation.logger import get_logger
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

try:
    from src.platforms.zen.accounts import LOCAL_PROXIES
except ImportError:
    LOCAL_PROXIES: list = []

logger = get_logger(__name__)


class ProxyClient:
    """Zen HTTP客户端（代理池模式）。

    不使用API密钥，而是将代理池中的每个代理视为候选节点。
    通过ProxyPoolSelector（基于汤普森采样算法）为每个请求选择最优代理。
    """

    _POOL_CACHE_MAX_AGE: float = PROXY_REFRESH_INTERVAL * 0.8

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._pool: ProxyPool = ProxyPool()
        self._selector: ProxyPoolSelector = ProxyPoolSelector(PROXY_SCORE_PERSIST_PATH)
        self._models: List[str] = list(MODELS)
        self._refresh_task: Optional[asyncio.Task] = None
        self._proxy_lock: asyncio.Lock = asyncio.Lock()
        self._active_requests: int = 0
        self._pool_refresh_pending: bool = False
        self._last_fetch_time: float = 0.0

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        pool = await self._load_pool_from_disk()
        if pool is not None and pool.count > 0:
            self._inject_local_proxies(pool)
            self._pool = pool
            self._selector.update_pool(pool.to_address_list())
            self._last_fetch_time = pool.fetch_time_epoch
        else:
            local_pool = ProxyPool()
            self._inject_local_proxies(local_pool)
            if local_pool.count > 0:
                self._pool = local_pool
                self._selector.update_pool(local_pool.to_address_list())

    async def background_setup(self) -> None:
        if not PROXY_FETCH_ENABLED:
            return
        cache_age = time.time() - self._last_fetch_time if self._last_fetch_time else float("inf")
        cache_valid = (
            self._pool.count > 0
            and self._last_fetch_time > 0
            and cache_age < self._POOL_CACHE_MAX_AGE
        )
        if not cache_valid:
            try:
                loop = asyncio.get_running_loop()
                pool = await loop.run_in_executor(None, self._do_proxy_fetch)
                await self._apply_pool(pool)
            except Exception as e:
                logger.warning("zen proxy fetch failed: %s", e)
        self._refresh_task = asyncio.ensure_future(self._bg_refresh_proxy())

    @staticmethod
    def _do_proxy_fetch() -> ProxyPool:
        return fetch_all_proxies()

    async def _apply_pool(self, pool: ProxyPool) -> None:
        self._inject_local_proxies(pool)
        async with self._proxy_lock:
            if self._active_requests > 0:
                self._pool_refresh_pending = True
                return
            self._pool = pool
            self._selector.update_pool(pool.to_address_list())
            self._last_fetch_time = pool.fetch_time_epoch
            self._pool_refresh_pending = False
            await self._save_pool_to_disk(pool)

    async def _check_deferred_refresh(self) -> None:
        if not PROXY_FETCH_ENABLED:
            return
        if self._pool_refresh_pending and self._active_requests == 0:
            try:
                loop = asyncio.get_running_loop()
                pool = await loop.run_in_executor(None, self._do_proxy_fetch)
                self._inject_local_proxies(pool)
                async with self._proxy_lock:
                    self._pool = pool
                    self._selector.update_pool(pool.to_address_list())
                    self._last_fetch_time = pool.fetch_time_epoch
                    self._pool_refresh_pending = False
                    await self._save_pool_to_disk(pool)
            except Exception as e:
                logger.warning("zen deferred proxy refresh failed: %s", e)

    @staticmethod
    def _inject_local_proxies(pool: ProxyPool) -> None:
        for addr in LOCAL_PROXIES:
            addr = addr.strip()
            if not addr or ":" not in addr:
                continue
            parts = addr.rsplit(":", 1)
            try:
                ip, port = parts[0], int(parts[1])
            except (ValueError, IndexError):
                continue
            pool.add(ProxyInfo(ip=ip, port=port, protocol="http", country="local"))

    async def _bg_refresh_proxy(self) -> None:
        if not PROXY_FETCH_ENABLED:
            return
        try:
            while True:
                await asyncio.sleep(PROXY_REFRESH_INTERVAL)
                try:
                    loop = asyncio.get_running_loop()
                    pool = await loop.run_in_executor(None, self._do_proxy_fetch)
                    await self._apply_pool(pool)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning("zen periodic proxy refresh failed: %s", e)
        except asyncio.CancelledError:
            raise

    async def _load_pool_from_disk(self) -> Optional[ProxyPool]:
        path = Path(PROXY_POOL_PERSIST_PATH)
        if not path.exists():
            return None
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw)
            pool = ProxyPool.from_dict(data)
            return pool if pool.count > 0 else None
        except Exception:
            return None

    async def _save_pool_to_disk(self, pool: ProxyPool) -> None:
        path = Path(PROXY_POOL_PERSIST_PATH)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(pool.to_dict(), indent=2), encoding="utf-8")
            os.replace(str(tmp), str(path))
        except Exception as e:
            logger.warning("zen save proxy pool failed: %s", e)

    async def candidates(self) -> List[Candidate]:
        if self._pool.count == 0 and PROXY_FETCH_ENABLED:
            return []
        return [
            Candidate(
                id=make_id("zen"),
                platform="zen",
                resource_id="proxy-pool",
                models=list(self._models),
                context_length=None,
                meta={"proxy_addr": "", "proxy_protocol": ""},
                **CAPS,
            )
        ]

    async def ensure_candidates(self, count: int) -> int:
        if self._pool.count == 0 and PROXY_FETCH_ENABLED:
            try:
                loop = asyncio.get_running_loop()
                pool = await loop.run_in_executor(None, self._do_proxy_fetch)
                await self._apply_pool(pool)
            except Exception:
                pass
        return 1 if self._pool.count > 0 else 0

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
        last_exc: Optional[Exception] = None
        failed_proxies: set = set()
        self._active_requests += 1
        try:
            attempt = 0
            while attempt < MAX_RETRIES:
                attempt += 1
                if PROXY_FETCH_ENABLED and self._pool.count > 0:
                    async with self._proxy_lock:
                        pool_addrs = self._pool.to_address_list()
                    available_proxies = [a for a in pool_addrs if a not in failed_proxies]
                    if not available_proxies:
                        raise PlatformError("No available proxies in pool")
                    chosen = self._selector.select(available_proxies)
                    new_addr = "" if (chosen == DIRECT or chosen is None) else chosen
                else:
                    new_addr = ""
                candidate.meta["proxy_addr"] = new_addr
                candidate.meta["proxy_protocol"] = "proxy" if new_addr else "direct"
                try:
                    has_content = False
                    async for chunk in self._do_request(candidate, messages, model, stream, **kw):
                        has_content = True
                        yield chunk
                    if not has_content:
                        if new_addr:
                            failed_proxies.add(new_addr)
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(min(2 ** (attempt - 1), 10))
                        continue
                    return
                except PlatformError:
                    raise
                except RuntimeError as e:
                    last_exc = e
                    if new_addr:
                        failed_proxies.add(new_addr)
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(min(2 ** (attempt - 1), 10))
                    continue
                except GeneratorExit:
                    raise
                except Exception as e:
                    last_exc = e
                    if new_addr:
                        failed_proxies.add(new_addr)
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(min(2 ** (attempt - 1), 10))
                    continue
            if last_exc:
                raise PlatformError(f"All {MAX_RETRIES} attempts failed") from last_exc
            raise PlatformError(f"All {MAX_RETRIES} attempts returned empty responses")
        finally:
            self._active_requests -= 1
            if self._active_requests == 0 and self._pool_refresh_pending:
                asyncio.ensure_future(self._check_deferred_refresh())

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        proxy_addr = candidate.meta.get("proxy_addr", "")
        selector_key = proxy_addr if proxy_addr else DIRECT
        headers = build_headers(proxy_addr)
        payload = build_payload(messages, model, stream=stream, **kw)
        url = "{}{}".format(BASE_URL, CHAT_PATH)
        request_kwargs: Dict[str, Any] = dict(
            headers=headers,
            json=payload,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=600 if stream else 120),
        )
        if proxy_addr:
            request_kwargs["proxy"] = "http://{}".format(proxy_addr)
        t0 = time.time()
        _request_ok = False
        _content_received = False
        _should_record_failure = True
        try:
            async with self._session.post(url, **request_kwargs) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    if resp.status == 429:
                        raise RuntimeError("zen rate limited (429): {}".format(body[:200]))
                    if 500 <= resp.status < 600:
                        raise RuntimeError("zen server error (HTTP {}): {}".format(resp.status, body[:200]))
                    raise PlatformError("zen HTTP{}: {}".format(resp.status, body[:200]))
                if not stream:
                    data = await resp.json()
                    choice = (data.get("choices") or [{}])[0]
                    msg = choice.get("message", {})
                    content = msg.get("content", "")
                    if content:
                        _content_received = True
                        _request_ok = True
                        _should_record_failure = False
                        yield content
                    tc = msg.get("tool_calls")
                    if tc:
                        _content_received = True
                        _request_ok = True
                        _should_record_failure = False
                        yield {"tool_calls": tc}
                    usage = data.get("usage")
                    if usage:
                        yield {"usage": {"prompt_tokens": usage.get("prompt_tokens", 0), "completion_tokens": usage.get("completion_tokens", 0)}}
                else:
                    _tc_accumulator: Dict[int, Dict[str, Any]] = {}
                    try:
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
                            if isinstance(parsed, dict):
                                if "tool_calls" in parsed:
                                    _content_received = True
                                    for tc_delta in parsed["tool_calls"]:
                                        idx = tc_delta.get("index", 0)
                                        if idx not in _tc_accumulator:
                                            _tc_accumulator[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
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
                                elif isinstance(parsed, str):
                                    if parsed:
                                        _content_received = True
                                        yield parsed
                                else:
                                    choices = parsed.get("choices", [])
                                    if choices:
                                        delta = choices[0].get("delta", {})
                                        content = delta.get("content")
                                        if content:
                                            _content_received = True
                                            yield content
                            elif isinstance(parsed, str):
                                if parsed:
                                    _content_received = True
                                    yield parsed
                        if _content_received:
                            _request_ok = True
                            _should_record_failure = False
                    except GeneratorExit:
                        if _content_received:
                            _request_ok = True
                            _should_record_failure = False
                        raise
                    except Exception as e:
                        _request_ok = False
                        _should_record_failure = True
                        raise RuntimeError(f"Stream processing error: {e}") from e
                    if _tc_accumulator:
                        yield {"tool_calls": [v for _, v in sorted(_tc_accumulator.items())]}
        except aiohttp.ClientError as e:
            _request_ok = False
            _should_record_failure = True
            raise RuntimeError(f"Network error: {e}") from e
        except asyncio.TimeoutError as e:
            _request_ok = False
            _should_record_failure = True
            raise RuntimeError(f"Timeout: {e}") from e
        except (PlatformError, RuntimeError):
            _request_ok = False
            _should_record_failure = True
            raise
        except Exception as e:
            _request_ok = False
            _should_record_failure = True
            raise RuntimeError(f"Unexpected error: {e}") from e
        finally:
            if _request_ok and _content_received:
                latency_ms = (time.time() - t0) * 1000.0
                self._selector.record_success(selector_key, latency_ms)
            elif _should_record_failure:
                self._selector.record_failure(selector_key)

    async def fetch_remote_models(self) -> List[str]:
        if not self._session:
            return []
        url = "{}{}".format(BASE_URL, MODELS_PATH)
        try:
            async with self._session.get(url, ssl=False, timeout=aiohttp.ClientTimeout(connect=10, total=30)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                model_data = data.get("data", [])
                if isinstance(model_data, list):
                    all_models = [m.get("id", "") for m in model_data if isinstance(m, dict) and m.get("id")]
                    if FILTER_PAID_MODELS:
                        return [m for m in all_models if m.endswith("-free")]
                    return all_models
                return []
        except Exception:
            return []

    def get_available_models(self) -> List[str]:
        return list(self._models)

    def update_models(self, models: List[str]) -> None:
        self._models = list(models)

    async def close(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
