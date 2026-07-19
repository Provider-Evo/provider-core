"""summary 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 summary 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import aiohttp.web

from src.webui.bootstrap.deps import get_registry_from_request
from src.webui.data.services import build_export_payload, build_summary_payload
from src.webui.data.services.export_util import make_json_download_name
from src.webui.data.services.schema.summary_schema import summarize_for_client

__all__ = ["summary_api", "export_summary"]


async def summary_api(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """只读摘要接口。"""
    registry = get_registry_from_request(request)
    if registry is None:
        return aiohttp.web.json_response(
            {"error": {"message": "registry unavailable"}}, status=503
        )
    payload = summarize_for_client(await build_summary_payload(registry))
    return aiohttp.web.json_response(payload)


async def export_summary(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """导出摘要 JSON。"""
    registry = get_registry_from_request(request)
    if registry is None:
        return aiohttp.web.json_response(
            {"error": {"message": "registry unavailable"}}, status=503
        )
    payload = await build_export_payload(registry)
    return aiohttp.web.json_response(
        payload,
        headers={
            "Content-Disposition": 'attachment; filename="{}"'.format(
                make_json_download_name("provider-summary")
            )
        },
    )
