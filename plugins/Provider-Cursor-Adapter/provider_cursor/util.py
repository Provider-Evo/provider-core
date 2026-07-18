"""util 模块 — Provider 适配器层。

职责：
    提供运行期无关的小工具（路径解析、字符串转换、header 构造等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

from typing import Any

from .core.constants import (
    BASE_URL,
    CAPS,
    CHAT_PATH,
    FETCH_MODELS_ENABLED,
    MODELS,
    MODELS_JS_URL,
    MODEL_FETCH_INTERVAL,
)
from .core.response.conversation import (
    build_cursor_messages,
    clean_system_prompt,
    derive_conversation_id,
)
from .core.response.extract import (
    extract_balanced_array,
    extract_id_from_subrows,
    parse_top_level_fields,
    split_top_level_objects,
)
from .core.headers import build_headers
from .core.payloads import build_payload
from .core.stream.sse import parse_sse_line

__all__ = [
    "Adapter",
    "CursorAdapter",
    "BASE_URL",
    "CHAT_PATH",
    "MODELS_JS_URL",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "build_headers",
    "build_payload",
    "parse_sse_line",
    "build_cursor_messages",
    "clean_system_prompt",
    "derive_conversation_id",
    "extract_balanced_array",
    "extract_id_from_subrows",
    "parse_top_level_fields",
    "split_top_level_objects",
]


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 :class:`CursorAdapter`。

    Args:
        name: 待访问的属性名。

    Returns:
        对应的属性对象。

    Raises:
        AttributeError: 当属性名未注册时抛出。
    """
    if name == "CursorAdapter":
        from .core.adapter.adaptercore import (  # noqa: PLC0415
            CursorAdapter as _CursorAdapter,
        )
        return _CursorAdapter
    if name == "Adapter":
        from .core.adapter.adaptercore import (  # noqa: PLC0415
            CursorAdapter as _Adapter,
        )
        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
