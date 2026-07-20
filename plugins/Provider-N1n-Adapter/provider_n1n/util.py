


from __future__ import annotations

from typing import Any

from .core.consts import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    FETCH_MODELS_ENABLED,
    MODELS,
    MODELS_PATH,
    MODEL_FETCH_INTERVAL,
)
from .core.headers import build_headers
from .core.payload import build_payload
from .core.stream.sse import parse_sse_line

__all__ = [
    "Adapter",
    "N1nAdapter",
    "BASE_URL",
    "CHAT_PATH",
    "MODELS_PATH",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "build_headers",
    "build_payload",
    "parse_sse_line",
]


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 :class:`N1nAdapter`。

    Args:
        name: 待访问的属性名。

    Returns:
        对应的属性对象。

    Raises:
        AttributeError: 当属性名未注册时抛出。
    """
    if name == "N1nAdapter":
        from .core.adapter.adaptercore import (  # noqa: PLC0415
            N1nAdapter as _N1nAdapter,
        )
        return _N1nAdapter
    if name == "Adapter":
        from .core.adapter.adaptercore import (  # noqa: PLC0415
            N1nAdapter as _Adapter,
        )
        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

__all__ = [
]
