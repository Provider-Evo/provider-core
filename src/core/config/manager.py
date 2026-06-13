"""配置管理器 — 复用 echotools ConfigCenter，绑定项目 AppConfig。"""
from __future__ import annotations

from typing import Optional

from echotools.config.center import ConfigCenter
from echotools.logger.manager import get_logger, set_color

from src.core.config.sections import AppConfig

logger = get_logger(__name__)

__all__ = ["ConfigManager"]


class ConfigManager:
    """项目配置管理器，内部复用 echotools ConfigCenter。"""

    def __init__(self) -> None:
        self._center = ConfigCenter()
        self._config: Optional[AppConfig] = None

    def load(self, config_path: Optional[str] = None) -> AppConfig:
        if config_path:
            self._center.load(config_path)
        else:
            self._center.init_from_template(exit_after_create=True, exit_after_merge=True)
        self._config = self._center.bind_proxy(AppConfig)
        set_color(self._config.debug.color)
        # 同步 loguru 日志颜色设置
        try:
            from src.logger import set_color as _loguru_set_color
            _loguru_set_color(self._config.debug.color)
        except Exception:
            pass
        logger.info("配置已加载: %s", self._center.path)
        return self._config

    async def reload(self) -> bool:
        ok = await self._center.reload()
        if ok:
            self._config = self._center.bind_proxy(AppConfig)
            set_color(self._config.debug.color)
            try:
                from src.logger import set_color as _loguru_set_color
                _loguru_set_color(self._config.debug.color)
            except Exception:
                pass
        return ok

    async def start_watching(self) -> None:
        await self._center.watch()

    async def stop_watching(self) -> None:
        await self._center.stop_watch()

    def on_config_change(self, config_path: str, callback) -> None:
        """注册配置变更回调。"""
        self._center.on_change(config_path, callback)

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            raise RuntimeError("配置尚未加载，请先调用 load()")
        return self._config

    @property
    def _config_path(self):
        return self._center.path

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        if self._config is None:
            raise RuntimeError("配置尚未加载，请先调用 load()")
        return getattr(self._config, name)

    def __repr__(self) -> str:
        return repr(self._center)
