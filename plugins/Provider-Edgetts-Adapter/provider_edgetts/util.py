"""util 模块 — Provider 适配器层。

职责：
    提供运行期无关的小工具（路径解析、字符串转换、header 构造等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""




from typing import Any

from .core.consts import CAPS, MODELS
from .core.client.drm import build_wss_headers as build_headers
from .core.client.drm import build_ssml as build_ssml
from .core.client.drm import parse_tts_text_frame as parse_sse_line

__all__ = [
    "EdgeTtsAdapter",
    "Adapter",
    "MODELS",
    "CAPS",
    "build_headers",
    "build_ssml",
    "parse_sse_line",
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
        from .core.acore import (  # noqa: PLC0415
            EdgeTtsAdapter as _EdgeTtsAdapter,
        )
        return _EdgeTtsAdapter
    if name == "Adapter":
        from .core.acore import (  # noqa: PLC0415
            EdgeTtsAdapter as _Adapter,
        )

        return _Adapter
    if name == "Account":
        from .core.client.client import Account as _Account  # noqa: PLC0415

        return _Account
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
