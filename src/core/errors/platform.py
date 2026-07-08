from __future__ import annotations
"""平台级异常——平台侧返回的错误。"""

from typing import Optional

from src.core.errors.base import ProviderError

__all__ = [
    "PlatformError",
    "AuthError",
    "LoginError",
    "TokenExpiredError",
    "UploadError",
    "PoWError",
    "EmbeddingError",
    "RateLimitError",
    "ModelNotFoundError",
    "ContextLengthError",
    "StreamError",
    "ServerError",
    "ImageError",
    "AudioError",
    "VideoError",
    "RerankError",
    "ModerationError",
    "FileError",
    "BatchError",
    "QuotaExceededError",
]


class PlatformError(ProviderError):
    """平台级异常——平台侧返回的错误。"""


class AuthError(PlatformError):
    """认证失败——凭证无效或过期。"""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
    ) -> None:
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
        super().__init__(message, original=original, status_code=429)
        self.retry_after = retry_after


class ModelNotFoundError(PlatformError):
    """模型不存在——请求的模型平台不支持。"""

    def __init__(self, model: str) -> None:
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
        super().__init__(message, original=original, status_code=400)


class StreamError(PlatformError):
    """流式响应错误——SSE 流中断或格式异常。"""


class ServerError(PlatformError):
    """Platform server error — upstream 5xx error."""

    def __init__(
        self,
        message: str,
        http_status: int = 500,
        original: Optional[Exception] = None,
    ) -> None:
        super().__init__(message, original=original, status_code=http_status)
        self.http_status = http_status


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


class QuotaExceededError(PlatformError):
    """配额耗尽——账号余额不足或月度用量超限。"""

    def __init__(self, message: str = "配额已耗尽") -> None:
        super().__init__(message, status_code=402)
