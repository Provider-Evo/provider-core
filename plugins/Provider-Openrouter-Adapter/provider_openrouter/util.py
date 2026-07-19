"""util 模块 — Provider 适配器层。

职责：
    提供运行期无关的小工具（路径解析、字符串转换、header 构造等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


# src/platforms/openrouter/util.py
"""OpenRouter 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.openrouter.core`` 子模块
- ``OpenRouterAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any, Dict, List, Optional, Union

from provider_openrouter.core.consts import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    EMBED_PATH,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
    MODELS_PATH,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
)
from provider_openrouter.core.headers import DEFAULT_HEADERS, build_headers
from provider_openrouter.core.payload import build_payload
from provider_openrouter.core.sse import parse_sse_line


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入实现类。"""
    if name in ("OpenRouterAdapter", "Adapter"):
        from provider_openrouter.core.acore import (  # noqa: PLC0415
            OpenRouterAdapter as _OpenRouterAdapter,
        )

        return _OpenRouterAdapter
    raise AttributeError(
        "module 'src.platforms.openrouter.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "OpenRouterAdapter",
    "Adapter",
    "BASE_URL",
    "CHAT_PATH",
    "EMBED_PATH",
    "MODELS_PATH",
    "DEFAULT_HEADERS",
    "RATE_LIMIT_COOLDOWN",
    "RECOVERY_INTERVAL",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "build_headers",
    "build_payload",
    "parse_sse_line",
]
