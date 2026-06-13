"""配置模块 — 复用 echotools ConfigCenter + 项目 AppConfig。"""
from __future__ import annotations

from typing import Dict, Optional

from src.core.config.sections import AppConfig
from src.core.config.manager import ConfigManager

__all__ = [
    "AppConfig", "ConfigManager",
    "get_config", "reload_config", "start_config_watcher", "write_config",
]

_mgr: Optional[ConfigManager] = None


def _get_manager() -> ConfigManager:
    global _mgr
    if _mgr is None:
        _mgr = ConfigManager()
        _mgr.load()
    return _mgr


def get_config() -> AppConfig:
    return _get_manager().config


async def reload_config() -> AppConfig:
    mgr = _get_manager()
    await mgr.reload()
    return mgr.config


async def write_config(data: Dict) -> bool:
    try:
        from echotools.config.loader import write_toml
        path = _get_manager()._config_path
        if path is None:
            return False
        write_toml(path, data)
        await _get_manager().reload()
        return True
    except Exception as exc:
        from echotools.logger.manager import get_logger
        get_logger(__name__).error("配置写入失败: %s", exc, exc_info=True)
        return False


async def start_config_watcher(interval: float = 2.0) -> None:
    await _get_manager().start_watching()
