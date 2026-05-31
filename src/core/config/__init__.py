from __future__ import annotations
import asyncio
from typing import Dict, Optional

from src.core.config.sections import AppConfig
from src.core.config.manager import ConfigManager

__all__ = ["AppConfig", "ConfigManager", "get_config", "reload_config", "start_config_watcher", "write_config"]

_cfg_manager: Optional[ConfigManager] = None


def _get_manager() -> ConfigManager:
    global _cfg_manager
    if _cfg_manager is None:
        _cfg_manager = ConfigManager()
        _cfg_manager.load()
    return _cfg_manager


def get_config() -> AppConfig:
    """获取当前应用配置（延迟初始化配置管理器）。

    Returns:
        AppConfig: 当前加载的完整应用配置。
    """
    return _get_manager().config


async def reload_config() -> AppConfig:
    """重新加载配置文件并返回最新配置。

    Returns:
        AppConfig: 重新加载后的完整应用配置。
    """
    mgr = _get_manager()
    await mgr.reload()
    return mgr.config


async def write_config(data: Dict) -> bool:
    """写入配置数据到文件并重新加载。

    Args:
        data: 完整的配置字典（TOML 兼容格式）。

    Returns:
        bool: 写入是否成功。
    """
    import tomlkit

    mgr = _get_manager()
    if mgr._config_path is None:
        return False

    try:
        # 使用 tomlkit 保留注释
        doc = tomlkit.document()
        for key, value in data.items():
            if isinstance(value, dict):
                table = tomlkit.table()
                for k, v in value.items():
                    try:
                        table[k] = tomlkit.item(v)
                    except (TypeError, ValueError):
                        table[k] = v
                doc[key] = table
            else:
                try:
                    doc[key] = tomlkit.item(value)
                except (TypeError, ValueError):
                    doc[key] = value

        with open(str(mgr._config_path), "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

        # 重新加载
        await mgr.reload()
        return True
    except Exception as exc:
        from src.logger import get_logger
        logger = get_logger(__name__)
        logger.error("配置写入失败: %s", exc, exc_info=True)
        return False


async def start_config_watcher(interval: float = 2.0) -> None:
    """启动配置文件变更监听器（后台轮询）。

    Args:
        interval: 轮询间隔（秒），默认为 2.0。
    """
    mgr = _get_manager()
    await mgr.start_watching()
