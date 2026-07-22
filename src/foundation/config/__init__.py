"""配置模块 — 复用 echotools ConfigCenter + 项目 AppConfig。"""
from __future__ import annotations

from typing import Dict, Optional

from pathlib import Path

from src.foundation.config.manager import ConfigManager
from src.foundation.config.reader import ConfigReader, get_config_reader
from src.foundation.config.secs import AppConfig

__all__ = [
    "AppConfig", "ConfigManager", "ConfigReader",
    "get_config", "get_config_manager", "get_config_reader",
    "reload_config", "start_config_watcher", "write_config",
]

_mgr: Optional[ConfigManager] = None


def _get_manager() -> ConfigManager:
    global _mgr
    if _mgr is None:
        _mgr = ConfigManager()
    if _mgr._config is None:
        _mgr.load()
    return _mgr


def get_config() -> AppConfig:
    return _get_manager().config


def get_config_manager() -> ConfigManager:
    return _get_manager()


async def reload_config() -> AppConfig:
    from src.foundation.config.files import ensure_main_config_file

    mgr = _get_manager()
    path = ensure_main_config_file()
    loaded = Path(str(mgr._center.path)).resolve() if mgr._center.path else None
    if loaded != path.resolve():
        mgr.load(str(path))
        return mgr.config
    await mgr.reload()
    return mgr.config


async def write_config(data: Dict) -> bool:
    try:
        from echotools.config.loader import write_toml

        from src.foundation.config.files import ensure_main_config_file

        path = ensure_main_config_file()
        write_toml(path, data)
        mgr = _get_manager()
        loaded = Path(str(mgr._center.path)).resolve() if mgr._center.path else None
        if loaded != path.resolve():
            mgr.load(str(path))
        else:
            await mgr.reload()
        return True
    except Exception as exc:
        from echotools.logger.manager import get_logger

        get_logger(__name__).error("配置写入失败: %s", exc, exc_info=True)
        return False


async def start_config_watcher(interval: float = 2.0) -> None:
    """已弃用：配置监视由 ``HotReloadService`` 统一负责。"""
    _ = interval
    logger = __import__("echotools.logger.manager", fromlist=["get_logger"]).get_logger(__name__)
    logger.warning("start_config_watcher 已弃用，请使用 HotReloadService")
