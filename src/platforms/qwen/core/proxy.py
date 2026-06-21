"""Qwen 平台代理覆盖状态管理。

负责跟踪 "代理强制开启 / 关闭 / 跟随全局" 三态。
本类无 I/O，仅维护一个状态机。
"""

from __future__ import annotations

from typing import Optional


class ProxyState:
    """代理覆盖状态机。

    Attributes:
        override: ``True``=强制开启；``False``=强制关闭；``None``=跟随全局。
    """

    def __init__(self) -> None:
        """初始化为 "跟随全局" 状态。"""
        self.override: Optional[bool] = None

    # ------------------------------------------------------------------ 写
    def set_enabled(self, enabled: bool) -> None:
        """设置代理开关。

        Args:
            enabled: ``True`` 强制使用代理；``False`` 强制不使用。
        """
        if enabled:
            self.override = True
        else:
            self.override = False

    def load(
        self,
        override: Optional[bool],
    ) -> None:
        """从持久化数据恢复状态。

        Args:
            override: 持久化中的 ``override`` 字段。
        """
        self.override = override

    # ------------------------------------------------------------------ 读
    def is_enabled(self) -> bool:
        """返回当前是否处于 "启用代理" 状态。"""
        if self.override is None:
            return False
        return bool(self.override)

    def get_proxy_url(self) -> Optional[str]:
        """如启用代理，返回应传给 ``session.request`` 的 ``proxy``。"""
        if self.override is True:
            from src.core.server import get_proxy_server  # noqa: PLC0415

            return get_proxy_server()
        return None

    def to_dict(self) -> dict:
        """序列化为可 JSON 化的字典。"""
        return {
            "enabled": self.override,
        }
