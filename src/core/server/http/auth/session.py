"""session 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 session 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

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
