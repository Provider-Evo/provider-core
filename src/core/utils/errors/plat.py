"""
platform 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.utils.errors.plat
- 文件名：platform.py
- 父包：provider-core/src/core/utils/errors

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-core/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""

from typing import Optional

from src.core.utils.errors.base import ProviderError

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
        super().__init__("模型不存在: {}".format(model), status_code=404)
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
    """类 ServerError。"""

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


# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
