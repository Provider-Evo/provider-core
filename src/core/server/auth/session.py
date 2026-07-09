from __future__ import annotations

"""WebUI 会话 cookie 常量与可注入校验器（core 不依赖 webui）。"""

from typing import Callable, Optional

__all__ = [
    "COOKIE_NAME",
    "register_session_verifier",
    "verify_session_token",
]

COOKIE_NAME = "pv2_session"

_verifier: Optional[Callable[[str], bool]] = None


def register_session_verifier(fn: Callable[[str], bool]) -> None:
    """由 bootstrap 在启动时注册 WebUI token 校验函数。"""
    global _verifier
    _verifier = fn


def verify_session_token(cookie_value: str) -> bool:
    """校验会话 cookie 值。"""
    if not cookie_value or _verifier is None:
        return False
    return _verifier(cookie_value)
