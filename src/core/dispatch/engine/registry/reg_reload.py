"""单插件热重载逻辑。"""

from __future__ import annotations

from typing import Any, List, Optional

from src.foundation.logger import get_logger

logger = get_logger(__name__)


def _plugin_registry(registry: Any) -> Any:
    """Return the echotools PluginRegistry (Registry wrapper exposes ``._registry``)."""
    inner = getattr(registry, "_registry", None)
    return inner if inner is not None else registry


async def _unregister_old_platform(registry: Any, record_before: Any) -> None:
    if record_before is None or record_before.adapter is None:
        return
    platform_name = (
        record_before.adapter.name if hasattr(record_before.adapter, "name") else ""
    )
    plugins = _plugin_registry(registry)
    old = plugins.get(platform_name)
    if old is None:
        return
    try:
        await old.close()
    except Exception as exc:
        logger.warning("关闭旧平台 [%s] 失败: %s", platform_name, exc)
    plugins._plugins.pop(platform_name, None)


async def _register_reloaded_adapter(
    registry: Any,
    record_after: Any,
    wl: Optional[List[str]],
    bl: Optional[List[str]],
) -> None:
    adapter = record_after.adapter
    name = adapter.name if hasattr(adapter, "name") else ""
    if not name or (wl is not None and name not in wl) or name in (bl or []):
        return
    _plugin_registry(registry).register(adapter)
    logger.info("平台插件已重新注册: %s", name)
    models = (
        list(adapter.supported_models) if hasattr(adapter, "supported_models") else []
    )
    ensure = getattr(registry, "ensure_candidates", None)
    if ensure is None:
        return
    for model in models:
        try:
            await ensure(model, 1)
        except Exception as exc:
            logger.warning("候选项刷新失败 [%s]: %s", name, exc)


async def reload_single_plugin_id(
    registry: Any,
    plugin_id: str,
    session: Any,
    runtime: Any,
    wl: Optional[List[str]],
    bl: Optional[List[str]],
) -> bool:
    record_before = runtime.loaded.get(plugin_id)
    await _unregister_old_platform(registry, record_before)

    ok = await runtime.reload_plugin(plugin_id, session)
    if not ok:
        logger.warning("插件热重载失败 [%s]", plugin_id)
        return False

    record_after = runtime.loaded.get(plugin_id)
    if record_after is not None and record_after.adapter is not None:
        await _register_reloaded_adapter(registry, record_after, wl, bl)
    return True
