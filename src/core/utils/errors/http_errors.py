"""http_errors 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 http_errors 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import re
from typing import Optional

import aiohttp

from src.core.utils.errors import ProviderError, classify_http_error

__all__ = ["classify_client_error", "maybe_classify_exception"]

_HTTP_STATUS_IN_MSG = re.compile(r"HTTP(\d{3})\b", re.IGNORECASE)


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
    if isinstance(exc, aiohttp.ClientConnectorError):
        from src.core.utils.errors.biz import NetworkError

        return NetworkError(f"连接失败: {exc}", original=exc)
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return classify_http_error(status, str(exc), original=exc)
    return exc
