"""Provider-Coplan-Util 插件入口。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import aiohttp.web
from provider_sdk import ProviderPlugin, Route

from provider_coplan_util.brand import BRAND_NAME, BRAND_TITLE, KEY_PREFIX
from provider_coplan_util.store import StrategyStore
from provider_coplan_util.templates import MARKET_TEMPLATES


class CoplanUtilPlugin(ProviderPlugin):
    def __init__(self) -> None:
        self._store: StrategyStore | None = None

    async def on_load(self) -> None:
        data_dir = Path(self.ctx.plugin_dir) / "data"
        self._store = StrategyStore(data_dir)
        self.ctx.logger.info(
            "Provider-Coplan-Util: loaded (brand: %s, key_prefix: %s)",
            BRAND_NAME,
            KEY_PREFIX,
        )

    @Route("/v1/coplan/status", methods=["GET"])
    async def status(self) -> Dict[str, Any]:
        groups = self._store.list_groups() if self._store else []
        return {
            "brand": BRAND_NAME,
            "brand_title": BRAND_TITLE,
            "key_prefix": KEY_PREFIX,
            "strategy_groups": len(groups),
            "market_templates": len(MARKET_TEMPLATES),
        }

    @Route("/v1/coplan/strategy-groups", methods=["GET"])
    async def list_groups(self) -> Dict[str, Any]:
        assert self._store is not None
        return {"groups": self._store.list_groups()}

    @Route("/v1/coplan/strategy-groups", methods=["POST"])
    async def create_group(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert self._store is not None
        try:
            body = await request.json()
        except Exception:
            return aiohttp.web.json_response({"error": "invalid json"}, status=400)
        name = str(body.get("name") or "").strip()
        if not name:
            return aiohttp.web.json_response({"error": "name required"}, status=400)
        group = self._store.create_group(name, str(body.get("description") or ""))
        return aiohttp.web.json_response({"group": group})

    @Route("/v1/coplan/strategy-groups/{group_id}/keys", methods=["POST"])
    async def add_key(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert self._store is not None
        group_id = request.match_info.get("group_id", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        models = body.get("models") if isinstance(body.get("models"), list) else []
        try:
            key_entry = self._store.add_key(group_id, models)
        except KeyError:
            return aiohttp.web.json_response({"error": "group not found"}, status=404)
        return aiohttp.web.json_response({"key": key_entry})

    @Route("/v1/coplan/market/templates", methods=["GET"])
    async def market_templates(self) -> Dict[str, Any]:
        return {"templates": MARKET_TEMPLATES, "brand": BRAND_NAME}

    @Route("/coplan", methods=["GET"])
    async def admin_page(self) -> aiohttp.web.Response:
        html_path = Path(self.ctx.plugin_dir) / "static" / "index.html"
        if not html_path.is_file():
            return aiohttp.web.Response(text="Coplan UI missing", status=404)
        return aiohttp.web.Response(
            text=html_path.read_text(encoding="utf-8"),
            content_type="text/html",
        )


def create_plugin() -> CoplanUtilPlugin:
    return CoplanUtilPlugin()
