from __future__ import annotations
"""Re-export all error classes + classify_http_error for backward compatibility."""

from typing import Optional

from src.core.errors.base import ProviderError
from src.core.errors.business import (
    ConfigError,
    NetworkError,
    NoCandidateError,
    NotSupportedError,
    RequestTimeoutError,
    ValidationError,
)
from src.core.errors.platform import (
    AudioError,
    AuthError,
    BatchError,
    ContextLengthError,
    EmbeddingError,
    FileError,
    ImageError,
    LoginError,
    ModelNotFoundError,
    ModerationError,
    PlatformError,
    PoWError,
    QuotaExceededError,
    RateLimitError,
    RerankError,
    ServerError,
    StreamError,
    TokenExpiredError,
    UploadError,
    VideoError,
)

__all__ = [
    "ProviderError",
    "PlatformError",
    "NoCandidateError",
    "AuthError",
    "LoginError",
    "TokenExpiredError",
    "UploadError",
    "PoWError",
    "EmbeddingError",
    "RateLimitError",
    "ModelNotFoundError",
    "ContextLengthError",
    "NetworkError",
    "StreamError",
    "ConfigError",
    "ValidationError",
    "QuotaExceededError",
    "ServerError",
    "RequestTimeoutError",
    "NotSupportedError",
    "ImageError",
    "AudioError",
    "VideoError",
    "RerankError",
    "ModerationError",
    "FileError",
    "BatchError",
    "classify_http_error",
]


def classify_http_error(
    status_code: int,
    message: str,
    original: Optional[Exception] = None,
) -> ProviderError:
    """根据 HTTP 状态码分类错误。

    Args:
        status_code: HTTP 状态码。
        message: 错误信息。
        original: 原始异常。

    Returns:
        对应的错误实例。
    """
    if status_code == 400:
        msg_lower = message.lower()
        context_keywords = (
            "context",
            "token",
            "max_tokens",
            "maximum context",
            "prompt is too long",
            "上下文",
            "超长",
            "超出",
        )
        if any(keyword in msg_lower for keyword in context_keywords):
            return ContextLengthError(message, original=original)
        return ValidationError(message)
    if status_code == 401:
        return AuthError(message, original=original)
    if status_code == 402:
        return QuotaExceededError(message)
    if status_code == 404:
        return ModelNotFoundError(model=message)
    if status_code == 408 or status_code == 504:
        return RequestTimeoutError(message)
    if status_code == 429:
        return RateLimitError(message, original=original)
    if status_code >= 500:
        return ServerError(message, http_status=status_code, original=original)
    return PlatformError(message, original=original, status_code=status_code)
