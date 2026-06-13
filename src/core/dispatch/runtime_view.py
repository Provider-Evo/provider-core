from __future__ import annotations

"""运行时视图聚合工具。"""

import time
from typing import Any, Dict, List

from src.core.config import get_config

__all__ = [
    "collect_platform_status",
    "collect_model_entries",
    "build_config_summary",
    "build_runtime_summary",
]


async def collect_platform_status(registry: Any) -> Dict[str, Dict[str, Any]]:
    """收集平台状态摘要。

    Args:
        registry: 平台注册表。

    Returns:
        以平台名为键的平台状态字典。
    """
    result: Dict[str, Dict[str, Any]] = {}
    for name, adapter in registry.adapters.items():
        try:
            candidates = await adapter.candidates()
            result[name] = {
                "candidates": len(candidates),
                "available": len(
                    [candidate for candidate in candidates if candidate.available and not candidate.busy]
                ),
                "models": len(adapter.supported_models),
                "context_length": getattr(adapter, "context_length", None),
            }
        except Exception as exc:
            result[name] = {"error": str(exc)}
    return result


async def collect_model_entries(registry: Any) -> List[Dict[str, Any]]:
    """收集模型列表。

    Args:
        registry: 平台注册表。

    Returns:
        模型字典列表。
    """
    return await registry.all_models()


def build_config_summary() -> Dict[str, Any]:
    """构建安全配置摘要。"""
    config = get_config()
    return {
        "server": {
            "version": config.server.version,
            "host": config.server.host,
            "port": config.server.port,
            "debug": config.server.debug,
            "startup_force_kill_port": config.server.startup_force_kill_port,
        },
        "auth": {
            "enabled": config.auth.enabled,
            "keys_count": len(config.auth.keys),
            "group_list_type": config.auth.group_list_type,
            "group_count": len(config.auth.group_list),
        },
        "gateway": {
            "concurrent_enabled": config.gateway.concurrent_enabled,
            "concurrent_count": config.gateway.concurrent_count,
            "min_tokens": config.gateway.min_tokens,
            "group_list_type": config.gateway.group_list_type,
            "group_count": len(config.gateway.group_list),
        },
        "proxy": {
            "proxy_enabled": config.proxy.proxy_enabled,
            "proxy_server": config.proxy.proxy_server,
            "proxy_rules": len(config.proxy.proxy_urls),
        },
        "platforms_proxy": {
            "enabled_platforms": list(config.platforms_proxy.enabled_platforms),
            "group_list_type": config.platforms_proxy.group_list_type,
        },
        "platforms": {
            "list_type": config.platforms_cfg.platform_list_type,
            "count": len(config.platforms_cfg.platform_list),
        },
        "debug": {"level": config.debug.level},
    }


async def build_runtime_summary(registry: Any) -> Dict[str, Any]:
    """构建 WebUI 摘要载荷。

    Args:
        registry: 平台注册表。

    Returns:
        WebUI 所需的只读汇总字典。
    """
    platforms = await collect_platform_status(registry)
    models = await collect_model_entries(registry)
    return {
        "service": "Provider-V2",
        "timestamp": int(time.time()),
        "config": build_config_summary(),
        "platforms": platforms,
        "models": models,
        "capabilities": {
            name: adapter.default_capabilities
            for name, adapter in registry.adapters.items()
        },
        "counts": {
            "platforms": len(platforms),
            "models": len(models),
            "available_platforms": len(
                [name for name, info in platforms.items() if info.get("available", 0) > 0]
            ),
        },
    }
