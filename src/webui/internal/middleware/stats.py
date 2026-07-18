"""
stats 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-self.src.webui.internal.middleware.stats
- 文件名：stats.py
- 父包：provider-self/src/webui/internal/middleware

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


import json
import time
import uuid
from typing import Any, Callable, Dict, Tuple

import aiohttp.web

from src.webui.data.services.logs.request_log import request_broker
from src.webui.data.services.stats import get_stats

__all__ = ["stats_middleware", "PARSED_JSON_BODY_KEY"]

PARSED_JSON_BODY_KEY = "_parsed_json_body"

_DEFAULT_API_PREFIXES = (
    "/v1/chat/",
    "/v1/completions",
    "/v1/messages",
    "/v1/models",
    "/v1/embeddings",
)


def _truncate_messages(messages: list) -> list:
    display: list = []
    for msg in messages:
        m = dict(msg)
        content = m.get("content", "")
        if isinstance(content, str) and len(content) > 500:
            m["content"] = content[:500] + "...(truncated)"
        elif isinstance(content, list):
            text = str(content)
            m["content"] = text[:500] + ("...(truncated)" if len(text) > 500 else "")
        display.append(m)
    return display


async def _parse_request_body(
    request: aiohttp.web.Request,
    track_live: bool,
) -> Dict[str, Any]:
    """Parse the JSON request body and build the body_info dict for stats events."""
    try:
        if request.content_type != "application/json":
            return {}
        body = await request.json()
    except Exception:
        return {}

    request[PARSED_JSON_BODY_KEY] = body
    model = body.get("model", "")
    messages = body.get("messages", [])
    return {
        "model": model,
        "messages_count": len(messages),
        "messages": _truncate_messages(messages) if track_live else [],
        "has_tools": bool(body.get("tools")),
        "stream": bool(body.get("stream", False)),
    }


def _extract_response_content(response: aiohttp.web.StreamResponse) -> str:
    """Extract concatenated message content from a non-streaming JSON response body."""
    if not hasattr(response, "body") or not response.body:
        return ""
    try:
        body_bytes = (
            response.body
            if isinstance(response.body, bytes)
            else response.body.encode("utf-8")
        )
        text = body_bytes.decode("utf-8", errors="replace")
        resp_data = json.loads(text)
        content = ""
        for choice in resp_data.get("choices", []):
            msg = choice.get("message", {})
            content += msg.get("content", "")
        return content
    except Exception:
        return ""


def _record_and_emit_end(
    request: aiohttp.web.Request,
    req_id: str,
    start: float,
    status: int,
    platform: str,
    model: str,
) -> None:
    """Record stats and push the request_end event; called from the finally block."""
    stats = get_stats()
    broker = request_broker
    latency_ms = (time.monotonic() - start) * 1000
    stats.record(
        platform=platform,
        model=model,
        status=status,
        latency_ms=latency_ms,
    )
    chunks = request.get("_req_log_chunks", [])
    response_text = "".join(str(chunk) for chunk in chunks)
    broker.push_event({
        "type": "request_end",
        "id": req_id,
        "status": status,
        "latency_ms": round(latency_ms, 1),
        "platform": platform,
        "model": model,
        "response": response_text,
    })


async def _run_handler_and_track(
    request: aiohttp.web.Request,
    handler: Callable,
    body_info: Dict[str, Any],
    state: Dict[str, Any],
) -> aiohttp.web.StreamResponse:
    """执行下游 handler，跟踪状态码/平台并记录响应内容，从 stats_middleware 抽出。"""
    try:
        response = await handler(request)
        state["status"] = response.status
        if hasattr(response, "_platform"):
            state["platform"] = response._platform

        if not body_info.get("stream"):
            content = _extract_response_content(response)
            if content:
                request["_req_log_chunks"].append(content)

        return response
    except aiohttp.web.HTTPException as exc:
        state["status"] = exc.status
        raise
    except Exception:
        state["status"] = 500
        raise


@aiohttp.web.middleware
async def stats_middleware(
    request: aiohttp.web.Request,
    handler: Callable,
) -> aiohttp.web.StreamResponse:
    path = request.path
    if not any(path.startswith(p) for p in _DEFAULT_API_PREFIXES):
        return await handler(request)
    if request.method != "POST":
        return await handler(request)

    broker = request_broker
    start = time.monotonic()
    state: Dict[str, Any] = {"status": 200, "platform": ""}
    req_id = uuid.uuid4().hex[:16]
    track_live = broker.has_listeners

    body_info = await _parse_request_body(request, track_live)
    model = body_info.get("model", "")

    broker.push_event({
        "type": "request_start",
        "id": req_id,
        "ts": time.time(),
        **body_info,
    })

    request["_req_log_id"] = req_id
    request["_req_log_chunks"] = []

    try:
        return await _run_handler_and_track(request, handler, body_info, state)
    finally:
        _record_and_emit_end(request, req_id, start, state["status"], state["platform"], model)

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
