
import asyncio
import json
from pathlib import Path
from typing import Any, Optional

from src.core.utils.compat.observability import get_observability_services
from src.foundation.logger import get_logger

__all__ = ["prepare_graceful_restart", "stop_runtime_before_restart"]

logger = get_logger(__name__)

_RUNTIME_STOP_TIMEOUT_S = 3.0


def _save_pre_restart_stats() -> None:
    obs = get_observability_services()
    try:
        obs.save_stats()
    except Exception as exc:
        logger.debug("重启前保存统计失败: %s", exc)
    try:
        obs.save_requests()
    except Exception as exc:
        logger.debug("重启前保存请求日志失败: %s", exc)


async def _broadcast_restart_notice() -> None:
    obs = get_observability_services()
    try:
        await obs.broadcast_log(
            {"type": "system_restarting", "message": "服务正在重启"}
        )
    except Exception as exc:
        logger.debug("重启前广播 WS 失败: %s", exc)


async def _save_terminal_states() -> None:
    obs = get_observability_services()
    try:
        obs.save_terminal_states()
    except Exception as exc:
        logger.debug("重启前保存终端状态失败: %s", exc)


async def _save_plugin_states(registry: Optional[Any]) -> None:
    """保存插件状态到持久化存储。"""
    if registry is None:
        return
    try:
        from src.core.server.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()

        # 保存插件状态
        plugin_states = {}
        for plugin_id, record in runtime._records.items():
            if hasattr(record.plugin, "get_state"):
                plugin_states[plugin_id] = await record.plugin.get_state()

        # 保存到文件
        from src.foundation.paths import persist_dir

        state_path = persist_dir() / "plugin_states.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(plugin_states), encoding="utf-8")
        logger.debug("插件状态已保存: %d 个插件", len(plugin_states))
    except Exception as exc:
        logger.debug("保存插件状态失败: %s", exc)


async def _save_connection_pool_state() -> None:
    """保存连接池状态。"""
    try:
        from src.core.server.lifecycle.net.conn import make_connector

        connector = make_connector()

        # 保存连接池配置
        pool_state = {
            "limit": connector.limit,
            "limit_per_host": connector.limit_per_host,
            "acquired": connector._acquired,
        }

        from src.foundation.paths import persist_dir

        state_path = persist_dir() / "connection_pool_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(pool_state), encoding="utf-8")
        logger.debug("连接池状态已保存")
    except Exception as exc:
        logger.debug("保存连接池状态失败: %s", exc)


async def _save_cache_state() -> None:
    """保存缓存状态。"""
    try:
        from src.core.dispatch.cache.response_cache import get_response_cache

        cache = get_response_cache()

        # 获取缓存统计信息
        cache_stats = cache.stats()

        from src.foundation.paths import persist_dir

        state_path = persist_dir() / "cache_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(cache_stats), encoding="utf-8")
        logger.debug("缓存状态已保存")
    except Exception as exc:
        logger.debug("保存缓存状态失败: %s", exc)


async def prepare_graceful_restart(
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
    *,
    reason: str = "",
) -> None:
    """在触发退出码 42 前持久化状态并通知前端。"""
    logger.info("重启前清理%s", f": {reason}" if reason else "")
    _save_pre_restart_stats()
    await _save_plugin_states(registry)
    await _save_connection_pool_state()
    await _save_cache_state()
    await _broadcast_restart_notice()
    await _save_terminal_states()


async def stop_runtime_before_restart(
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
) -> None:
    """快速重启前停止插件运行时（对齐 Provider-V2，不等待完整 HTTP 关停链）。"""
    del session
    runtime = None
    if registry is not None:
        runtime = getattr(registry, "_external_loader", None)
    if runtime is None:
        try:
            from src.core.server.plugins.runtime import get_plugin_runtime

            runtime = get_plugin_runtime()
        except Exception as exc:
            logger.debug("获取插件运行时失败: %s", exc)
    if runtime is None:
        return
    try:
        await asyncio.wait_for(runtime.close(), timeout=_RUNTIME_STOP_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning(
            "插件运行时关闭超时 (%ss)，继续快速重启", _RUNTIME_STOP_TIMEOUT_S
        )
    except Exception as exc:
        logger.warning("插件运行时关闭失败: %s", exc)
