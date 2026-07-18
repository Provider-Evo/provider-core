"""
base 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-self.src.core.adapters.base
- 文件名：base.py
- 父包：provider-self/src/core/adapters

职责：

    提供运行期凭证占位（API keys / accounts / session cookies 等）。
    真实凭证由 git 仓库外的 accounts.py 或 .env-like override 提供；
    本文件只暴露字段名与默认空值，供 SDK 与插件入口在导入失败时回退。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
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

import importlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.foundation.logger import get_logger

logger = get_logger(__name__)

__all__ = ["BaseAccountAdapter", "AccountBase", "TokenInfo"]


@dataclass
class TokenInfo:
    """统一 Token 信息。"""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        if self.expires_at <= 0:
            return False
        return time.time() >= self.expires_at

    def to_header(self) -> str:
        return f"{self.token_type} {self.access_token}"


@dataclass
class AccountBase:
    """账户基类 — 适配器的 Account dataclass 应继承此类。

    简单适配器（API Key 模式）只需设置 ``api_key`` 字段。
    复杂适配器（cookie/token 模式）可覆盖 ``auth_url`` / ``authenticate``。
    """
    username: str = ""
    password: str = ""
    api_key: str = ""
    token: TokenInfo = field(default_factory=TokenInfo)
    is_active: bool = True
    extra: Dict[str, Any] = field(default_factory=dict)


class BaseAccountAdapter(ABC):
    """适配器基类 — 统一 accounts 加载、token 管理、候选生成。

    子类需实现：
    - ``name``：平台标识
    - ``account_class``：Account dataclass 类（默认 AccountBase）
    - ``candidates_from_accounts``：从 accounts 列表生成候选

    可选覆盖：
    - ``authenticate(account)``：自定义登录逻辑
    - ``refresh_token(account)``：自定义 token 刷新
    - ``api_key_header``：API Key 模式的 header 名（如 ``Authorization``）
    """

    # ── 子类需定义 ──

    @property
    @abstractmethod
    def name(self) -> str:
        """平台标识（如 "deepseek"、"qwen"）。"""

    account_class: type = AccountBase
    """Account dataclass 类。"""

    api_key_header: str = "Authorization"
    """API Key 模式的 header 名。"""

    api_key_prefix: str = "Bearer "
    """API Key 模式的前缀。"""

    # ── 内部状态 ──

    def __init__(self) -> None:
        self._accounts: List[AccountBase] = []

    @property
    def accounts(self) -> List[AccountBase]:
        return self._accounts

    # ── accounts 加载 ──

    def load_accounts_from_module(self, module_path: str) -> None:
        """从 Python 模块加载 accounts 列表。

        兼容两种格式：
        - ``API_KEYS: List[str]`` → 简单 API Key 模式
        - ``ACCOUNTS: List[Account]`` → 复杂 Account 模式
        """
        try:
            mod = importlib.import_module(module_path)
        except ImportError:
            logger.warning("无法导入 accounts 模块: %s", module_path)
            return

        # 优先尝试 ACCOUNTS 列表
        raw_accounts = getattr(mod, "ACCOUNTS", None)
        if raw_accounts and isinstance(raw_accounts, list):
            for item in raw_accounts:
                if isinstance(item, self.account_class):
                    self._accounts.append(item)
                elif isinstance(item, dict):
                    self._accounts.append(self.account_class(**item))
            logger.info(
                "%s: 从 %s 加载 %d 个 accounts",
                self.name, module_path, len(self._accounts),
            )
            return

        # 回退到 API_KEYS 列表
        api_keys = getattr(mod, "API_KEYS", None)
        if api_keys and isinstance(api_keys, list):
            for key in api_keys:
                if isinstance(key, str) and key.strip():
                    self._accounts.append(
                        self.account_class(api_key=key.strip())
                    )
            logger.info(
                "%s: 从 %s 加载 %d 个 API keys",
                self.name, module_path, len(self._accounts),
            )
            return

        logger.debug("%s: 模块 %s 中无 ACCOUNTS 或 API_KEYS", self.name, module_path)

    def load_accounts_from_config(self, config: Dict[str, Any]) -> None:
        """从 config dict 加载 accounts（兼容 ConfigReader 输出）。"""
        api_keys = config.get("api_keys", [])
        if isinstance(api_keys, list):
            for key in api_keys:
                if isinstance(key, str) and key.strip():
                    self._accounts.append(
                        self.account_class(api_key=key.strip())
                    )

    # ── Token 管理 ──

    async def authenticate(self, account: AccountBase) -> TokenInfo:
        """认证账户并返回 TokenInfo。

        简单适配器（API Key）直接返回；复杂适配器需覆盖此方法。
        """
        if account.api_key:
            return TokenInfo(access_token=account.api_key)
        return TokenInfo()

    async def refresh_token(self, account: AccountBase) -> TokenInfo:
        """刷新 Token。默认重新 authenticate。"""
        return await self.authenticate(account)

    async def get_valid_token(self, account: AccountBase) -> TokenInfo:
        """获取有效 Token（过期时自动刷新）。"""
        if account.token.is_expired:
            account.token = await self.refresh_token(account)
        if not account.token.access_token:
            account.token = await self.authenticate(account)
        return account.token

    # ── 候选生成（子类实现） ──

    @abstractmethod
    async def candidates_from_accounts(
        self, accounts: List[AccountBase]
    ) -> List[Any]:
        """从 accounts 列表生成候选（调用方的 Candidate 对象）。"""

    async def candidates(self) -> List[Any]:
        """生成候选（自动过滤非活跃账户）。"""
        active = [a for a in self._accounts if a.is_active]
        return await self.candidates_from_accounts(active)

    # ── API Key 模式辅助 ──

    def api_key_headers(self, account: AccountBase) -> Dict[str, str]:
        """生成 API Key 模式的请求 headers。"""
        token = account.api_key or account.token.access_token
        if not token:
            return {}
        return {self.api_key_header: f"{self.api_key_prefix}{token}"}
