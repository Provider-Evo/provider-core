from __future__ import annotations

"""HTTP 异常分类辅助 — 将 aiohttp 错误映射为 ProviderError。"""

from typing import Optional

import aiohttp

from src.core.errors import ProviderError, classify_http_error

__all__ = ["classify_client_error", "maybe_classify_exception"]


def classify_client_error(
    status_code: int,
    message: str,
    *,
    original: Optional[Exception] = None,
) -> ProviderError:
    """将 HTTP 状态码分类为类型化 ProviderError。"""
    return classify_http_error(status_code, message, original=original)


def maybe_classify_exception(exc: Exception) -> Exception:
    """若异常携带 HTTP 状态则返回分类后的 ProviderError，否则原样返回。"""
    if isinstance(exc, aiohttp.ClientResponseError):
        return classify_http_error(exc.status, str(exc.message), original=exc)
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return classify_http_error(status, str(exc), original=exc)
    return exc
