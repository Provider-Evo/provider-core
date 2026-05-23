from __future__ import annotations

from typing import Optional

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


class ProviderError(Exception):
    """网关基础异常。所有 Provider-V2 异常的根基类。"""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
        status_code: int = 500,
    ) -> None:
        """初始化。

        Args:
            message: 错误描述。
            original: 原始异常（可选）。
            status_code: HTTP 状态码建议值。
        """
        super().__init__(message)
        self.original = original
        self.status_code = status_code


class PlatformError(ProviderError):
    """平台级异常——平台侧返回的错误。"""


class NoCandidateError(ProviderError):
    """无可用候选项——所有候选项均不可用或不存在。"""

    def __init__(self, message: str = "无可用候选项") -> None:
        """初始化。

        Args:
            message: 错误描述。
        """
        super().__init__(message, status_code=503)


class AuthError(PlatformError):
    """认证失败——凭证无效或过期。"""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
    ) -> None:
        """初始化。

        Args:
            message: 错误描述。
            original: 原始异常。
        """
        super().__init__(message, original=original, status_code=401)


class LoginError(AuthError):
    """登录失败——用户名或密码错误，或登录接口异常。"""


class TokenExpiredError(AuthError):
    """Token 过期——需要重新登录或刷新 token。"""


class UploadError(PlatformError):
    """文件上传失败。"""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
    ) -> None:
        """初始化。

        Args:
            message: 错误描述。
            original: 原始异常。
        """
        super().__init__(message, original=original, status_code=502)


class PoWError(PlatformError):
    """PoW 计算失败——工作量证明验证失败。"""


class EmbeddingError(PlatformError):
    """嵌入向量生成失败。"""


class RateLimitError(PlatformError):
    """速率限制——请求频率超过平台限制。"""

    def __init__(
        self,
        message: str = "请求频率超限",
        retry_after: Optional[float] = None,
        original: Optional[Exception] = None,
    ) -> None:
        """初始化。

        Args:
            message: 错误描述。
            retry_after: 建议重试等待秒数。
            original: 原始异常。
        """
        super().__init__(message, original=original, status_code=429)
        self.retry_after = retry_after


class ModelNotFoundError(PlatformError):
    """模型不存在——请求的模型平台不支持。"""

    def __init__(self, model: str) -> None:
        """初始化。

        Args:
            model: 请求的模型名。
        """
        super().__init__(
            "模型不存在: {}".format(model), status_code=404
        )
        self.model = model


class ContextLengthError(PlatformError):
    """上下文长度超限——输入 token 超过模型最大上下文。"""

    def __init__(
        self,
        message: str = "输入超过最大上下文长度",
        original: Optional[Exception] = None,
    ) -> None:
        """初始化。

        Args:
            message: 错误描述。
            original: 原始异常。
        """
        super().__init__(message, original=original, status_code=400)


class NetworkError(ProviderError):
    """网络错误——连接失败、超时等网络层面异常。"""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
    ) -> None:
        """初始化。

        Args:
            message: 错误描述。
            original: 原始异常。
        """
        super().__init__(message, original=original, status_code=502)


class StreamError(PlatformError):
    """流式响应错误——SSE 流中断或格式异常。"""


class ConfigError(ProviderError):
    """配置错误——config.toml 格式错误或缺少必要字段。"""

    def __init__(self, message: str) -> None:
        """初始化。

        Args:
            message: 错误描述。
        """
        super().__init__(message, status_code=500)


class ValidationError(ProviderError):
    """请求验证错误——请求体格式或参数不合法。"""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        """初始化。

        Args:
            message: 错误描述。
            field: 出错的字段名（可选）。
        """
        super().__init__(message, status_code=400)
        self.field = field


class QuotaExceededError(PlatformError):
    """配额耗尽——账号余额不足或月度用量超限。"""

    def __init__(self, message: str = "配额已耗尽") -> None:
        """初始化。

        Args:
            message: 错误描述。
        """
        super().__init__(message, status_code=402)


class ServerError(PlatformError):
    """平台服务器错误——平台侧 5xx 错误。"""

    def __init__(
        self,
        message: str,
        http_status: int = 500,
        original: Optional[Exception] = None,
    ) -> None:
        """初始化。

        Args:
            message: 错误描述。
            http_status: 平台返回的 HTTP 状态码。
            original: 原始异常。
        """
        super().__init__(message, original=original, status_code=502)
        self.http_status = http_status


class RequestTimeoutError(ProviderError):
    """请求超时——平台响应超时。"""

    def __init__(self, message: str = "请求超时") -> None:
        """初始化。

        Args:
            message: 错误描述。
        """
        super().__init__(message, status_code=504)


class NotSupportedError(ProviderError):
    """功能不支持——当前平台或配置不支持请求的功能。"""

    def __init__(self, feature: str) -> None:
        """初始化。

        Args:
            feature: 不支持的功能名。
        """
        super().__init__(
            "{} 功能当前不支持".format(feature), status_code=501
        )
        self.feature = feature


class ImageError(PlatformError):
    """图像处理错误——图像生成、编辑或变体失败。"""


class AudioError(PlatformError):
    """音频处理错误——语音合成、转录或翻译失败。"""


class VideoError(PlatformError):
    """视频处理错误——视频生成失败。"""


class RerankError(PlatformError):
    """重排序错误——文档重排序请求失败。"""


class ModerationError(PlatformError):
    """内容审核错误——审核请求失败。"""


class FileError(PlatformError):
    """文件操作错误——文件上传、下载或管理失败。"""


class BatchError(PlatformError):
    """批处理错误——批量请求创建或处理失败。"""


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
