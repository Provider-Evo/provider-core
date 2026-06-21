from __future__ import annotations

"""Ollama HTTP 客户端。

负责与 Ollama 服务器通信，支持流式/非流式请求、服务器发现、候选项构建。
"""

import asyncio
import concurrent.futures
import json
import os
import re
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import aiohttp

from src.core.dispatch.candidate import Candidate, make_id
from src.logger import get_logger
from src.platforms.ollama.accounts import ACCOUNTS
from src.platforms.ollama.core.constants import (
    BASE_URL,
    CHAT_PATH,
    DYNAMIC_DISCOVERY,
    EMBED_PATH,
    FILTER_CLOUD_MODELS,
    MAX_WORKERS,
    PAGE_SIZE,
    REFRESH_INTERVAL,
    TIMEOUT,
)

logger = get_logger(__name__)

MAX_RETRIES: int = 3
BG_REFRESH_INTERVAL: int = REFRESH_INTERVAL

# ── 持久化路径 ────────────────────────────────────────────
_SRV_FILE: Path = Path("persist/ollama/servers.json")
_REG_FILE: Path = Path("persist/ollama/registry.json")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 请求构建（core 层实现，util.py 负责重导出）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def build_image_messages(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将 OpenAI 格式的消息转换为 Ollama 格式。

    处理多模态消息中的 image_url，提取 base64 数据。

    Args:
        messages: OpenAI 格式的消息列表。

    Returns:
        Ollama 格式的消息列表。
    """
    if not messages:
        return []

    result: List[Dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "user")

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            text_parts: List[str] = []
            images: List[str] = []
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "image_url":
                    url = part.get("image_url", {}).get("url", "")
                    if url.startswith("data:") and ";base64," in url:
                        images.append(url.split(";base64,", 1)[1])
            entry: Dict[str, Any] = {
                "role": role,
                "content": "\n".join(text_parts),
            }
            if images:
                entry["images"] = images
            result.append(entry)
            continue

        result.append({"role": role, "content": str(content)})

    return result


def build_chat_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建 Ollama 聊天请求体。

    Args:
        messages: Ollama 格式的消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 额外参数（temperature, top_p, max_tokens, stop）。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }

    opts: Dict[str, Any] = {}
    if kw.get("temperature") is not None:
        opts["temperature"] = kw["temperature"]
    if kw.get("top_p") is not None:
        opts["top_p"] = kw["top_p"]
    if kw.get("max_tokens") is not None:
        opts["num_predict"] = kw["max_tokens"]
    if kw.get("stop"):
        opts["stop"] = kw["stop"]
    if opts:
        payload["options"] = opts

    return payload


def parse_ollama_line(
    line: bytes,
) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 Ollama 流式响应的单行 JSON。

    Ollama 的流式响应不是 SSE 格式，而是逐行 JSON。

    Args:
        line: 原始字节行（已去除首尾空白）。

    Returns:
        str（文本片段）、dict（usage）或 None（跳过）。
    """
    if not line:
        return None

    try:
        data = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    if "error" in data:
        raise ValueError("ollama error: {}".format(data["error"]))

    content = data.get("message", {}).get("content", "")

    if data.get("done"):
        usage: Dict[str, int] = {}
        if "prompt_eval_count" in data:
            usage["prompt_tokens"] = data["prompt_eval_count"]
        if "eval_count" in data:
            usage["completion_tokens"] = data["eval_count"]
        if usage:
            return {"usage": usage}
        return None

    if content:
        return content

    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 服务器发现（同步，需 run_in_executor 调用）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _fetch_page(page: int) -> Optional[str]:
    """获取指定页面的 HTML 内容。

    Args:
        page: 页码。

    Returns:
        HTML 字符串或 None。
    """
    try:
        import requests

        proxies = None
        try:
            from src.core.config import get_config
            cfg = get_config()
            if cfg.proxy.proxy_enabled and cfg.proxy.proxy_server:
                if not cfg.proxy.proxy_urls or any(
                    re.match(p, BASE_URL) for p in cfg.proxy.proxy_urls
                ):
                    proxies = {
                        "http": cfg.proxy.proxy_server,
                        "https": cfg.proxy.proxy_server,
                    }
        except Exception:
            pass

        r = requests.get(
            "{}?page={}&page_size={}".format(BASE_URL, page, PAGE_SIZE),
            timeout=TIMEOUT,
            verify=False,
            proxies=proxies,
        )
        if r.ok:
            return r.text
        return None
    except Exception:
        return None


def _parse_pages(html: str) -> int:
    """从 HTML 中解析总页数。

    Args:
        html: 首页 HTML 内容。

    Returns:
        总页数。
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        pag = soup.find("ul", class_="pagination")
        if not pag:
            return 1
        mx = 1
        for a in pag.find_all("a", class_="page-link"):
            m = re.search(r"page=(\d+)", a.get("href", ""))
            if m:
                mx = max(mx, int(m.group(1)))
        return mx
    except Exception:
        return 1


def _parse_ips(html: str) -> List[str]:
    """从 HTML 中提取服务器 IP 列表。

    Args:
        html: 页面 HTML 内容。

    Returns:
        IP 地址列表。
    """
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        ips: List[str] = []
        for btn in soup.find_all("button", onclick=True):
            m = re.search(
                r"copyToClipboard\('([^']+)'\)",
                btn.get("onclick", ""),
            )
            if m:
                ips.append(m.group(1))
        return ips
    except Exception:
        return []


def _show_model(base: str, name: str) -> Optional[Dict[str, Any]]:
    """查询模型详情。

    Args:
        base: 服务器基础 URL。
        name: 模型名称。

    Returns:
        模型详情字典或 None。
    """
    try:
        import requests

        r = requests.post(
            "{}/api/show".format(base),
            json={"name": name},
            timeout=TIMEOUT,
            verify=False,
        )
        if r.ok:
            return r.json()
        return None
    except Exception:
        return None


def detect_capabilities(detail: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    """从模型详情中检测能力。

    Args:
        detail: /api/show 返回的模型详情。

    Returns:
        能力字典。
    """
    caps: Dict[str, bool] = {
        "chat": True,
        "vision": False,
        "embedding": False,
        "tools": False,
    }
    if not detail:
        return caps

    model_info = detail.get("model_info") or {}
    for k in model_info:
        kl = k.lower()
        if any(x in kl for x in ("vision", "projector", "mmproj", "clip")):
            caps["vision"] = True
            break

    tpl = detail.get("template") or ""
    if "tools" in tpl.lower() or ".Tools" in tpl:
        caps["tools"] = True

    det = detail.get("details") or {}
    for fam in (det.get("families") or []):
        if any(x in fam.lower() for x in ("clip", "vision")):
            caps["vision"] = True

    params = detail.get("parameters") or ""
    if "embedding" in params.lower():
        caps["embedding"] = True
    if not caps["embedding"]:
        _name = (detail.get("name") or "").lower()
        _embed_kw = ("embed", "bge", "nomic", "text2vec", "e5-", "gte-", "sentence")
        if any(kw in _name for kw in _embed_kw):
            caps["embedding"] = True

    return caps


def _verify_server(ip: str) -> Optional[Dict[str, Any]]:
    """验证单个服务器并获取模型列表。

    Args:
        ip: 服务器 IP（含端口）。

    Returns:
        服务器信息字典或 None。
    """
    import requests

    if ip.startswith(("http://", "https://")):
        base = ip.rstrip("/")
    else:
        base = "http://{}".format(ip)
    try:
        r = requests.get(base, timeout=TIMEOUT)
        if "ollama" not in r.text.lower():
            return None
    except Exception:
        return None

    try:
        r = requests.get("{}/api/tags".format(base), timeout=TIMEOUT)
        models = r.json().get("models", [])
        if not models:
            return None
    except Exception:
        return None

    infos: List[Dict[str, Any]] = []
    for m in models:
        name = m.get("name", "")
        if not name:
            continue
        if FILTER_CLOUD_MODELS and name.endswith(":cloud"):
            continue
        detail = _show_model(base, name)
        _det = m.get("details") or {}
        infos.append({
            "name": name,
            "size": m.get("size", 0),
            "capabilities": detect_capabilities(detail),
            "family": _det.get("family") or "",
            "parameter_size": _det.get("parameter_size") or "",
        })

    return {
        "ip": ip,
        "base_url": base,
        "models": infos,
        "model_names": [m["name"] for m in infos],
        "verified_at": time.time(),
    }


def collect_servers(
    additional: Optional[List[str]] = None,
    skip_network: bool = False,
) -> Dict[str, Any]:
    """收集所有可用的 Ollama 服务器（网络 I/O 副作用）。

    从在线列表抓取 + 附加服务器列表合并后并发验证。

    Args:
        additional: 附加服务器 IP 列表。
        skip_network: 跳过网络抓取，仅验证 additional 列表中的服务器。

    Returns:
        服务器字典 {ip: server_info}。
    """
    all_ips: List[str] = []

    if not skip_network:
        html = _fetch_page(1)
        if html:
            pages = _parse_pages(html)
            all_ips.extend(_parse_ips(html))

            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
                futs = {
                    ex.submit(_fetch_page, p): p
                    for p in range(2, pages + 1)
                }
                for f in concurrent.futures.as_completed(futs):
                    r = f.result()
                    if r:
                        all_ips.extend(_parse_ips(r))

        all_ips = list(set(all_ips))

    if additional:
        for s in additional:
            if s and s not in all_ips:
                all_ips.append(s)

    result: Dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_verify_server, ip): ip for ip in all_ips}
        for f in concurrent.futures.as_completed(futs):
            try:
                info = f.result()
                if info:
                    result[info["ip"]] = info
            except Exception as e:
                logger.debug("验证服务器 %s 失败: %s", futs[f], e)

    return result


def build_registry(servers: Dict[str, Any]) -> Dict[str, Any]:
    """从服务器列表构建模型注册表。

    Args:
        servers: 服务器字典。

    Returns:
        模型注册表 {model_name: model_info}。
    """
    reg: Dict[str, Any] = {}
    for ip, srv in servers.items():
        for m in srv.get("models", []):
            name = m.get("name", "")
            if not name:
                continue
            if name not in reg:
                reg[name] = {
                    "servers": [],
                    "capabilities": m.get("capabilities", {"chat": True}),
                    "family": m.get("family", ""),
                }
            reg[name]["servers"].append({
                "ip": ip,
                "base_url": srv["base_url"],
            })
            for k, v in m.get("capabilities", {}).items():
                if v:
                    reg[name]["capabilities"][k] = True
    return reg


def save_cache(servers: Dict[str, Any], registry: Dict[str, Any]) -> None:
    """保存服务器和注册表到本地文件。

    Args:
        servers: 服务器字典。
        registry: 模型注册表。
    """
    for f in (_SRV_FILE, _REG_FILE):
        f.parent.mkdir(parents=True, exist_ok=True)

    tmp = str(_SRV_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            {"servers": servers, "last_refresh": time.time()},
            f,
            indent=2,
        )
    os.replace(tmp, str(_SRV_FILE))

    tmp = str(_REG_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            {"models": registry, "last_refresh": time.time()},
            f,
            indent=2,
        )
    os.replace(tmp, str(_REG_FILE))


def load_cache() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """从本地文件加载服务器和注册表。

    Returns:
        (服务器字典, 模型注册表) 元组。
    """
    srv: Dict[str, Any] = {}
    reg: Dict[str, Any] = {}
    if _SRV_FILE.exists():
        try:
            srv = json.loads(
                _SRV_FILE.read_text(encoding="utf-8")
            ).get("servers", {})
        except Exception:
            srv = {}
    if _REG_FILE.exists():
        try:
            reg = json.loads(
                _REG_FILE.read_text(encoding="utf-8")
            ).get("models", {})
        except Exception:
            reg = {}
    return srv, reg


def needs_refresh() -> bool:
    """判断是否需要重新发现服务器。

    Returns:
        True 表示需要刷新。
    """
    if not _SRV_FILE.exists():
        return True
    try:
        d = json.loads(_SRV_FILE.read_text(encoding="utf-8"))
        return time.time() - d.get("last_refresh", 0) >= REFRESH_INTERVAL
    except Exception:
        return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OllamaClient 类
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class OllamaClient:
    """Ollama HTTP 客户端。

    负责服务器发现、模型缓存、聊天请求。
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._servers: Dict[str, Any] = {}
        self._registry: Dict[str, Any] = {}

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化客户端，注入 session 并准备状态。

        Args:
            session: aiohttp 会话实例。
        """
        await self.init_immediate(session)
        await self.background_setup()

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化，不阻塞——从缓存加载。

        Args:
            session: aiohttp 会话实例。
        """
        self._session = session
        try:
            self._servers, self._registry = load_cache()
        except Exception as e:
            logger.warning("ollama缓存加载失败: %s", e)
            self._servers, self._registry = {}, {}
        logger.debug(
            "ollama客户端初始化完成（缓存: %d服务器, %d模型）",
            len(self._servers),
            len(self._registry),
        )

    async def background_setup(self) -> None:
        """后台完善：执行服务器发现并启动定时刷新。"""
        if not DYNAMIC_DISCOVERY:
            logger.debug(
                "ollama动态发现已禁用，使用持久化缓存（%d服务器, %d模型）",
                len(self._servers),
                len(self._registry),
            )
            return

        additional = [acc.server_url for acc in ACCOUNTS if acc.server_url]
        force = needs_refresh()
        try:
            loop = asyncio.get_running_loop()
            servers, registry = await loop.run_in_executor(
                None,
                lambda: _do_refresh(force=force, additional=additional),
            )
            self._servers = servers
            self._registry = registry
            logger.debug(
                "ollama发现完成: %d服务器, %d模型",
                len(servers),
                len(registry),
            )
        except Exception as e:
            logger.error("ollama服务器发现失败: %s", e)

        asyncio.ensure_future(self._bg_refresh())

    async def _bg_refresh(self) -> None:
        """后台定时刷新服务器列表。"""
        if not DYNAMIC_DISCOVERY:
            return
        while True:
            await asyncio.sleep(BG_REFRESH_INTERVAL)
            try:
                additional = [acc.server_url for acc in ACCOUNTS if acc.server_url]
                loop = asyncio.get_running_loop()
                servers, registry = await loop.run_in_executor(
                    None,
                    lambda: _do_refresh(force=True, additional=additional),
                )
                self._servers = servers
                self._registry = registry
                logger.debug("ollama刷新完成: %d服务器", len(servers))
            except Exception as e:
                logger.warning("ollama刷新失败: %s", e)

    def get_available_models(self) -> List[str]:
        """返回当前已发现的所有模型名称。

        Returns:
            模型名称列表。
        """
        return list(self._registry.keys())

    def update_models(self, models: List[str]) -> None:
        """更新模型列表（Ollama为动态发现，此方法为规范兼容）。

        Args:
            models: 新的模型列表（通常不使用，以动态发现为准）。
        """
        return

    async def candidates(self) -> List[Candidate]:
        """从已发现的服务器构建候选项列表。

        Returns:
            Candidate 实例列表。
        """
        from src.platforms.ollama.core.constants import CAPS

        out: List[Candidate] = []
        for ip, srv in self._servers.items():
            models = srv.get("model_names", [])
            if not models:
                continue
            caps: Dict[str, bool] = {"chat": True}
            for m_info in srv.get("models", []):
                for k, v in m_info.get("capabilities", {}).items():
                    if v:
                        caps[k] = True
            if not caps.get("embedding"):
                _embed_kw = ("embed", "bge", "nomic", "text2vec", "e5-", "gte-", "sentence")
                if any(kw in m.lower() for m in models for kw in _embed_kw):
                    caps["embedding"] = True
            out.append(
                Candidate(
                    id=make_id("ollama", ip),
                    platform="ollama",
                    resource_id=ip,
                    models=models,
                    context_length=None,
                    meta={"ip": ip, "base_url": srv["base_url"]},
                    **caps,
                )
            )
        return out

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。

        Args:
            count: 期望的最小候选项数量（未使用，仅接口兼容）。

        Returns:
            可用服务器数量。
        """
        return len(self._servers)

    async def create_embedding(
        self,
        candidate: "Candidate",
        input_data: Union[str, List[str]],
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        base_url = candidate.meta.get("base_url", "")
        if not base_url:
            raise ValueError("candidate 缺少 base_url")
        url = base_url.rstrip("/") + EMBED_PATH

        payload: Dict[str, Any] = {"model": model, "input": input_data}
        try:
            async with self._session.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"ollama HTTP {resp.status}: {body}")
                data = await resp.json()
        except asyncio.TimeoutError:
            raise RuntimeError(f"ollama embed 请求超时: {url}")

        embeddings = data.get("embeddings", [])
        return {
            "object": "list",
            "data": [
                {"object": "embedding", "index": i, "embedding": emb}
                for i, emb in enumerate(embeddings)
            ],
            "model": model,
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "total_tokens": data.get("prompt_eval_count", 0),
            },
        }

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行聊天补全，含重试。

        Args:
            candidate: 候选项实例。
            messages: OpenAI 格式的消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            thinking: 是否启用思考模式（Ollama 不支持，忽略）。
            search: 是否启用搜索（Ollama 不支持，忽略）。
            **kw: 额外参数（temperature, top_p, max_tokens, stop）。

        Yields:
            str（文本增量）、dict（usage/tool_calls）或 None。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    candidate, messages, model, stream, **kw
                ):
                    yield chunk
                return
            except Exception as e:
                last_exc = e
                logger.warning(
                    "ollama重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e
                )
        if last_exc:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 HTTP 请求。

        Args:
            candidate: 候选项实例。
            messages: Ollama 格式的消息列表。
            model: 模型名称。
            stream: 是否流式输出。
            **kw: 额外参数。

        Yields:
            str（文本增量）、dict（usage）或 None。

        Raises:
            Exception: HTTP 错误时抛出。
        """
        base_url = candidate.meta.get("base_url", "")
        if not base_url:
            raise ValueError("candidate.meta['base_url'] 为空")
        url = "{}{}".format(base_url, CHAT_PATH)

        chat_messages = build_image_messages(messages)
        payload = build_chat_payload(chat_messages, model, stream=stream, **kw)

        if self._session is None:
            raise RuntimeError("OllamaClient 未初始化，请先调用 init()")

        async with self._session.post(
            url,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=600),
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise Exception("ollama HTTP{}: {}".format(resp.status, body))

            if not stream:
                async for chunk in self._handle_non_stream(resp):
                    yield chunk
            else:
                async for chunk in self._handle_stream(resp):
                    yield chunk

    async def _handle_non_stream(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理非流式响应。

        Args:
            resp: HTTP 响应对象。

        Yields:
            文本内容或 usage 字典。
        """
        data = await resp.json()
        if "error" in data:
            raise Exception("ollama error: {}".format(data["error"]))
        content = data.get("message", {}).get("content", "")
        if content:
            yield content
        usage = _extract_usage(data)
        if usage:
            yield {"usage": usage}

    async def _handle_stream(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理流式响应。

        Args:
            resp: HTTP 响应对象。

        Yields:
            文本增量、usage 字典或 None。
        """
        buf = b""
        async for chunk in resp.content.iter_any():
            if not chunk:
                continue
            buf += chunk
            lines = buf.split(b"\n")
            buf = lines[-1]
            for line in lines[:-1]:
                stripped = line.strip()
                if not stripped:
                    continue
                parsed = parse_ollama_line(stripped)
                if parsed is not None:
                    yield parsed
                    if isinstance(parsed, dict) and "usage" in parsed:
                        return

        if buf.strip():
            parsed = parse_ollama_line(buf.strip())
            if parsed is not None:
                yield parsed

    async def close(self) -> None:
        """清理资源。"""
        return


def _extract_usage(data: Dict[str, Any]) -> Dict[str, int]:
    """从 Ollama 响应中提取 usage 信息。

    Args:
        data: JSON 响应数据。

    Returns:
        包含 prompt_tokens 和/或 completion_tokens 的字典。
    """
    usage: Dict[str, int] = {}
    if "prompt_eval_count" in data:
        usage["prompt_tokens"] = data["prompt_eval_count"]
    if "eval_count" in data:
        usage["completion_tokens"] = data["eval_count"]
    return usage


def _do_refresh(
    force: bool = False,
    additional: Optional[List[str]] = None,
    skip_network: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """同步刷新逻辑，供 run_in_executor 调用。

    Args:
        force: 是否强制刷新。
        additional: 附加服务器 URL 列表。
        skip_network: 跳过网络抓取，仅验证 additional 列表。

    Returns:
        (servers, registry) 元组。
    """
    if not force and not needs_refresh():
        return load_cache()

    cached_servers, cached_registry = load_cache()
    servers = collect_servers(additional=additional, skip_network=skip_network)
    registry = build_registry(servers)

    # 网络返回空结果但缓存有数据时，保留缓存不覆盖（网络故障保护）
    if not servers and cached_servers and not skip_network:
        logger.debug(
            "ollama网络发现返回空结果，保留缓存（%d服务器, %d模型）",
            len(cached_servers),
            len(cached_registry),
        )
        return cached_servers, cached_registry

    save_cache(servers, registry)
    return servers, registry
