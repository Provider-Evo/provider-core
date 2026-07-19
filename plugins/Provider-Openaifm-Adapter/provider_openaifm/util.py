"""util 模块 — Provider 适配器层。

职责：
    提供运行期无关的小工具（路径解析、字符串转换、header 构造等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""




from typing import Any

from .core.consts import (
    CAPS,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    MODELS,
    STYLES,
    STYLE_PROMPTS,
    VOICES,
)
from .core.headers import build_headers
from .core.tts import build_tts_form_data

__all__ = [
    "OpenaiFmAdapter",
    "Adapter",
    "MODELS",
    "CAPS",
    "VOICES",
    "STYLES",
    "DEFAULT_VOICE",
    "DEFAULT_STYLE",
    "STYLE_PROMPTS",
    "build_headers",
    "build_tts_form_data",
]


def __getattr__(name: str) -> Any:
    """Lazy-load :class:`OpenaiFmAdapter` on first access.

    Args:
        name: Attribute name being accessed.

    Returns:
        The requested attribute.

    Raises:
        AttributeError: If the name is not recognized.
    """
    if name == "OpenaiFmAdapter":
        from .core.acore import (  # noqa: PLC0415
            OpenaiFmAdapter as _OpenaiFmAdapter,
        )

        return _OpenaiFmAdapter
    if name == "Adapter":
        from .core.acore import (  # noqa: PLC0415
            OpenaiFmAdapter as _Adapter,
        )

        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
