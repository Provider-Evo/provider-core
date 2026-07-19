"""request_context 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 request_context 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

__all__ = ["get_api_token", "set_api_token", "clear_api_token"]

_api_token: ContextVar[Optional[str]] = ContextVar("provider_api_token", default=None)


def get_api_token() -> Optional[str]:
    return _api_token.get()


def set_api_token(token: str) -> None:
    _api_token.set(token)


def clear_api_token() -> None:
    _api_token.set(None)
