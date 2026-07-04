# zen_server.py
"""Zen 平台独立服务器 - tools 归一化逻辑完全重构版本"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import ssl
import sys
import tempfile
import time
import uuid
from typing import Any, AsyncGenerator, AsyncIterator, Dict, List, Optional, Union

import aiohttp
from aiohttp import web

SERVER_VERSION: str = "2024-11-tools-fix-FINAL"

try:
    from curl_cffi.requests import AsyncSession as CurlAsyncSession  # type: ignore
    _HAS_CURL_CFFI = True
except Exception:
    CurlAsyncSession = None  # type: ignore
    _HAS_CURL_CFFI = False

# ============================================================
# 全局常量配置
# ============================================================

PORT: int = 7331
MAX_CONCURRENT: int = 4
MAX_QUEUE_SIZE: int = 1000

PROXY_POOL: List[Optional[str]] = [
    "http://127.0.0.1:10808",
    "http://127.0.0.1:7500",
    "http://127.0.0.1:7890",
    None,
]

DATA_FILE: str = "zen_data.json"

CONNECT_TIMEOUT: float = 60.0
FIRST_CHUNK_TIMEOUT: float = 60.0
STREAM_TOTAL_TIMEOUT: float = 600.0
STREAM_READ_TIMEOUT: float = 600.0
NON_STREAM_TIMEOUT: float = 180.0
MODELS_FETCH_TIMEOUT: float = 60.0

RETRY_COUNT: int = 2
MAX_REQUEST_RESTARTS: int = -1
RESTART_DELAY: float = 0.2

FALLBACK_MODEL: str = "mimo-v2.5-free"
FALLBACK_MODEL_ENABLED: bool = True

BASE_URL: str = "https://opencode.ai/zen/v1"
CHAT_PATH: str = "/chat/completions"
MODELS_PATH: str = "/models"

USE_CURL_CFFI: bool = True
IMPERSONATE_PROFILE: str = "chrome124"
DEBUG_LOG_BODY: bool = True
DEFAULT_USER_AGENT: str = "curl/8.7.1"

DEFAULT_MODELS: List[str] = [
    "mimo-v2.5-free",
    "deepseek-v4-flash-free",
    "qwen3.6-plus-free",
    "minimax-m3-free",
    "nemotron-3-ultra-free",
    "north-mini-code-free",
]

CAPABILITIES: Dict[str, bool] = {
    "chat": True,
    "vision": True,
    "tools": True,
    "native_tools": True,
    "thinking": True,
    "search": False,
}

# ============================================================
# 强制刷新的日志工具（不依赖 print 缓冲）
# ============================================================

def _log(msg: str) -> None:
    """立即写入 stderr 并刷新，确保日志实时可见。"""
    sys.stderr.write("[zen] {}\n".format(msg))
    sys.stderr.flush()

# ============================================================
# ID 生成
# ============================================================

def _gen_id(prefix: str) -> str:
    return "{}_{}".format(prefix, uuid.uuid4().hex[:24])

def _msg_id() -> str:
    return _gen_id("msg")

def _tool_id() -> str:
    return _gen_id("toolu")

# ============================================================
# 工具（tools）归一化 —— 统一入口，只调用一次
# ============================================================

def _normalize_tool_entry(t: Any) -> Optional[Dict[str, Any]]:
    """把单个 tool 定义归一化为标准 OpenAI 格式。
    
    兼容两种输入：
      1) OpenAI: {"type":"function","function":{"name":...,"parameters":...}}
      2) Anthropic: {"name":...,"description":...,"input_schema":...}
    """
    if not isinstance(t, dict):
        return None

    # 形态1: OpenAI 原生，function.name 存在
    func = t.get("function")
    if isinstance(func, dict) and func.get("name"):
        return {
            "type": "function",
            "function": {
                "name": func["name"],
                "description": func.get("description", "") or "",
                "parameters": func.get("parameters") or func.get("input_schema") or {},
            },
        }

    # 形态2: Anthropic 原生，顶层 name 存在
    name = t.get("name")
    if name:
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": t.get("description", "") or "",
                "parameters": t.get("input_schema") or t.get("parameters") or {},
            },
        }

    _log("WARN: Dropping tool (no name): {}".format(json.dumps(t, ensure_ascii=False)[:150]))
    return None

def normalize_tools(tools: Any) -> Optional[List[Dict[str, Any]]]:
    """对一整个 tools 列表做归一化。
    
    重要：每个请求路径（OpenAI / Anthropic）只调用这个函数**一次**，
    之后直接使用归一化结果，不再二次转换。
    """
    if not tools or not isinstance(tools, list):
        return None
    normalized = [
        nt for nt in (_normalize_tool_entry(t) for t in tools) if nt is not None
    ]
    result = normalized or None
    if result:
        names = [
            t["function"]["name"] for t in result
            if isinstance(t, dict) and isinstance(t.get("function"), dict)
        ]
        _log("normalize_tools: {} raw -> {} normalized: {}".format(
            len(tools), len(result), names
        ))
    else:
        _log("normalize_tools: {} raw -> 0 normalized (all invalid or empty)".format(
            len(tools) if isinstance(tools, list) else 0
        ))
    return result

# ============================================================
# Payload 构建（不再做任何 tools 转换，只接收已归一化的）
# ============================================================

def build_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    tools: Optional[List[Dict[str, Any]]] = None,  # 已归一化或 None
    **kw: Any,
) -> Dict[str, Any]:
    """构建发给上游的 payload。
    
    注意：tools 参数现在是**已归一化**的 OpenAI 格式，或者 None。
    这个函数**不再**调用 normalize_tools，避免重复转换。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if kw.get("temperature") is not None:
        payload["temperature"] = kw["temperature"]
    if kw.get("top_p") is not None:
        payload["top_p"] = kw["top_p"]
    if kw.get("max_tokens") is not None:
        payload["max_tokens"] = kw["max_tokens"]
    if kw.get("stop"):
        payload["stop"] = kw["stop"]
    
    # 关键修改：直接使用传入的 tools（已归一化），不再二次转换
    if tools:
        payload["tools"] = tools
    
    if kw.get("tool_choice") and payload.get("tools"):
        payload["tool_choice"] = kw["tool_choice"]
    if kw.get("thinking"):
        payload["thinking"] = True
    if kw.get("search"):
        payload["search"] = True
    
    return payload

# ============================================================
# 请求头构建 / 调试日志
# ============================================================

def _build_headers(stream: bool) -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
        "User-Agent": DEFAULT_USER_AGENT,
    }

def _debug_log_body(status: int, text: str) -> None:
    if not DEBUG_LOG_BODY:
        return
    snippet = (text or "")[:1500]
    _log("Upstream HTTP {} raw body: {}".format(status, snippet))

# ============================================================
# SSE 解析
# ============================================================

def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    if not data_str or data_str == "[DONE]":
        return None
    try:
        obj = json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None

    choice = (obj.get("choices") or [{}])[0]
    delta = choice.get("delta", {})

    reasoning = delta.get("reasoning") or delta.get("reasoning_content")
    if reasoning:
        return {"thinking": reasoning}

    content = delta.get("content", "")
    if content:
        return content

    tc = delta.get("tool_calls")
    if tc:
        return {"tool_calls": tc}

    usage = obj.get("usage")
    if usage and isinstance(usage, dict):
        return {"usage": {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
        }}

    return None

def _extract_error_info(data: Any) -> Optional[Dict[str, str]]:
    if not isinstance(data, dict):
        return None
    error_obj = None
    if data.get("type") == "error":
        error_obj = data.get("error", {})
    elif "error" in data:
        error_obj = data["error"]
    if error_obj is None:
        return None
    if not isinstance(error_obj, dict):
        return {"type": "", "message": str(error_obj)}

    message = error_obj.get("message", "") or str(error_obj)
    err_type = error_obj.get("type", "") or ""
    param = None

    metadata = error_obj.get("metadata")
    if isinstance(metadata, dict):
        raw = metadata.get("raw")
        if isinstance(raw, str):
            try:
                raw_obj = json.loads(raw)
                raw_err = raw_obj.get("error") if isinstance(raw_obj, dict) else None
                if isinstance(raw_err, dict):
                    message = raw_err.get("message", message) or message
                    err_type = raw_err.get("type", "") or err_type
                    param = raw_err.get("param")
            except (json.JSONDecodeError, ValueError):
                pass

    result: Dict[str, str] = {"type": err_type, "message": message}
    if param:
        result["param"] = param
    return result

def _is_model_error(err_info: Dict[str, str]) -> bool:
    err_type = (err_info.get("type") or "").lower()
    err_msg = (err_info.get("message") or "").lower()
    if "modelerror" in err_type:
        return True
    if "not supported" in err_msg and "model" in err_msg:
        return True
    return False

def _is_validation_error(err_info: Dict[str, str]) -> bool:
    if err_info.get("param"):
        return True
    msg = (err_info.get("message") or "").lower()
    for kw in ("param incorrect", "missing function.name", "invalid_request",
               "invalid request", "bad request", "is missing"):
        if kw in msg:
            return True
    return False

def _classify_http_error(
    status: int, err_info: Optional[Dict[str, str]], raw_text: str
) -> Exception:
    msg = err_info["message"] if err_info else (raw_text or "")[:300]

    if err_info and _is_model_error(err_info):
        return ModelNotSupportedError(msg)

    if status == 429:
        return RateLimitedError("HTTP 429 - {}".format(msg))

    if status == 400:
        return ProviderValidationError(msg)

    return UpstreamError("HTTP {} - {}".format(status, msg))

# ============================================================
# 通用 SSE 行缓冲解析器
# ============================================================

async def _iter_sse_lines(chunk_iter: AsyncIterator[bytes]) -> AsyncGenerator[str, None]:
    buffer = ""
    async for raw in chunk_iter:
        if not raw:
            continue
        if isinstance(raw, bytes):
            buffer += raw.decode("utf-8", errors="replace")
        else:
            buffer += str(raw)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip("\r").strip()
            if line:
                yield line
    tail = buffer.strip()
    if tail:
        yield tail

def _check_and_pass(line: str) -> Optional[str]:
    if not line.startswith("data:"):
        return None
    data_str = line[5:].strip()
    if data_str and data_str != "[DONE]":
        try:
            obj = json.loads(data_str)
        except json.JSONDecodeError:
            obj = None
        if obj is not None:
            err_info = _extract_error_info(obj)
            if err_info:
                if _is_model_error(err_info):
                    raise ModelNotSupportedError(err_info["message"])
                if _is_validation_error(err_info):
                    raise ProviderValidationError(err_info["message"])
                raise UpstreamError("API error: {}".format(err_info["message"]))
    return line

# ============================================================
# HTTP 响应工具
# ============================================================

def _json_response(data: Any, status: int = 200) -> web.Response:
    return web.json_response(
        data, status=status,
        dumps=lambda x: json.dumps(x, ensure_ascii=False),
    )

def _error_response(
    status: int,
    message: str,
    error_type: str = "invalid_request_error",
) -> web.Response:
    return _json_response({
        "error": {"message": message, "type": error_type, "code": status}
    }, status=status)

async def _get_json(request: web.Request) -> Optional[Dict[str, Any]]:
    try:
        return await request.json()
    except (json.JSONDecodeError, ValueError):
        return None

# ============================================================
# SSL Context
# ============================================================

def _make_ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

# ============================================================
# 自定义异常
# ============================================================

class UpstreamError(RuntimeError):
    pass

class RateLimitedError(UpstreamError):
    pass

class ModelNotSupportedError(RuntimeError):
    pass

class ProviderValidationError(RuntimeError):
    pass

# ============================================================
# curl_cffi 响应读取辅助
# ============================================================

async def _read_curl_text(resp: Any) -> str:
    if hasattr(resp, "atext"):
        try:
            result = resp.atext()
            if asyncio.iscoroutine(result):
                return await result
            return result
        except TypeError:
            pass
    text = getattr(resp, "text", "")
    return text if isinstance(text, str) else ""

async def _read_curl_json(resp: Any) -> Any:
    json_attr = getattr(resp, "json", None)
    if json_attr is not None:
        try:
            result = json_attr()
            if asyncio.iscoroutine(result):
                result = await result
            return result
        except Exception:
            pass
    text = await _read_curl_text(resp)
    return json.loads(text)

def _curl_byte_iter(resp: Any) -> AsyncIterator[bytes]:
    if hasattr(resp, "aiter_content"):
        return resp.aiter_content()
    if hasattr(resp, "aiter_bytes"):
        return resp.aiter_bytes()
    if hasattr(resp, "aiter_raw"):
        return resp.aiter_raw()
    raise UpstreamError("curl_cffi response missing async content iterator")

# ============================================================
# 节点管理器
# ============================================================

class NodeManager:
    def __init__(self, pool: List[Optional[str]], data_file: str) -> None:
        self._pool: List[Optional[str]] = pool if pool else [None]
        self._data_file = data_file
        self._current_index: int = 0
        self._lock = asyncio.Lock()
        self._load()

    def _load(self) -> None:
        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            idx = int(data.get("current_node_index", 0))
            if 0 <= idx < len(self._pool):
                self._current_index = idx
                _log("NodeManager: Restored node index {} ({})".format(
                    idx, self._describe(idx)
                ))
            else:
                self._current_index = 0
        except FileNotFoundError:
            self._current_index = 0
            _log("NodeManager: No data file, starting from index 0.")
        except Exception as e:
            self._current_index = 0
            _log("NodeManager: Load failed: {}. Reset to 0.".format(e))

    def _save(self) -> None:
        data = {
            "current_node_index": self._current_index,
            "current_node": self._describe(self._current_index),
            "updated_at": int(time.time()),
        }
        tmp_path = None
        try:
            dir_name = os.path.dirname(os.path.abspath(self._data_file)) or "."
            with tempfile.NamedTemporaryFile(
                mode="w", dir=dir_name, delete=False,
                suffix=".tmp", encoding="utf-8",
            ) as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                tmp_path = f.name
            os.replace(tmp_path, self._data_file)
        except Exception as e:
            _log("NodeManager: Save failed: {}".format(e))
            try:
                if tmp_path:
                    os.unlink(tmp_path)
            except Exception:
                pass

    def _describe(self, index: int) -> str:
        node = self._pool[index]
        return "direct" if node is None else node

    @property
    def current_proxy(self) -> Optional[str]:
        return self._pool[self._current_index]

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def current_description(self) -> str:
        return self._describe(self._current_index)

    @property
    def pool_size(self) -> int:
        return len(self._pool)

    async def switch_next(self) -> str:
        async with self._lock:
            self._current_index = (self._current_index + 1) % len(self._pool)
            desc = self._describe(self._current_index)
            _log("NodeManager: Switched to index {} ({})".format(
                self._current_index, desc
            ))
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._save)
        return desc

# ============================================================
# 并发调度器
# ============================================================

class QueueFullError(Exception):
    pass

class RequestScheduler:
    def __init__(self, max_concurrent: int, max_queue: int) -> None:
        self._max_concurrent = max_concurrent
        self._max_queue = max_queue
        self._semaphore: Optional[asyncio.Semaphore] = (
            asyncio.Semaphore(max_concurrent) if max_concurrent != -1 else None
        )
        self._pending: int = 0
        self._lock = asyncio.Lock()

    @property
    def pending(self) -> int:
        return self._pending

    async def submit(self, coro_factory) -> Any:
        async with self._lock:
            if self._max_queue > 0 and self._pending >= self._max_queue:
                raise QueueFullError(
                    "Server is busy, please try again later. "
                    "Queue limit ({}) reached.".format(self._max_queue)
                )
            self._pending += 1
        try:
            if self._semaphore is not None:
                async with self._semaphore:
                    return await coro_factory()
            else:
                return await coro_factory()
        finally:
            async with self._lock:
                self._pending -= 1

# ============================================================
# 活跃请求追踪
# ============================================================

class ActiveRequestTracker:
    def __init__(self) -> None:
        self._tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def register(self, req_id: str, task: asyncio.Task) -> None:
        async with self._lock:
            self._tasks[req_id] = task

    async def unregister(self, req_id: str) -> None:
        async with self._lock:
            self._tasks.pop(req_id, None)

    async def cancel_all(self) -> int:
        current = asyncio.current_task()
        async with self._lock:
            targets = [
                t for t in self._tasks.values()
                if t is not current and not t.done()
            ]
            for t in targets:
                t.cancel()
            self._tasks = {
                rid: t for rid, t in self._tasks.items()
                if t is current
            }
            return len(targets)

    @property
    def count(self) -> int:
        return len(self._tasks)

# ============================================================
# 全局应用状态
# ============================================================

class AppState:
    def __init__(self) -> None:
        self.node_manager = NodeManager(PROXY_POOL, DATA_FILE)
        self.scheduler = RequestScheduler(MAX_CONCURRENT, MAX_QUEUE_SIZE)
        self.tracker = ActiveRequestTracker()
        self.zen_client = ZenClient(self)

_app_state: Optional[AppState] = None

def get_state() -> AppState:
    global _app_state
    if _app_state is None:
        _app_state = AppState()
    return _app_state

# ============================================================
# Zen HTTP 客户端
# ============================================================

class ZenClient:
    def __init__(self, state: AppState) -> None:
        self._state = state
        self._models: List[str] = list(DEFAULT_MODELS)
        self._use_curl: bool = bool(USE_CURL_CFFI and _HAS_CURL_CFFI)

        if USE_CURL_CFFI and not _HAS_CURL_CFFI:
            _log("curl_cffi not installed, falling back to aiohttp. "
                 "Recommend: pip install curl_cffi")
        _log("HTTP backend: {}".format(
            "curl_cffi (impersonate={})".format(IMPERSONATE_PROFILE)
            if self._use_curl else "aiohttp"
        ))

    def _make_session(self) -> aiohttp.ClientSession:
        connector = aiohttp.TCPConnector(
            ssl=_make_ssl_ctx(),
            use_dns_cache=False,
            limit=100,
        )
        return aiohttp.ClientSession(
            connector=connector,
            trust_env=False,
        )

    async def fetch_models(self) -> List[str]:
        proxy = self._state.node_manager.current_proxy
        url = "{}{}".format(BASE_URL, MODELS_PATH)
        try:
            if self._use_curl:
                data = await self._fetch_models_curl(url, proxy)
            else:
                data = await self._fetch_models_aiohttp(url, proxy)

            if data is None:
                return list(DEFAULT_MODELS)

            err_info = _extract_error_info(data)
            if err_info:
                _log("fetch_models error: {}".format(err_info["message"]))
                return list(DEFAULT_MODELS)

            model_data = data.get("data", [])
            if isinstance(model_data, list):
                models = [
                    m.get("id", "") for m in model_data
                    if isinstance(m, dict) and m.get("id")
                ]
                free = [m for m in models if m.endswith("-free")]
                if free:
                    self._models = free
                    return free
            return list(DEFAULT_MODELS)
        except Exception as e:
            _log("fetch_models exception: {}".format(e))
            return list(DEFAULT_MODELS)

    async def _fetch_models_aiohttp(
        self, url: str, proxy: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        async with self._make_session() as session:
            kw: Dict[str, Any] = {
                "timeout": aiohttp.ClientTimeout(
                    connect=CONNECT_TIMEOUT,
                    total=MODELS_FETCH_TIMEOUT,
                ),
                "headers": _build_headers(False),
            }
            if proxy:
                kw["proxy"] = proxy
            async with session.get(url, **kw) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()

    async def _fetch_models_curl(
        self, url: str, proxy: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        session_kwargs: Dict[str, Any] = {}
        if IMPERSONATE_PROFILE:
            session_kwargs["impersonate"] = IMPERSONATE_PROFILE
        async with CurlAsyncSession(**session_kwargs) as session:  # type: ignore
            kw: Dict[str, Any] = {
                "headers": _build_headers(False),
                "timeout": MODELS_FETCH_TIMEOUT,
            }
            if proxy:
                kw["proxy"] = proxy
            resp = await session.get(url, **kw)
            status = getattr(resp, "status_code", None)
            if status is None:
                status = getattr(resp, "status", 0)
            if status != 200:
                return None
            return await _read_curl_json(resp)

    async def _do_request(
        self,
        proxy: Optional[str],
        payload: Dict[str, Any],
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        # 诊断日志：发送给上游前打印 payload 里的 tools
        tools_in_payload = payload.get("tools", [])
        tool_names = [
            t["function"]["name"]
            for t in tools_in_payload
            if isinstance(t, dict)
               and isinstance(t.get("function"), dict)
               and t["function"].get("name")
        ]
        _log("_do_request: sending to upstream, tools={}".format(tool_names))

        if self._use_curl:
            gen = self._do_request_curl(proxy, payload, stream)
        else:
            gen = self._do_request_aiohttp(proxy, payload, stream)
        async for chunk in gen:
            yield chunk

    async def _do_request_aiohttp(
        self,
        proxy: Optional[str],
        payload: Dict[str, Any],
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        url = "{}{}".format(BASE_URL, CHAT_PATH)

        if stream:
            timeout = aiohttp.ClientTimeout(
                total=STREAM_TOTAL_TIMEOUT,
                connect=CONNECT_TIMEOUT,
                sock_read=STREAM_READ_TIMEOUT,
            )
        else:
            timeout = aiohttp.ClientTimeout(
                total=NON_STREAM_TIMEOUT,
                connect=CONNECT_TIMEOUT,
            )

        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        try:
            async with self._make_session() as session:
                kw: Dict[str, Any] = {
                    "headers": _build_headers(stream),
                    "data": body_bytes,
                    "timeout": timeout,
                }
                if proxy:
                    kw["proxy"] = proxy

                async with session.post(url, **kw) as resp:
                    if resp.status != 200:
                        err_text = await resp.text()
                        _debug_log_body(resp.status, err_text)
                        err_info = None
                        try:
                            err_data = json.loads(err_text)
                            err_info = _extract_error_info(err_data)
                        except (json.JSONDecodeError, ValueError):
                            pass
                        raise _classify_http_error(resp.status, err_info, err_text)

                    if not stream:
                        data = await resp.json()
                        err_info = _extract_error_info(data)
                        if err_info:
                            if _is_model_error(err_info):
                                raise ModelNotSupportedError(err_info["message"])
                            if _is_validation_error(err_info):
                                raise ProviderValidationError(err_info["message"])
                            raise UpstreamError(
                                "API error: {}".format(err_info["message"])
                            )
                        yield data
                        return

                    line_iter = _iter_sse_lines(resp.content.iter_any()).__aiter__()

                    try:
                        first_line = await asyncio.wait_for(
                            line_iter.__anext__(),
                            timeout=FIRST_CHUNK_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        raise UpstreamError(
                            "First chunk timeout ({}s)".format(FIRST_CHUNK_TIMEOUT)
                        )
                    except StopAsyncIteration:
                        return

                    out = _check_and_pass(first_line)
                    if out is not None:
                        yield out

                    async for line in line_iter:
                        out = _check_and_pass(line)
                        if out is not None:
                            yield out

        except (ModelNotSupportedError, ProviderValidationError, UpstreamError):
            raise
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError as e:
            raise UpstreamError("Request timeout: {}".format(e))
        except Exception as e:
            raise UpstreamError("Request error: {}".format(e))

    async def _do_request_curl(
        self,
        proxy: Optional[str],
        payload: Dict[str, Any],
        stream: bool,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        if CurlAsyncSession is None:
            raise UpstreamError("curl_cffi backend selected but not installed")

        url = "{}{}".format(BASE_URL, CHAT_PATH)
        headers = _build_headers(stream)
        body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        timeout = STREAM_TOTAL_TIMEOUT if stream else NON_STREAM_TIMEOUT

        session_kwargs: Dict[str, Any] = {}
        if IMPERSONATE_PROFILE:
            session_kwargs["impersonate"] = IMPERSONATE_PROFILE

        resp: Any = None
        try:
            async with CurlAsyncSession(**session_kwargs) as session:  # type: ignore
                req_kwargs: Dict[str, Any] = {
                    "headers": headers,
                    "data": body_bytes,
                    "timeout": timeout,
                    "stream": stream,
                }
                if proxy:
                    req_kwargs["proxy"] = proxy

                resp = await session.post(url, **req_kwargs)
                status = getattr(resp, "status_code", None)
                if status is None:
                    status = getattr(resp, "status", 0)

                if status != 200:
                    err_text = await _read_curl_text(resp)
                    _debug_log_body(status, err_text)
                    err_info = None
                    try:
                        err_data = json.loads(err_text)
                        err_info = _extract_error_info(err_data)
                    except (json.JSONDecodeError, ValueError, TypeError):
                        pass
                    raise _classify_http_error(status, err_info, err_text)

                if not stream:
                    data = await _read_curl_json(resp)
                    err_info = _extract_error_info(data)
                    if err_info:
                        if _is_model_error(err_info):
                            raise ModelNotSupportedError(err_info["message"])
                        if _is_validation_error(err_info):
                            raise ProviderValidationError(err_info["message"])
                        raise UpstreamError(
                            "API error: {}".format(err_info["message"])
                        )
                    yield data
                    return

                byte_iter = _curl_byte_iter(resp)
                line_iter = _iter_sse_lines(byte_iter).__aiter__()

                try:
                    first_line = await asyncio.wait_for(
                        line_iter.__anext__(),
                        timeout=FIRST_CHUNK_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    raise UpstreamError(
                        "First chunk timeout ({}s)".format(FIRST_CHUNK_TIMEOUT)
                    )
                except StopAsyncIteration:
                    return

                out = _check_and_pass(first_line)
                if out is not None:
                    yield out

                async for line in line_iter:
                    out = _check_and_pass(line)
                    if out is not None:
                        yield out

        except (ModelNotSupportedError, ProviderValidationError, UpstreamError):
            raise
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError as e:
            raise UpstreamError("Request timeout: {}".format(e))
        except Exception as e:
            raise UpstreamError("Request error (curl_cffi): {}".format(e))
        finally:
            if resp is not None and hasattr(resp, "aclose"):
                try:
                    await resp.aclose()
                except Exception:
                    pass

    async def chat_completion(
        self,
        payload: Dict[str, Any],
        _fallback_applied: bool = False,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        stream = payload.get("stream", False)
        last_error: Optional[Exception] = None

        for attempt in range(1 + RETRY_COUNT):
            proxy = self._state.node_manager.current_proxy
            desc = self._state.node_manager.current_description
            yielded_any = False

            try:
                if attempt > 0:
                    _log("Retry {}/{} via {}".format(attempt, RETRY_COUNT, desc))
                else:
                    _log("Request via {} (model={})".format(desc, payload.get("model")))

                async for chunk in self._do_request(proxy, payload, stream):
                    yielded_any = True
                    yield chunk
                return

            except asyncio.CancelledError:
                raise

            except ModelNotSupportedError as e:
                _log("Model not supported: {}".format(e))
                if (
                    FALLBACK_MODEL_ENABLED
                    and not _fallback_applied
                    and payload.get("model") != FALLBACK_MODEL
                ):
                    _log("Falling back to model: {}".format(FALLBACK_MODEL))
                    fallback_payload = dict(payload)
                    fallback_payload["model"] = FALLBACK_MODEL
                    async for chunk in self.chat_completion(
                        fallback_payload, _fallback_applied=True
                    ):
                        yield chunk
                    return
                else:
                    raise

            except ProviderValidationError as e:
                _log("Provider rejected request params (not retrying): {}".format(e))
                raise

            except RateLimitedError as e:
                last_error = e
                _log("Rate limited on {}: {}. Skipping remaining retries.".format(desc, e))
                break

            except Exception as e:
                last_error = e
                _log("Attempt {}/{} failed (yielded_any={}): {}".format(
                    attempt + 1, 1 + RETRY_COUNT, yielded_any, e
                ))
                if yielded_any:
                    break
                continue

        _log("Giving up on current node. Switching...")
        new_node = await self._state.node_manager.switch_next()
        cancelled = await self._state.tracker.cancel_all()
        _log("Switched to {}. Cancelled {} other request(s).".format(new_node, cancelled))
        raise UpstreamError(
            "Request failed (last: {}). Switched to node: {}.".format(
                last_error, new_node
            )
        )

# ============================================================
# 弹性重启包装器
# ============================================================

async def _run_resilient(
    req_id: str,
    state: AppState,
    func,
) -> Any:
    attempts = 0
    last_error: Optional[Exception] = None

    while True:
        task = asyncio.current_task()
        await state.tracker.register(req_id, task)
        try:
            result = await func()
            return result
        except asyncio.CancelledError:
            attempts += 1
            _log("resilient: {} cancelled (restart #{})".format(req_id, attempts))
        except UpstreamError as e:
            attempts += 1
            last_error = e
            _log("resilient: {} upstream error (restart #{}): {}".format(req_id, attempts, e))
        except ModelNotSupportedError:
            raise
        except ProviderValidationError:
            raise
        except ConnectionResetError:
            _log("resilient: {} client disconnected.".format(req_id))
            raise
        finally:
            await state.tracker.unregister(req_id)

        if MAX_REQUEST_RESTARTS != -1 and attempts >= MAX_REQUEST_RESTARTS:
            raise UpstreamError(
                "Max restarts ({}) exceeded for {}. Last: {}".format(
                    MAX_REQUEST_RESTARTS, req_id, last_error
                )
            )

        await asyncio.sleep(RESTART_DELAY)

# ============================================================
# 流式写入辅助
# ============================================================

async def _sse_write(resp: web.StreamResponse, event: str, data: Any) -> None:
    try:
        await resp.write(
            "event: {}\ndata: {}\n\n".format(
                event, json.dumps(data, ensure_ascii=False)
            ).encode("utf-8")
        )
    except Exception:
        pass

# ============================================================
# OpenAI 兼容端点
# ============================================================

async def health_handler(request: web.Request) -> web.Response:
    state = get_state()
    return _json_response({
        "status": "ok",
        "platform": "zen",
        "version": SERVER_VERSION,
        "timestamp": int(time.time()),
        "node": {
            "current": state.node_manager.current_description,
            "index": state.node_manager.current_index,
            "pool_size": state.node_manager.pool_size,
        },
        "scheduler": {
            "max_concurrent": MAX_CONCURRENT,
            "max_queue": MAX_QUEUE_SIZE,
            "pending": state.scheduler.pending,
        },
        "http_backend": "curl_cffi" if state.zen_client._use_curl else "aiohttp",
    })

async def list_models_handler(request: web.Request) -> web.Response:
    state = get_state()
    models = await state.zen_client.fetch_models()
    return _json_response({
        "object": "list",
        "data": [
            {"id": m, "object": "model", "created": 1700000000, "owned_by": "zen"}
            for m in models
        ],
    })

async def get_model_handler(request: web.Request) -> web.Response:
    model_id = request.match_info.get("model_id", "")
    state = get_state()
    models = await state.zen_client.fetch_models()
    for m in models:
        if m == model_id:
            return _json_response({
                "id": m, "object": "model",
                "created": 1700000000, "owned_by": "zen",
            })
    return _error_response(404, "Model not found: {}".format(model_id), "model_not_found")

async def chat_completions_handler(request: web.Request) -> web.StreamResponse:
    state = get_state()

    if MAX_QUEUE_SIZE > 0 and state.scheduler.pending >= MAX_QUEUE_SIZE:
        return web.Response(
            status=503,
            text="Server is busy, please try again later.",
            content_type="text/plain",
        )

    body = await _get_json(request)
    if body is None:
        return _error_response(400, "Invalid JSON in request body")
    if not body.get("messages"):
        return _error_response(400, "messages is required")
    if not body.get("model"):
        return _error_response(400, "model is required")

    # ★ 关键改动：在这里直接归一化 tools（只调用一次）
    normalized_tools = normalize_tools(body.get("tools"))
    _log("chat_completions: normalized_tools={}".format(
        [t["function"]["name"] for t in (normalized_tools or [])
         if isinstance(t, dict) and isinstance(t.get("function"), dict)]
    ))

    extra = body.get("extra_body") or body.get("extra") or {}
    payload = build_payload(
        messages=body["messages"],
        model=body["model"],
        stream=bool(body.get("stream", False)),
        tools=normalized_tools,  # 直接传归一化后的结果
        temperature=body.get("temperature"),
        top_p=body.get("top_p"),
        max_tokens=body.get("max_tokens"),
        stop=body.get("stop"),
        tool_choice=body.get("tool_choice"),
        thinking=bool(extra.get("thinking", False) or body.get("thinking", False)),
        search=bool(extra.get("search", False) or body.get("search", False)),
    )

    stream = payload["stream"]
    req_id = _gen_id("req")

    if not stream:
        async def _do_non_stream():
            result = None
            async for chunk in state.zen_client.chat_completion(payload):
                result = chunk
                break
            return result

        try:
            result = await state.scheduler.submit(
                lambda: _run_resilient(req_id, state, _do_non_stream)
            )
            if result is None:
                return _error_response(500, "No response from Zen API")
            return _json_response(result)
        except QueueFullError as e:
            return web.Response(status=503, text=str(e), content_type="text/plain")
        except ModelNotSupportedError as e:
            return _error_response(400, str(e), "model_not_supported")
        except ProviderValidationError as e:
            return _error_response(400, str(e), "invalid_request_error")
        except UpstreamError as e:
            return _error_response(502, str(e), "upstream_error")
        except Exception as e:
            return _error_response(500, str(e), "server_error")

    resp = web.StreamResponse(status=200, headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
    await resp.prepare(request)

    async def _do_stream():
        async for chunk in state.zen_client.chat_completion(payload):
            if isinstance(chunk, str):
                try:
                    await resp.write((chunk + "\n").encode("utf-8"))
                except ConnectionResetError:
                    raise
                except Exception:
                    return

    try:
        await state.scheduler.submit(
            lambda: _run_resilient(req_id, state, _do_stream)
        )
    except QueueFullError as e:
        err = json.dumps({"error": {"message": str(e), "type": "server_busy"}},
                         ensure_ascii=False)
        try:
            await resp.write(("data: " + err + "\n\n").encode("utf-8"))
        except Exception:
            pass
    except ConnectionResetError:
        pass
    except ModelNotSupportedError as e:
        err = json.dumps({"error": {"message": str(e), "type": "model_not_supported"}},
                         ensure_ascii=False)
        try:
            await resp.write(("data: " + err + "\n\n").encode("utf-8"))
        except Exception:
            pass
    except ProviderValidationError as e:
        err = json.dumps({"error": {"message": str(e), "type": "invalid_request_error"}},
                         ensure_ascii=False)
        try:
            await resp.write(("data: " + err + "\n\n").encode("utf-8"))
        except Exception:
            pass
    except UpstreamError as e:
        err = json.dumps({"error": {"message": str(e), "type": "upstream_error"}},
                         ensure_ascii=False)
        try:
            await resp.write(("data: " + err + "\n\n").encode("utf-8"))
        except Exception:
            pass
    except Exception as e:
        err = json.dumps({"error": {"message": str(e), "type": "server_error"}},
                         ensure_ascii=False)
        try:
            await resp.write(("data: " + err + "\n\n").encode("utf-8"))
        except Exception:
            pass

    return resp

# ============================================================
# Anthropic 兼容端点
# ============================================================

def _anthropic_convert_messages(
    body: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], Optional[List[Dict[str, Any]]]]:
    system = body.get("system", "")
    if isinstance(system, list):
        system = "\n".join(
            p.get("text", "") for p in system
            if isinstance(p, dict) and p.get("type") == "text"
        )
    elif not isinstance(system, str):
        system = str(system)

    oai_messages: List[Dict[str, Any]] = []
    if system:
        oai_messages.append({"role": "system", "content": system})

    for m in body.get("messages", []):
        role = m.get("role", "user")
        content = m.get("content", "")

        if isinstance(content, str):
            oai_messages.append({"role": role, "content": content})
            continue

        if not isinstance(content, list):
            oai_messages.append({"role": role, "content": str(content)})
            continue

        converted: List[Dict[str, Any]] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            pt = part.get("type", "")

            if pt == "text":
                converted.append({"type": "text", "text": part.get("text", "")})
            elif pt == "image":
                source = part.get("source", {})
                st = source.get("type", "")
                if st == "url":
                    converted.append({
                        "type": "image_url",
                        "image_url": {"url": source.get("url", "")},
                    })
                elif st == "base64":
                    converted.append({
                        "type": "image_url",
                        "image_url": {
                            "url": "data:{};base64,{}".format(
                                source.get("media_type", "image/jpeg"),
                                source.get("data", ""),
                            )
                        },
                    })
            elif pt == "tool_use":
                pass
            elif pt == "tool_result":
                tool_id = part.get("tool_use_id", "")
                tc_content = part.get("content", "")
                if isinstance(tc_content, list):
                    tc_content = "\n".join(
                        p.get("text", "") for p in tc_content
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                oai_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": str(tc_content),
                })
                converted = []
                break

        if converted:
            oai_messages.append({"role": role, "content": converted})

    # ★ 关键改动：在这里归一化 tools（只调用一次）
    oai_tools = normalize_tools(body.get("tools"))
    
    return oai_messages, oai_tools

def _convert_to_anthropic(response: Dict[str, Any]) -> Dict[str, Any]:
    choices = response.get("choices", [])
    if not choices:
        return {
            "id": _msg_id(), "type": "message", "role": "assistant",
            "content": [], "model": response.get("model", ""),
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 0, "output_tokens": 0},
        }

    message = choices[0].get("message", {})
    content_text = message.get("content", "")
    reasoning = message.get("reasoning") or message.get("reasoning_content", "")
    tool_calls = message.get("tool_calls", [])

    anth_content: List[Dict[str, Any]] = []
    if reasoning:
        anth_content.append({"type": "thinking", "thinking": reasoning})
    if content_text:
        anth_content.append({"type": "text", "text": content_text})

    for tc in tool_calls:
        func = tc.get("function", {})
        args = func.get("arguments", "{}")
        if isinstance(args, dict):
            args_json = args
        else:
            try:
                args_json = json.loads(args)
            except json.JSONDecodeError:
                args_json = {}

        tool_id = tc.get("id") or _tool_id()
        if not tool_id.startswith("toolu_"):
            tool_id = "toolu_" + tool_id

        anth_content.append({
            "type": "tool_use",
            "id": tool_id,
            "name": func.get("name", ""),
            "input": args_json,
        })

    if not anth_content:
        anth_content.append({"type": "text", "text": ""})

    usage = response.get("usage", {})
    return {
        "id": response.get("id", _msg_id()),
        "type": "message",
        "role": "assistant",
        "content": anth_content,
        "model": response.get("model", ""),
        "stop_reason": "tool_use" if tool_calls else "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        },
    }

async def anthropic_messages_handler(request: web.Request) -> web.StreamResponse:
    state = get_state()

    if MAX_QUEUE_SIZE > 0 and state.scheduler.pending >= MAX_QUEUE_SIZE:
        return web.Response(
            status=503, text="Server is busy, please try again later.",
            content_type="text/plain",
        )

    body = await _get_json(request)
    if body is None:
        return _error_response(400, "Invalid JSON")
    if not body.get("messages"):
        return _error_response(400, "messages is required")
    if not body.get("model"):
        return _error_response(400, "model is required")

    model = body["model"]
    stream = bool(body.get("stream", False))
    oai_messages, oai_tools = _anthropic_convert_messages(body)

    _log("anthropic_messages: converted_tools={}".format(
        [t["function"]["name"] for t in (oai_tools or [])
         if isinstance(t, dict) and isinstance(t.get("function"), dict)]
    ))

    thinking = False
    t = body.get("thinking")
    if isinstance(t, bool):
        thinking = t
    elif isinstance(t, dict):
        thinking = t.get("type") == "enabled" or bool(t.get("enabled", False))

    payload = build_payload(
        messages=oai_messages,
        model=model,
        stream=stream,
        tools=oai_tools,  # 直接传归一化后的结果，不再二次转换
        temperature=body.get("temperature"),
        top_p=body.get("top_p"),
        max_tokens=body.get("max_tokens", 4096),
        stop=body.get("stop_sequences"),
        tool_choice=body.get("tool_choice"),
        thinking=thinking,
        search=body.get("search", False),
    )

    req_id = _gen_id("req")

    if not stream:
        async def _do_non_stream():
            result = None
            async for chunk in state.zen_client.chat_completion(payload):
                result = chunk
                break
            return result

        try:
            result = await state.scheduler.submit(
                lambda: _run_resilient(req_id, state, _do_non_stream)
            )
            if result is None:
                return _error_response(500, "No response from Zen API")
            return _json_response(_convert_to_anthropic(result))
        except QueueFullError as e:
            return web.Response(status=503, text=str(e), content_type="text/plain")
        except ModelNotSupportedError as e:
            return _error_response(400, str(e), "model_not_supported")
        except ProviderValidationError as e:
            return _error_response(400, str(e), "invalid_request_error")
        except UpstreamError as e:
            return _error_response(502, str(e), "upstream_error")
        except Exception as e:
            return _error_response(500, str(e), "server_error")

    resp = web.StreamResponse(status=200, headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    })
    await resp.prepare(request)
    msg_id = _msg_id()

    async def _do_stream() -> None:
        tool_buf: Dict[int, Dict[str, str]] = {}
        text_started = False
        text_index = 0

        await _sse_write(resp, "message_start", {
            "type": "message_start",
            "message": {
                "id": msg_id, "type": "message", "role": "assistant",
                "content": [], "model": model,
                "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 0, "output_tokens": 0},
            },
        })
        await _sse_write(resp, "ping", {"type": "ping"})

        async for raw_chunk in state.zen_client.chat_completion(payload):
            if not isinstance(raw_chunk, str):
                continue
            for line in raw_chunk.splitlines():
                line = line.strip()
                if not line.startswith("data:"):
                    continue
                data_str = line[5:].strip()
                parsed = parse_sse_line(data_str)
                if parsed is None:
                    continue

                if isinstance(parsed, str):
                    if not text_started:
                        text_started = True
                        await _sse_write(resp, "content_block_start", {
                            "type": "content_block_start",
                            "index": text_index,
                            "content_block": {"type": "text", "text": ""},
                        })
                    await _sse_write(resp, "content_block_delta", {
                        "type": "content_block_delta",
                        "index": text_index,
                        "delta": {"type": "text_delta", "text": parsed},
                    })
                elif isinstance(parsed, dict):
                    if "thinking" in parsed:
                        if not text_started:
                            text_started = True
                            await _sse_write(resp, "content_block_start", {
                                "type": "content_block_start",
                                "index": text_index,
                                "content_block": {"type": "text", "text": ""},
                            })
                        await _sse_write(resp, "content_block_delta", {
                            "type": "content_block_delta",
                            "index": text_index,
                            "delta": {"type": "thinking_delta",
                                      "thinking": parsed["thinking"]},
                        })
                    elif "tool_calls" in parsed:
                        for tc in parsed["tool_calls"]:
                            idx = tc.get("index", 0)
                            if idx not in tool_buf:
                                tool_buf[idx] = {"id": "", "name": "", "arguments": ""}
                            buf = tool_buf[idx]
                            if tc.get("id"):
                                buf["id"] = tc["id"]
                            func = tc.get("function", {})
                            if func.get("name"):
                                buf["name"] = func["name"]
                            if func.get("arguments"):
                                buf["arguments"] += func["arguments"]
                    elif "usage" in parsed:
                        pass

        if text_started:
            await _sse_write(resp, "content_block_stop", {
                "type": "content_block_stop", "index": text_index,
            })

        has_tools = bool(tool_buf)
        for tc_idx in sorted(tool_buf.keys()):
            buf = tool_buf[tc_idx]
            tool_id = buf["id"] or _tool_id()
            if not tool_id.startswith("toolu_"):
                tool_id = "toolu_" + tool_id
            args_str = buf["arguments"] or "{}"
            try:
                json.loads(args_str)
            except json.JSONDecodeError:
                args_str = "{}"
            block_index = text_index + 1 + tc_idx
            await _sse_write(resp, "content_block_start", {
                "type": "content_block_start", "index": block_index,
                "content_block": {"type": "tool_use", "id": tool_id,
                                  "name": buf["name"], "input": {}},
            })
            await _sse_write(resp, "content_block_delta", {
                "type": "content_block_delta", "index": block_index,
                "delta": {"type": "input_json_delta", "partial_json": args_str},
            })
            await _sse_write(resp, "content_block_stop", {
                "type": "content_block_stop", "index": block_index,
            })

        await _sse_write(resp, "message_delta", {
            "type": "message_delta",
            "delta": {"stop_reason": "tool_use" if has_tools else "end_turn",
                      "stop_sequence": None},
            "usage": {"output_tokens": 0},
        })
        await _sse_write(resp, "message_stop", {"type": "message_stop"})

    try:
        await state.scheduler.submit(
            lambda: _run_resilient(req_id, state, _do_stream)
        )
    except QueueFullError as e:
        await _sse_write(resp, "error",
                         {"error": {"message": str(e), "type": "server_busy"}})
    except ConnectionResetError:
        pass
    except ModelNotSupportedError as e:
        await _sse_write(resp, "error",
                         {"error": {"message": str(e), "type": "model_not_supported"}})
    except ProviderValidationError as e:
        await _sse_write(resp, "error",
                         {"error": {"message": str(e), "type": "invalid_request_error"}})
    except UpstreamError as e:
        await _sse_write(resp, "error",
                         {"error": {"message": str(e), "type": "upstream_error"}})
    except Exception as e:
        await _sse_write(resp, "error",
                         {"error": {"message": str(e), "type": "server_error"}})

    return resp

async def anthropic_list_models_handler(request: web.Request) -> web.Response:
    state = get_state()
    models = await state.zen_client.fetch_models()
    now = int(time.time())
    data = [{"type": "model", "id": m, "display_name": m, "created_at": now}
            for m in models]
    return _json_response({
        "type": "list", "data": data, "has_more": False,
        "first_id": data[0]["id"] if data else None,
        "last_id": data[-1]["id"] if data else None,
    })

async def anthropic_retrieve_model_handler(request: web.Request) -> web.Response:
    model_id = request.match_info.get("model_id", "")
    return _json_response({
        "type": "model", "id": model_id,
        "display_name": model_id, "created_at": int(time.time()),
    })

async def anthropic_count_tokens_handler(request: web.Request) -> web.Response:
    body = await _get_json(request)
    if body is None:
        return _error_response(400, "Invalid JSON")
    estimated = 0
    for m in body.get("messages", []):
        content = m.get("content", "")
        if isinstance(content, str):
            estimated += len(content) // 3
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    estimated += len(part["text"]) // 3
    for t in body.get("tools", []):
        estimated += len(json.dumps(t, ensure_ascii=False)) // 3
    return _json_response({"input_tokens": estimated})

# ============================================================
# 管理端点
# ============================================================

async def admin_refresh_models_handler(request: web.Request) -> web.Response:
    state = get_state()
    models = await state.zen_client.fetch_models()
    return _json_response({
        "status": "ok", "models": models,
        "count": len(models), "timestamp": int(time.time()),
    })

async def admin_switch_node_handler(request: web.Request) -> web.Response:
    state = get_state()
    old = state.node_manager.current_description
    new = await state.node_manager.switch_next()
    cancelled = await state.tracker.cancel_all()
    return _json_response({
        "status": "ok", "previous_node": old, "current_node": new,
        "cancelled_requests": cancelled, "timestamp": int(time.time()),
    })

async def capabilities_handler(request: web.Request) -> web.Response:
    return _json_response({
        "platform": "zen", "capabilities": CAPABILITIES,
        "models": DEFAULT_MODELS, "timestamp": int(time.time()),
    })

async def status_handler(request: web.Request) -> web.Response:
    state = get_state()
    models = await state.zen_client.fetch_models()
    return _json_response({
        "status": "running", "platform": "zen",
        "version": SERVER_VERSION,
        "node": {
            "current": state.node_manager.current_description,
            "index": state.node_manager.current_index,
            "pool": ["direct" if p is None else p for p in PROXY_POOL],
            "pool_size": state.node_manager.pool_size,
        },
        "scheduler": {
            "max_concurrent": MAX_CONCURRENT,
            "max_queue": MAX_QUEUE_SIZE,
            "pending": state.scheduler.pending,
            "active_upstream": state.tracker.count,
        },
        "models": {
            "available": models, "count": len(models), "default": DEFAULT_MODELS,
        },
        "fallback": {
            "enabled": FALLBACK_MODEL_ENABLED, "model": FALLBACK_MODEL,
        },
        "capabilities": CAPABILITIES,
        "http_backend": "curl_cffi" if state.zen_client._use_curl else "aiohttp",
        "timestamp": int(time.time()),
    })

async def count_tokens_handler(request: web.Request) -> web.Response:
    body = await _get_json(request)
    if body is None:
        return _error_response(400, "Invalid JSON")
    estimated = 0
    for m in body.get("messages", []):
        content = m.get("content", "")
        if isinstance(content, str):
            estimated += len(content) // 3
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("text"):
                    estimated += len(part["text"]) // 3
    for t in body.get("tools", []):
        estimated += len(json.dumps(t, ensure_ascii=False)) // 3
    return _json_response({"input_tokens": estimated})

# ============================================================
# 函数调用端点（stub）
# ============================================================

_FUNCTION_REGISTRY: Dict[str, Dict[str, Any]] = {}

async def function_call_handler(request: web.Request) -> web.Response:
    body = await _get_json(request)
    if body is None:
        return _error_response(400, "Invalid JSON")
    name = body.get("name", "")
    if name not in _FUNCTION_REGISTRY:
        return _error_response(404, "Function not found: {}".format(name))
    return _json_response({
        "name": name, "arguments": body.get("arguments", {}),
        "output": "Executed {}".format(name),
    })

async def list_functions_handler(request: web.Request) -> web.Response:
    return _json_response({"functions": list(_FUNCTION_REGISTRY.values())})

# ============================================================
# 路由注册
# ============================================================

def setup_routes(app: web.Application) -> None:
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    app.router.add_get("/v1/health", health_handler)

    app.router.add_get("/v1/models", list_models_handler)
    app.router.add_get("/v1/models/{model_id}", get_model_handler)
    app.router.add_post("/v1/chat/completions", chat_completions_handler)
    app.router.add_post("/v1/messages/count_tokens", count_tokens_handler)

    app.router.add_post("/v1/messages", anthropic_messages_handler)
    app.router.add_post("/messages", anthropic_messages_handler)
    app.router.add_get("/anthropic/v1/models", anthropic_list_models_handler)
    app.router.add_get("/anthropic/v1/models/{model_id}", anthropic_retrieve_model_handler)
    app.router.add_post("/anthropic/v1/messages/count_tokens", anthropic_count_tokens_handler)

    app.router.add_post("/v1/function/call", function_call_handler)
    app.router.add_get("/v1/functions", list_functions_handler)

    app.router.add_post("/v1/admin/refresh_models", admin_refresh_models_handler)
    app.router.add_post("/v1/admin/switch_node", admin_switch_node_handler)
    app.router.add_get("/v1/capabilities", capabilities_handler)
    app.router.add_get("/v1/status", status_handler)

# ============================================================
# 启动入口（含端口占用检测）
# ============================================================

def _check_port_in_use(port: int) -> bool:
    """检查端口是否被占用（Windows/Linux 通用）"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("0.0.0.0", port))
        s.close()
        return False
    except OSError:
        return True

def main() -> None:
    # 启动前先检查端口，避免新旧进程冲突
    if _check_port_in_use(PORT):
        _log("=" * 70)
        _log("ERROR: Port {} is already in use!".format(PORT))
        _log("Please kill the old process first:")
        _log("  Windows: netstat -ano | findstr {} → taskkill /PID <PID> /F".format(PORT))
        _log("  Linux:   lsof -ti:{} | xargs kill -9".format(PORT))
        _log("=" * 70)
        sys.exit(1)

    app = web.Application()
    setup_routes(app)
    state = get_state()

    # 超大号版本号横幅，确保你不会看错版本
    banner = """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║               ZEN PLATFORM SERVER                            ║
║           VERSION: {:<42} ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""".format(SERVER_VERSION)
    _log(banner)

    _log("Config:")
    _log("  Port               : {}".format(PORT))
    _log("  Max Concurrent     : {}".format(
        "unlimited" if MAX_CONCURRENT == -1 else MAX_CONCURRENT))
    _log("  Max Queue Size     : {}".format(MAX_QUEUE_SIZE))
    _log("")
    _log("HTTP Backend:")
    _log("  Selected           : {}".format(
        "curl_cffi (impersonate={})".format(IMPERSONATE_PROFILE)
        if state.zen_client._use_curl else "aiohttp"
    ))
    _log("  curl_cffi installed: {}".format(_HAS_CURL_CFFI))
    _log("")
    _log("Node Pool:")
    _log("  Current Node       : {} (index={})".format(
        state.node_manager.current_description,
        state.node_manager.current_index,
    ))
    _log("")
    _log("Endpoints:")
    _log("  POST /v1/chat/completions   (OpenAI)")
    _log("  POST /v1/messages           (Anthropic)")
    _log("  GET  /v1/status")
    _log("=" * 70)

    web.run_app(app, host="0.0.0.0", port=PORT, print=lambda x: None)

if __name__ == "__main__":
    main()
