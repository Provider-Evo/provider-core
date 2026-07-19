"""util 模块 — Provider 适配器层。

职责：
    提供运行期无关的小工具（路径解析、字符串转换、header 构造等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import Any

from provider_perplexity.core.consts import (
    AUTH_ENDPOINT,
    BASE_URL,
    CAPS,
    CHAT_PATH,
)
from provider_perplexity.core.headers import build_headers
from provider_perplexity.core.catalog.models import MODEL_ALIASES, MODELS
from provider_perplexity.core.payload import build_payload
from provider_perplexity.core.stream.sse import parse_sse_line


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入实现类。"""
    if name in ("PerplexityAdapter", "Adapter"):
        from provider_perplexity.core.adapter.acore import (  # noqa: PLC0415
            PerplexityAdapter as _PerplexityAdapter,
        )

        return _PerplexityAdapter
    raise AttributeError(
        "module 'src.platforms.perplexity.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "PerplexityAdapter",
    "Adapter",
    "BASE_URL",
    "AUTH_ENDPOINT",
    "CHAT_PATH",
    "CAPS",
    "MODELS",
    "MODEL_ALIASES",
    "build_headers",
    "build_payload",
    "parse_sse_line",
]
