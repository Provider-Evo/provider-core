"""口令哈希工具（无副作用）。"""

from __future__ import annotations

import hashlib


def hash_password(password: str) -> str:
    """对登录口令做 SHA-256 哈希。

    Args:
        password: 原始口令。

    Returns:
        十六进制哈希字符串。

    Examples:
        >>> hash_password("abc")
        'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()
