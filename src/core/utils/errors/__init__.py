from __future__ import annotations
"""Re-export all error classes + classify_http_error + shortcuts for backward compatibility."""

from typing import Optional

from src.core.utils.errors.base import ProviderError
from src.core.utils.errors.biz import (
    ConfigError,
    GatewayAbortedError,
    NetworkError,
    NoCandidateError,
    NotSupportedError,
    RequestTimeoutError,
    ValidationError,
)
from src.core.utils.errors.plat import (
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
from src.core.utils.errors.shcuts import (
    raise_rate_limit,
    raise_auth_failed,
    raise_login_failed,
    raise_token_expired,
    raise_model_not_found,
    raise_server_error,
    raise_network_error,
    raise_no_candidate,
    raise_config_error,
    raise_validation_error,
    raise_platform_error,
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
    "GatewayAbortedError",
    "ImageError",
    "AudioError",
    "VideoError",
    "RerankError",
    "ModerationError",
    "FileError",
    "BatchError",
    "classify_http_error",
    "raise_rate_limit",
    "raise_auth_failed",
    "raise_login_failed",
    "raise_token_expired",
    "raise_model_not_found",
    "raise_server_error",
    "raise_network_error",
    "raise_no_candidate",
    "raise_config_error",
    "raise_validation_error",
    "raise_platform_error",
]


_CONTEXT_LENGTH_KEYWORDS = frozenset({
    # English
    "context_length",
    "context window",
    "maximum context",
    "token limit",
    "max_tokens",
    "prompt is too long",
    "input token",
    "context length",
    "exceed_context",
    "exceeds the available context",
    "available context size",
    "n_prompt_tokens",
    # Chinese
    "上下文",
    "超长",
    "超出",
    "token 超过",
})


def classify_http_error(
    status_code: int,
    message: str,
    original: Optional[Exception] = None,
) -> ProviderError:
    """中文说明：classify_http_error。

Classify an HTTP status code into a typed ProviderError.

Args:
    status_code: HTTP status code.
    message: Error message.
    original: Original exception.

Returns:
    Typed error instance."""
    if status_code == 400:
        msg_lower = message.lower()
        if any(kw in msg_lower for kw in _CONTEXT_LENGTH_KEYWORDS):
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
