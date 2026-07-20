

# src/platforms/nvidia/util.py
"""Nvidia 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.nvidia.core`` 子模块
- ``NvidiaAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any, Dict, List, Optional, Union

from provider_nvidia.core.consts import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    FETCH_MODELS_ENABLED,
    MAX_TOKENS,
    MODEL_FETCH_INTERVAL,
    MODELS,
    RECOVERY_INTERVAL,
)
from provider_nvidia.core.headers import build_headers
from provider_nvidia.core.payload import build_payload
from provider_nvidia.core.helpers.sse import parse_sse_line


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入实现类。"""
    if name in ("NvidiaAdapter", "Adapter"):
        from provider_nvidia.core.acore import (  # noqa: PLC0415
            Adapter as _Adapter,
        )

        return _Adapter
    raise AttributeError(
        "module 'src.platforms.nvidia.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "BASE_URL",
    "CHAT_PATH",
    "MAX_TOKENS",
    "RECOVERY_INTERVAL",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "build_headers",
    "build_payload",
    "parse_sse_line",
    "NvidiaAdapter",
    "Adapter",
]
