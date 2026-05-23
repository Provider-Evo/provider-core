import asyncio
from typing import Optional

from src.core.config.sections import AppConfig
from src.core.config.manager import ConfigManager

__all__ = ["AppConfig", "ConfigManager", "get_config", "reload_config", "start_config_watcher"]

_cfg_manager: Optional[ConfigManager] = None


def _get_manager() -> ConfigManager:
    global _cfg_manager
    if _cfg_manager is None:
        _cfg_manager = ConfigManager()
        _cfg_manager.load()
    return _cfg_manager


def get_config() -> AppConfig:
    return _get_manager().config


async def reload_config() -> AppConfig:
    mgr = _get_manager()
    await mgr.reload()
    return mgr.config


async def start_config_watcher(interval: float = 2.0) -> None:
    mgr = _get_manager()
    await mgr.start_watching()
