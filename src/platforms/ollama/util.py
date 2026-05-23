from __future__ import annotations

"""Ollama 对外工具门面。

该模块只负责对外导出稳定接口，所有实现来自 ``src.platforms.ollama.core.client``。
符合平台适配器依赖方向规范：adapter.py -> util.py -> core/*
"""

from typing import Any, Dict

from src.platforms.ollama.core.client import (
    BASE_URL,
    CHAT_PATH,
    MAX_WORKERS,
    PAGE_SIZE,
    REFRESH_INTERVAL,
    TIMEOUT,
    OllamaClient,
    build_chat_payload,
    build_image_messages,
    build_registry,
    collect_servers,
    detect_capabilities,
    load_cache,
    needs_refresh,
    parse_ollama_line,
    save_cache,
)
from src.platforms.ollama.core.constants import (
    CAPS,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
)


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 Ollama 请求头。

    Ollama 为本地服务，无需认证头。此函数为接口规范兼容保留。

    Args:
        token: 未使用，仅为接口兼容保留。

    Returns:
        标准请求头字典。
    """
    return {"Content-Type": "application/json"}


def build_payload(
    messages: list,
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建 Ollama 聊天请求体（build_chat_payload 的别名）。

    Args:
        messages: Ollama 格式的消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 额外参数。

    Returns:
        请求体字典。
    """
    return build_chat_payload(messages, model, stream, **kw)


def parse_sse_line(data_str: str) -> Any:
    """解析 Ollama 流式响应行（parse_ollama_line 的别名）。

    Ollama 使用逐行 JSON 而非 SSE 格式。

    Args:
        data_str: JSON 字符串行。

    Returns:
        str（文本片段）、dict（usage）或 None（跳过）。
    """
    return parse_ollama_line(data_str.encode("utf-8"))


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 OllamaAdapter。"""
    if name == "OllamaAdapter":
        from src.platforms.ollama.core.adapter_impl import (  # noqa: PLC0415
            OllamaAdapter as _OllamaAdapter,
        )

        return _OllamaAdapter
    if name == "OllamaClient":
        return OllamaClient
    raise AttributeError(
        "module 'src.platforms.ollama.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "OllamaAdapter",
    "OllamaClient",
    "BASE_URL",
    "CHAT_PATH",
    "PAGE_SIZE",
    "TIMEOUT",
    "MAX_WORKERS",
    "REFRESH_INTERVAL",
    "CAPS",
    "MODELS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "build_headers",
    "build_payload",
    "build_chat_payload",
    "build_image_messages",
    "parse_sse_line",
    "parse_ollama_line",
    "detect_capabilities",
    "collect_servers",
    "build_registry",
    "save_cache",
    "load_cache",
    "needs_refresh",
]
