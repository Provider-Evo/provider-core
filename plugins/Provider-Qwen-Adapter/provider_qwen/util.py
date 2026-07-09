from __future__ import annotations

"""Qwen 对外工具门面。

该模块只负责对外导出稳定接口：
- 共享常量/函数来自 ``src.platforms.qwen.core.shared``
- ``QwenAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载，避免循环导入
"""

from typing import Any

from src.platforms.qwen.core.shared import (
    CAPS,
    MODELS,
    MODELS_PERSIST_PATH,
    build_headers,
    build_payload,
    parse_sse_event,
    parse_sse_line,
)


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 QwenAdapter。"""
    if name in ("QwenAdapter", "Adapter"):
        from src.platforms.qwen.core.adaptercore import (  # noqa: PLC0415
            QwenAdapter as _QwenAdapter,
        )

        return _QwenAdapter
    raise AttributeError("module 'src.platforms.qwen.util' has no attribute '{}'".format(name))


__all__ = [
    "QwenAdapter",
    "Adapter",
    "MODELS",
    "CAPS",
    "MODELS_PERSIST_PATH",
    "parse_sse_line",
    "parse_sse_event",
    "build_headers",
    "build_payload",
]
