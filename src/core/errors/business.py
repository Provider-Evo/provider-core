from __future__ import annotations
"""业务级异常——网关自身的业务逻辑错误。"""

from typing import Optional

from src.core.errors.base import ProviderError

__all__ = [
    "NoCandidateError",
    "NetworkError",
    "ConfigError",
    "ValidationError",
    "RequestTimeoutError",
    "NotSupportedError",
]


class NoCandidateError(ProviderError):
    """无可用候选项——所有候选项均不可用或不存在。"""

    def __init__(self, message: str = "无可用候选项") -> None:
        super().__init__(message, status_code=503)


class NetworkError(ProviderError):
    """网络错误——连接失败、超时等网络层面异常。"""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, original=original, status_code=502)


class ConfigError(ProviderError):
    """配置错误——config.toml 格式错误或缺少必要字段。"""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


class ValidationError(ProviderError):
    """请求验证错误——请求体格式或参数不合法。"""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        super().__init__(message, status_code=400)
        self.field = field


class RequestTimeoutError(ProviderError):
    """请求超时——平台响应超时。"""

    def __init__(self, message: str = "请求超时") -> None:
        super().__init__(message, status_code=504)


class NotSupportedError(ProviderError):
    """功能不支持——当前平台或配置不支持请求的功能。"""

    def __init__(self, feature: str) -> None:
        super().__init__(
            "{} 功能当前不支持".format(feature), status_code=501
        )
        self.feature = feature
