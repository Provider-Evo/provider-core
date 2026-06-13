"""CodeBuddy 对外工具门面。

该模块只负责对外导出稳定接口：

- 共享常量/函数来自 core/ 下的纯函数模块
- :class:`CodebuddyAdapter` 通过 ``__getattr__`` 延迟加载，避免循环导入
"""

from __future__ import annotations

from typing import Any

from .core.constants import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    FETCH_MODELS_ENABLED,
    IDE_VERSION,
    MODELS,
    MODEL_FETCH_INTERVAL,
)
from .core.headers import build_headers
from .core.payloads import build_payload
from .core.sse import parse_sse_line

__all__ = [
    "Adapter",
    "CodebuddyAdapter",
    "BASE_URL",
    "CHAT_PATH",
    "IDE_VERSION",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "build_headers",
    "build_payload",
    "parse_sse_line",
]


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 :class:`CodebuddyAdapter`。

    Args:
        name: 待访问的属性名。

    Returns:
        对应的属性对象。

    Raises:
        AttributeError: 当属性名未注册时抛出。
    """
    if name == "CodebuddyAdapter":
        from .core.adaptercore import (  # noqa: PLC0415
            CodebuddyAdapter as _CodebuddyAdapter,
        )
        return _CodebuddyAdapter
    if name == "Adapter":
        from .core.adaptercore import (  # noqa: PLC0415
            CodebuddyAdapter as _Adapter,
        )
        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
