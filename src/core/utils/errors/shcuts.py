"""
shortcuts 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.utils.errors.shcuts
- 文件名：shortcuts.py
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

from __future__ import annotations

from typing import Any, Dict, Optional

from src.core.utils.errors.plat import (
    AuthError,
    LoginError,
    ModelNotFoundError,
    PlatformError,
    RateLimitError,
    ServerError,
    TokenExpiredError,
)
from src.core.utils.errors.biz import (
    ConfigError,
    NetworkError,
    NoCandidateError,
    ValidationError,
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
        message, http_status=http_status, original=original, platform=platform,
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
        message, original=original, status_code=status_code, platform=platform,
    )

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
