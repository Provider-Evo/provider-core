
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
