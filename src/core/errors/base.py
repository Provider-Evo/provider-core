from __future__ import annotations
"""基础异常类：ProviderError。"""

from typing import Optional

__all__ = ["ProviderError"]


class ProviderError(Exception):
    """网关基础异常。所有 Provider-V2 异常的根基类。"""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.original = original
        self.status_code = status_code
