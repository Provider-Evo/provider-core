
from __future__ import annotations

import inspect
from typing import Any, Callable

import aiohttp.web

from src.foundation.logger import get_logger

__all__ = ["register_plugin_routes"]

logger = get_logger(__name__)


def _adapt_handler(handler: Callable[..., Any]) -> Callable[..., Any]:
    """将插件处理器适配为 aiohttp 路由回调。"""

    async def _wrapped(request: aiohttp.web.Request) -> aiohttp.web.StreamResponse:
        kwargs: dict[str, Any] = {}
        if "request" in inspect.signature(handler).parameters:
            kwargs["request"] = request
        result = handler(**kwargs) if kwargs else handler()
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, aiohttp.web.StreamResponse):
            return result
        if isinstance(result, (bytes, bytearray)):
            return aiohttp.web.Response(body=bytes(result))
        if isinstance(result, str):
            return aiohttp.web.Response(text=result, content_type="text/html")
        return aiohttp.web.json_response(result)

    return _wrapped


def register_plugin_routes(app: aiohttp.web.Application) -> None:
    """注册插件 Route 组件与 static/ 目录。"""
    try:
        from src.core.server.plugins.runtime import get_plugin_runtime
    except ImportError:
        return

    runtime = get_plugin_runtime()
    records = getattr(runtime, "loaded", {}) or {}
    if not records:
        return

    for plugin_id, record in records.items():
        plugin = record.plugin
        plugin_dir = record.plugin_dir
        static_dir = plugin_dir / "static"
        if not static_dir.is_dir():
            for candidate in plugin_dir.glob("*/frontend_media"):
                if candidate.is_dir():
                    static_dir = candidate
                    break
        if static_dir.is_dir():
            prefix = f"/static/plugins/{plugin_id.rsplit('.', 1)[-1]}/"
            try:
                app.router.add_static(prefix, path=str(static_dir), show_index=False)
                logger.info("插件静态资源: %s -> %s", prefix, static_dir.name)
            except Exception as exc:
                logger.warning("插件静态资源注册失败 [%s]: %s", plugin_id, exc)

        for comp in record.components:
            if comp.get("type") != "route":
                continue
            meta = comp.get("metadata") or {}
            path = str(meta.get("path") or "").strip()
            if not path:
                continue
            handler_name = str(meta.get("handler_name") or "")
            if not handler_name or not hasattr(plugin, handler_name):
                logger.warning("插件路由处理器缺失 [%s]: %s", plugin_id, handler_name)
                continue
            handler = getattr(plugin, handler_name)
            methods = [m.upper() for m in (meta.get("methods") or ["GET"])]
            for method in methods:
                app.router.add_route(method, path, _adapt_handler(handler))
            logger.debug("插件路由: %s %s [%s]", ",".join(methods), path, plugin_id)
