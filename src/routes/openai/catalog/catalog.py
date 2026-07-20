
import json
from pathlib import Path
from typing import Callable, Dict, FrozenSet, Set, Tuple

import aiohttp.web

from src.foundation.logger import get_logger
from src.routes.shared.handler import (
    make_empty_list,
    make_not_found,
    make_not_supported,
)

__all__ = ["register_catalog_routes"]

logger = get_logger(__name__)

RouteKey = Tuple[str, str]

_CATALOG_PATH = Path(__file__).resolve().parent / "route_catalog.json"

# 已在 routes.py 显式注册的路由（method, path）
_MANUAL: FrozenSet[RouteKey] = frozenset(
    {
        ("*", "/v1/chat/completions"),
        ("POST", "/v1/chat/completions"),
        ("GET", "/v1/chat/completions"),
        ("POST", "/v1/completions"),
        ("POST", "/v1/responses"),
        ("GET", "/v1/responses/{response_id}"),
        ("DELETE", "/v1/responses/{response_id}"),
        ("POST", "/v1/responses/{response_id}/cancel"),
        ("GET", "/v1/responses/{response_id}/input_items"),
        ("POST", "/v1/responses/compact"),
        ("POST", "/v1/responses/input_tokens"),
        ("POST", "/v1/embeddings"),
        ("POST", "/v1/images/generations"),
        ("POST", "/v1/images/edits"),
        ("POST", "/v1/images/variations"),
        ("POST", "/v1/audio/speech"),
        ("POST", "/v1/audio/transcriptions"),
        ("POST", "/v1/audio/translations"),
        ("POST", "/v1/videos"),
        ("GET", "/v1/videos"),
        ("GET", "/v1/videos/{video_id}"),
        ("DELETE", "/v1/videos/{video_id}"),
        ("GET", "/v1/videos/{video_id}/content"),
        ("POST", "/v1/videos/{video_id}/remix"),
        ("POST", "/v1/videos/characters"),
        ("GET", "/v1/videos/characters/{character_id}"),
        ("POST", "/v1/videos/edits"),
        ("POST", "/v1/videos/extensions"),
        ("POST", "/v1/videos/generations"),
        ("POST", "/v1/moderations"),
        ("POST", "/v1/rerank"),
        ("POST", "/v1/files"),
        ("GET", "/v1/files"),
        ("GET", "/v1/files/{file_id}"),
        ("DELETE", "/v1/files/{file_id}"),
        ("GET", "/v1/files/{file_id}/content"),
        ("POST", "/v1/fine_tuning/jobs"),
        ("GET", "/v1/fine_tuning/jobs"),
        ("GET", "/v1/fine_tuning/jobs/{fine_tuning_job_id}"),
        ("POST", "/v1/fine_tuning/jobs/{fine_tuning_job_id}/cancel"),
        ("GET", "/v1/fine_tuning/jobs/{fine_tuning_job_id}/events"),
        ("POST", "/v1/batches"),
        ("GET", "/v1/batches"),
        ("GET", "/v1/batches/{batch_id}"),
        ("POST", "/v1/batches/{batch_id}/cancel"),
        ("POST", "/v1/assistants"),
        ("GET", "/v1/assistants"),
        ("GET", "/v1/assistants/{assistant_id}"),
        ("POST", "/v1/assistants/{assistant_id}"),
        ("DELETE", "/v1/assistants/{assistant_id}"),
        ("POST", "/v1/threads"),
        ("GET", "/v1/threads/{thread_id}"),
        ("POST", "/v1/threads/{thread_id}"),
        ("DELETE", "/v1/threads/{thread_id}"),
        ("POST", "/v1/threads/{thread_id}/messages"),
        ("GET", "/v1/threads/{thread_id}/messages"),
        ("POST", "/v1/threads/{thread_id}/runs"),
        ("GET", "/v1/threads/{thread_id}/runs"),
        ("GET", "/v1/threads/{thread_id}/runs/{run_id}"),
        ("POST", "/v1/threads/{thread_id}/runs/{run_id}/cancel"),
        ("POST", "/v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs"),
        ("POST", "/v1/vector_stores"),
        ("GET", "/v1/vector_stores"),
        ("GET", "/v1/vector_stores/{vector_store_id}"),
        ("DELETE", "/v1/vector_stores/{vector_store_id}"),
        ("POST", "/v1/vector_stores/{vector_store_id}/files"),
        ("GET", "/v1/vector_stores/{vector_store_id}/files"),
        ("POST", "/v1/uploads"),
        ("POST", "/v1/uploads/{upload_id}/parts"),
        ("POST", "/v1/uploads/{upload_id}/complete"),
        ("POST", "/v1/uploads/{upload_id}/cancel"),
        ("GET", "/v1/models"),
        ("GET", "/v1/models/{model}"),
        ("DELETE", "/v1/models/{model}"),
        ("DELETE", "/v1/chat/completions/{completion_id}"),
        ("POST", "/v1/chat/completions/{completion_id}"),
        ("GET", "/v1/chat/completions/{completion_id}"),
        ("GET", "/v1/chat/completions/{completion_id}/messages"),
    }
)


def _normalize_path(path: str) -> str:
    return (
        path.replace("{fine_tuning_job_id}", "{fine_tuning_job_id}")
        .replace("{job_id}", "{fine_tuning_job_id}")
        .replace("{store_id}", "{vector_store_id}")
    )


def _feature_name(path: str) -> str:
    parts = path.replace("/v1/", "").split("/")
    return parts[0].replace("_", " ").title() if parts else "OpenAI API"


def _pick_handler(method: str, path: str) -> Callable:
    feature = _feature_name(path)
    if path.startswith("/v1/organization") or path.startswith("/v1/projects"):
        return make_not_supported("OpenAI Admin API")
    if path.startswith("/v1/realtime"):
        return make_not_supported("Realtime API")
    if path.startswith("/v1/conversations"):
        return make_not_supported("Conversations API")
    if path.startswith("/v1/containers"):
        return make_not_supported("Containers API")
    if path.startswith("/v1/evals"):
        return make_not_supported("Evals API")
    if path.startswith("/v1/skills"):
        return make_not_supported("Skills API")
    if path.startswith("/v1/chatkit"):
        return make_not_supported("ChatKit API")
    if "/voice_consents" in path or path.endswith("/audio/voices"):
        return make_not_supported("Audio voices")
    if method == "GET" and "{" in path:
        return make_not_found(feature)
    if method == "GET":
        return make_empty_list()
    return make_not_supported(feature)


def _load_catalog() -> list[dict]:
    if not _CATALOG_PATH.is_file():
        logger.warning("route_catalog.json 缺失，跳过 bulk 注册")
        return []
    return json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))


def _register_catalog_entry(
    app: aiohttp.web.Application,
    method: str,
    path: str,
    handler: Callable,
) -> bool:
    if method == "GET":
        app.router.add_get(path, handler)
        return True
    if method == "POST":
        app.router.add_post(path, handler)
        return True
    if method == "DELETE":
        app.router.add_delete(path, handler)
        return True
    if method == "PUT":
        app.router.add_put(path, handler)
        return True
    if method == "PATCH":
        app.router.add_patch(path, handler)
        return True
    return False


def register_catalog_routes(app: aiohttp.web.Application) -> int:
    """注册 catalog 中尚未手动绑定的端点，返回新增数量。"""
    registered: Set[RouteKey] = set()
    count = 0
    for entry in _load_catalog():
        method = str(entry["method"]).upper()
        path = _normalize_path(str(entry["path"]))
        key: RouteKey = (method, path)
        if key in _MANUAL or key in registered:
            continue
        handler = _pick_handler(method, path)
        if not _register_catalog_entry(app, method, path, handler):
            continue
        registered.add(key)
        count += 1
    logger.info("OpenAI catalog 批量注册 %d 条端点", count)
    return count
