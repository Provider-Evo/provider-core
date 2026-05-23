from __future__ import annotations

"""Edge TTS 对外门面。

该模块只负责对外导出稳定接口：

- 共享常量/函数来自 core/ 下的纯函数模块
- :class:`EdgeTtsAdapter` 通过 ``__getattr__`` 延迟加载，避免循环导入
"""


from typing import Any

from .core.constants import CAPS, MODELS
from .core.headers import build_headers
from .core.payloads import build_payload
from .core.sse import parse_sse_line
from .core.ssml import build_ssml

__all__ = [
    "EdgeTtsAdapter",
    "MODELS",
    "CAPS",
    "build_headers",
    "build_payload",
    "parse_sse_line",
    "build_ssml",
]


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 :class:`EdgeTtsAdapter`。

    Args:
        name: 待访问的属性名。

    Returns:
        对应的属性对象。

    Raises:
        AttributeError: 当属性名未注册时抛出。
    """
    if name == "EdgeTtsAdapter":
        from .core.impl import (  # noqa: PLC0415
            EdgeTtsAdapter as _EdgeTtsAdapter,
        )
        return _EdgeTtsAdapter
    if name == "Adapter":
        from .core.impl import (  # noqa: PLC0415
            EdgeTtsAdapter as _Adapter,
        )

        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
