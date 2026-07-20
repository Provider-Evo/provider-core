

from __future__ import annotations

from typing import Any, Dict

from provider_sdk import ProviderPlugin, Route


class WebuiUtilPlugin(ProviderPlugin):
    async def on_load(self) -> None:
        self.ctx.logger.info("Provider-Webui-Util: theme assets at /static/plugins/provider-webui-util/")

    @Route("/v1/webui/enhance/info", methods=["GET"])
    async def enhance_info(self) -> Dict[str, Any]:
        return {
            "theme": "entropy-refined",
            "css": "/static/plugins/provider-webui-util/enhance.css",
            "js": "/static/plugins/provider-webui-util/enhance.js",
            "enabled": True,
        }


def create_plugin() -> WebuiUtilPlugin:
    return WebuiUtilPlugin()
