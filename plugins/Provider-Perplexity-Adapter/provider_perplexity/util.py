from __future__ import annotations

"""Perplexity 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.perplexity.core`` 子模块
- ``PerplexityAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any

from src.platforms.perplexity.core.constants import (
    AUTH_ENDPOINT,
    BASE_URL,
    CAPS,
    CHAT_PATH,
)
from src.platforms.perplexity.core.headers import build_headers
from src.platforms.perplexity.core.models import MODEL_ALIASES, MODELS
from src.platforms.perplexity.core.payloads import build_payload
from src.platforms.perplexity.core.sse import parse_sse_line


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入实现类。"""
    if name in ("PerplexityAdapter", "Adapter"):
        from src.platforms.perplexity.core.adaptercore import (  # noqa: PLC0415
            PerplexityAdapter as _PerplexityAdapter,
        )

        return _PerplexityAdapter
    raise AttributeError(
        "module 'src.platforms.perplexity.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "PerplexityAdapter",
    "Adapter",
    "BASE_URL",
    "AUTH_ENDPOINT",
    "CHAT_PATH",
    "CAPS",
    "MODELS",
    "MODEL_ALIASES",
    "build_headers",
    "build_payload",
    "parse_sse_line",
]
