"""gTTS 对外工具门面。

该模块只负责对外导出稳定接口：

- 共享常量/函数来自 core/ 下的纯函数模块
- :class:`GttsAdapter` 通过 ``__getattr__`` 延迟加载，避免循环导入
"""

from __future__ import annotations

from typing import Any

from .core.constants import (
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
from .core.payloads import build_payload
from .core.sse import parse_sse_line
from .core.tts import build_tts_params

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
        from .core.adaptercore import (  # noqa: PLC0415
            GttsAdapter as _GttsAdapter,
        )
        return _GttsAdapter
    if name == "Adapter":
        from .core.adaptercore import (  # noqa: PLC0415
            GttsAdapter as _Adapter,
        )
        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
