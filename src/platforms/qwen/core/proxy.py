"""Qwen 平台代理覆盖状态管理。

负责跟踪 "代理强制开启 / 关闭 / 跟随全局" 三态，以及 "自动启用 24h
后过期" 的时间逻辑。本类无 I/O，仅维护一个状态机。
"""

from __future__ import annotations

import time
from typing import Final, Optional

PROXY_AUTO_EXPIRY: Final[int] = 86400
"""自动启用代理的有效期（秒）。"""


class ProxyState:
    """代理覆盖状态机。

    Attributes:
        override: ``True``=强制开启；``False``=强制关闭；``None``=跟随全局。
        auto_enabled_at: 上次因 WAF 触发自动启用的时间戳；
            ``None`` 表示非自动启用。
    """

    def __init__(self) -> None:
        """初始化为 "跟随全局" 状态。"""
        self.override: Optional[bool] = None
        self.auto_enabled_at: Optional[float] = None

    # ------------------------------------------------------------------ 写
    def set_enabled(self, enabled: bool, *, auto: bool = False) -> None:
        """设置代理开关。

        Args:
            enabled: ``True`` 强制使用代理；``False`` 强制不使用。
            auto: 是否为自动启用（用于 24 小时过期逻辑）。
        """
        if enabled:
            self.override = True
            if auto:
                self.auto_enabled_at = time.time()
        else:
            self.override = False
            self.auto_enabled_at = None

    def load(
        self,
        override: Optional[bool],
        auto_enabled_at: Optional[float],
    ) -> None:
        """从持久化数据恢复状态，并清理过期项。

        Args:
            override: 持久化中的 ``override`` 字段。
            auto_enabled_at: 持久化中的 ``auto_enabled_at`` 字段。
        """
        self.override = override
        if auto_enabled_at is not None:
            self.auto_enabled_at = float(auto_enabled_at)
            self._check_expiry()
        else:
            self.auto_enabled_at = None

    # ------------------------------------------------------------------ 读
    def _check_expiry(self) -> None:
        """检查自动代理是否过期；过期则清除。"""
        if self.auto_enabled_at is None:
            return
        if time.time() - self.auto_enabled_at > PROXY_AUTO_EXPIRY:
            self.override = None
            self.auto_enabled_at = None

    def is_enabled(self) -> bool:
        """返回当前是否处于 "启用代理" 状态。"""
        if self.override is None:
            return False
        if self.override:
            self._check_expiry()
        return bool(self.override)

    def get_proxy_url(self) -> Optional[str]:
        """如启用代理，返回应传给 ``session.request`` 的 ``proxy``。"""
        self._check_expiry()
        if self.override is True:
            from src.core.proxy import get_proxy_server  # noqa: PLC0415

            return get_proxy_server()
        return None

    def to_dict(self) -> dict:
        """序列化为可 JSON 化的字典。"""
        return {
            "enabled": self.override,
            "auto_enabled_at": self.auto_enabled_at,
        }
