
from __future__ import annotations

from typing import Any, Dict, Optional

from src.core.utils.errors.biz import (
    ConfigError,
    NetworkError,
    NoCandidateError,
    ValidationError,
)
from src.core.utils.errors.plat import (
    AuthError,
    LoginError,
    ModelNotFoundError,
    PlatformError,
    RateLimitError,
    ServerError,
    TokenExpiredError,
)

__all__ = [
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


def raise_rate_limit(
    message: str = "Rate limit exceeded",
    *,
    retry_after: Optional[float] = None,
    original: Optional[Exception] = None,
) -> None:
    """抛出速率限制错误（429）。"""
    details: Dict[str, Any] = {}
    if retry_after is not None:
        details["retry_after"] = retry_after
    raise RateLimitError(message, original=original, details=details or None)


def raise_auth_failed(
    message: str = "Authentication failed",
    *,
    platform: str = "",
    original: Optional[Exception] = None,
) -> None:
    """抛出认证失败错误（401）。"""
    raise AuthError(message, original=original, platform=platform)


def raise_login_failed(
    message: str = "Login failed",
    *,
    platform: str = "",
    original: Optional[Exception] = None,
) -> None:
    """抛出登录失败错误。"""
    raise LoginError(message, original=original, platform=platform)


def raise_token_expired(
    message: str = "Token expired",
    *,
    platform: str = "",
    original: Optional[Exception] = None,
) -> None:
    """抛出 Token 过期错误。"""
    raise TokenExpiredError(message, original=original, platform=platform)


def raise_model_not_found(
    model: str = "",
    *,
    message: str = "",
    original: Optional[Exception] = None,
) -> None:
    """抛出模型未找到错误（404）。"""
    msg = message or f"Model not found: {model}" if model else "Model not found"
    raise ModelNotFoundError(msg, model=model, original=original)


def raise_server_error(
    message: str = "Server error",
    *,
    http_status: int = 500,
    platform: str = "",
    original: Optional[Exception] = None,
) -> None:
    """抛出服务端错误（5xx）。"""
    raise ServerError(
        message,
        http_status=http_status,
        original=original,
        platform=platform,
    )


def raise_network_error(
    message: str = "Network error",
    *,
    original: Optional[Exception] = None,
) -> None:
    """抛出网络错误。"""
    raise NetworkError(message, original=original)


def raise_no_candidate(
    message: str = "No available candidate",
    *,
    original: Optional[Exception] = None,
) -> None:
    """抛出无可用候选错误。"""
    raise NoCandidateError(message, original=original)


def raise_config_error(
    message: str = "Configuration error",
    *,
    original: Optional[Exception] = None,
) -> None:
    """抛出配置错误。"""
    raise ConfigError(message, original=original)


def raise_validation_error(
    message: str = "Validation error",
    *,
    original: Optional[Exception] = None,
) -> None:
    """抛出验证错误（400）。"""
    raise ValidationError(message, original=original)


def raise_platform_error(
    message: str = "Platform error",
    *,
    status_code: int = 502,
    platform: str = "",
    original: Optional[Exception] = None,
) -> None:
    """抛出平台通用错误。"""
    raise PlatformError(
        message,
        original=original,
        status_code=status_code,
        platform=platform,
    )
