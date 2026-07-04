"""Configuration manager — wraps echotools ConfigCenter, binds project AppConfig."""
from __future__ import annotations

from typing import Optional

from echotools.config.center import ConfigCenter
from echotools.logger.manager import get_logger, set_color

from src.core.config.sections import AppConfig

logger = get_logger(__name__)

__all__ = ["ConfigManager"]


class ConfigManager:
    """Project configuration manager, wrapping echotools ConfigCenter."""

    def __init__(self) -> None:
        self._center = ConfigCenter()
        self._config: Optional[AppConfig] = None

    def _apply_color(self) -> None:
        """Apply color settings from config to both echotools and loguru."""
        if self._config is None:
            return
        set_color(self._config.debug.color)
        try:
            from src.logger import set_color as _loguru_set_color
            _loguru_set_color(self._config.debug.color)
        except Exception:
            pass

    def load(self, config_path: Optional[str] = None) -> AppConfig:
        if config_path:
            self._center.load(config_path)
        else:
            # 默认使用 config/main_config.toml
            from src.paths import config_dir
            default_config_path = config_dir() / "main_config.toml"
            if default_config_path.exists():
                self._center.load(str(default_config_path))
            else:
                self._center.init_from_template(exit_after_create=True, exit_after_merge=False)
        self._config = self._center.bind_proxy(AppConfig)
        self._apply_color()
        logger.debug("Config loaded: %s", self._center.path)
        return self._config

    async def reload(self) -> bool:
        ok = await self._center.reload()
        if ok:
            self._config = self._center.bind_proxy(AppConfig)
            self._apply_color()
        return ok

    async def start_watching(self) -> None:
        await self._center.watch()

    async def stop_watching(self) -> None:
        await self._center.stop_watch()

    def on_config_change(self, config_path: str, callback) -> None:
        """Register config change callback."""
        self._center.on_change(config_path, callback)

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            raise RuntimeError("Config not loaded yet, call load() first")
        return self._config

    @property
    def _config_path(self):
        return self._center.path

    def __repr__(self) -> str:
        return repr(self._center)
