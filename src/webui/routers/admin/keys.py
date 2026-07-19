"""keys 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 keys 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import aiohttp.web

from src.core.auth.virtual_keys import get_virtual_key_store
from src.foundation.logger import get_logger

__all__ = ["virtual_keys_list", "virtual_keys_create", "virtual_keys_delete"]

logger = get_logger(__name__)


async def virtual_keys_list(_request: aiohttp.web.Request) -> aiohttp.web.Response:
    store = get_virtual_key_store()
    keys = await store.list_keys()
    return aiohttp.web.json_response({"success": True, "keys": keys})


async def virtual_keys_create(request: aiohttp.web.Request) -> aiohttp.web.Response:
    try:
        body = await request.json()
    except Exception:
        body = {}
    name = str(body.get("name") or "").strip()
    quota_total = int(body.get("quota_total") or 0)
    expires_at = float(body.get("expires_at") or 0)
    models = body.get("models") or []
    if not isinstance(models, list):
        models = []
    store = get_virtual_key_store()
    created = await store.create(
        name=name,
        quota_total=quota_total,
        expires_at=expires_at,
        models=[str(m) for m in models if m],
    )
    return aiohttp.web.json_response({"success": True, "key": created})


async def virtual_keys_delete(request: aiohttp.web.Request) -> aiohttp.web.Response:
    key_id = request.match_info.get("key_id", "")
    if not key_id:
        return aiohttp.web.json_response({"error": "key_id required"}, status=400)
    store = get_virtual_key_store()
    ok = await store.delete(key_id)
    if not ok:
        return aiohttp.web.json_response({"error": "not found"}, status=404)
    return aiohttp.web.json_response({"success": True})
