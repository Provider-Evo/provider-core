


from __future__ import annotations

from typing import Any

from .core.consts import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    DEFAULT_MODEL,
    GTTS_DEFAULT_LANG,
    GTTS_DEFAULT_TLD,
    GTTS_MAX_CHARS,
    GTTS_SLOW,
    MAX_RETRIES,
    MODELS,
    TTS_PATH,
)
from .core.headers import build_headers
from .core.payload import build_payload
from .core.stream.sse import parse_sse_line
from .core.stream.tts import build_tts_params

__all__ = [
    "Adapter",
    "GttsAdapter",
    "BASE_URL",
    "CHAT_PATH",
    "TTS_PATH",
    "DEFAULT_MODEL",
    "GTTS_DEFAULT_LANG",
    "GTTS_DEFAULT_TLD",
    "GTTS_SLOW",
    "GTTS_MAX_CHARS",
    "MAX_RETRIES",
    "MODELS",
    "CAPS",
    "build_headers",
    "build_payload",
    "parse_sse_line",
    "build_tts_params",
]


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 :class:`GttsAdapter`。

    Args:
        name: 待访问的属性名。

    Returns:
        对应的属性对象。

    Raises:
        AttributeError: 当属性名未注册时抛出。
    """
    if name == "GttsAdapter":
        from .core.acore import (  # noqa: PLC0415
            GttsAdapter as _GttsAdapter,
        )
        return _GttsAdapter
    if name == "Adapter":
        from .core.acore import (  # noqa: PLC0415
            GttsAdapter as _Adapter,
        )
        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
