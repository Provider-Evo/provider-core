"""plugin 模块 — Provider 适配器层。

职责：
    作为 Provider-Evo 项目标准模块，提供 plugin 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


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
            "enabled": True,
        }


def create_plugin() -> WebuiUtilPlugin:
    return WebuiUtilPlugin()
