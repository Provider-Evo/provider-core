"""插件运行时组件 API（对照 MaiBot runtime_routes）。"""
from __future__ import annotations

from typing import Any, Dict, List

import aiohttp.web

__all__ = [
    "plugins_runtime_components",
    "plugins_runtime_home_cards",
    "plugins_runtime_hooks",
    "plugins_runtime_hook_specs",
]


def _runtime() -> Any:
    from src.core.server.plugins.runtime import get_plugin_runtime

    return get_plugin_runtime()


async def plugins_runtime_components(request: aiohttp.web.Request) -> aiohttp.web.Response:
    plugin_id = request.match_info.get("plugin_id", "")
    runtime = _runtime()
    components: List[Dict[str, Any]] = runtime.get_components()
    if plugin_id:
        components = [c for c in components if c.get("plugin_id") == plugin_id]
    return aiohttp.web.json_response({"success": True, "components": components})


async def plugins_runtime_home_cards(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    runtime = _runtime()
    cards = runtime.get_components("home_card")
    return aiohttp.web.json_response({"success": True, "cards": cards})


async def plugins_runtime_hooks(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    runtime = _runtime()
    hooks = runtime.get_components("hook")
    registered = []
    try:
        from src.core.server.plugins.hook_registry import get_hook_registry

        registered = get_hook_registry().list_registered()
    except Exception:
        pass
    return aiohttp.web.json_response(
        {"success": True, "hooks": hooks, "registered": registered}
    )


async def plugins_runtime_hook_specs(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    from src.core.server.plugins.hook_registry import HOOK_SPECS

    return aiohttp.web.json_response({"success": True, "specs": HOOK_SPECS})
