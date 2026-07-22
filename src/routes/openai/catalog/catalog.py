
import json
from pathlib import Path
from typing import Callable, Dict, FrozenSet, Set, Tuple

import aiohttp.web

from src.foundation.logger import get_logger
from src.routes.shared.prefix import OAI_PREFIX, oai_path as _p
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
        ("*", _p("/v1/chat/completions")),
        ("POST", _p("/v1/chat/completions")),
        ("GET", _p("/v1/chat/completions")),
        ("POST", _p("/v1/completions")),
        ("POST", _p("/v1/responses")),
        ("GET", _p("/v1/responses/{response_id}")),
        ("DELETE", _p("/v1/responses/{response_id}")),
        ("POST", _p("/v1/responses/{response_id}/cancel")),
        ("GET", _p("/v1/responses/{response_id}/input_items")),
        ("POST", _p("/v1/responses/compact")),
        ("POST", _p("/v1/responses/input_tokens")),
        ("POST", _p("/v1/embeddings")),
        ("POST", _p("/v1/images/generations")),
        ("POST", _p("/v1/images/edits")),
        ("POST", _p("/v1/images/variations")),
        ("POST", _p("/v1/audio/speech")),
        ("POST", _p("/v1/audio/transcriptions")),
        ("POST", _p("/v1/audio/translations")),
        ("POST", _p("/v1/videos")),
        ("GET", _p("/v1/videos")),
        ("GET", _p("/v1/videos/{video_id}")),
        ("DELETE", _p("/v1/videos/{video_id}")),
        ("GET", _p("/v1/videos/{video_id}/content")),
        ("POST", _p("/v1/videos/{video_id}/remix")),
        ("POST", _p("/v1/videos/characters")),
        ("GET", _p("/v1/videos/characters/{character_id}")),
        ("POST", _p("/v1/videos/edits")),
        ("POST", _p("/v1/videos/extensions")),
        ("POST", _p("/v1/videos/generations")),
        ("POST", _p("/v1/moderations")),
        ("POST", _p("/v1/rerank")),
        ("POST", _p("/v1/files")),
        ("GET", _p("/v1/files")),
        ("GET", _p("/v1/files/{file_id}")),
        ("DELETE", _p("/v1/files/{file_id}")),
        ("GET", _p("/v1/files/{file_id}/content")),
        ("POST", _p("/v1/fine_tuning/jobs")),
        ("GET", _p("/v1/fine_tuning/jobs")),
        ("GET", _p("/v1/fine_tuning/jobs/{fine_tuning_job_id}")),
        ("POST", _p("/v1/fine_tuning/jobs/{fine_tuning_job_id}/cancel")),
        ("GET", _p("/v1/fine_tuning/jobs/{fine_tuning_job_id}/events")),
        ("POST", _p("/v1/batches")),
        ("GET", _p("/v1/batches")),
        ("GET", _p("/v1/batches/{batch_id}")),
        ("POST", _p("/v1/batches/{batch_id}/cancel")),
        ("POST", _p("/v1/assistants")),
        ("GET", _p("/v1/assistants")),
        ("GET", _p("/v1/assistants/{assistant_id}")),
        ("POST", _p("/v1/assistants/{assistant_id}")),
        ("DELETE", _p("/v1/assistants/{assistant_id}")),
        ("POST", _p("/v1/threads")),
        ("GET", _p("/v1/threads/{thread_id}")),
        ("POST", _p("/v1/threads/{thread_id}")),
        ("DELETE", _p("/v1/threads/{thread_id}")),
        ("POST", _p("/v1/threads/{thread_id}/messages")),
        ("GET", _p("/v1/threads/{thread_id}/messages")),
        ("POST", _p("/v1/threads/{thread_id}/runs")),
        ("GET", _p("/v1/threads/{thread_id}/runs")),
        ("GET", _p("/v1/threads/{thread_id}/runs/{run_id}")),
        ("POST", _p("/v1/threads/{thread_id}/runs/{run_id}/cancel")),
        ("POST", _p("/v1/threads/{thread_id}/runs/{run_id}/submit_tool_outputs")),
        ("POST", _p("/v1/vector_stores")),
        ("GET", _p("/v1/vector_stores")),
        ("GET", _p("/v1/vector_stores/{vector_store_id}")),
        ("DELETE", _p("/v1/vector_stores/{vector_store_id}")),
        ("POST", _p("/v1/vector_stores/{vector_store_id}/files")),
        ("GET", _p("/v1/vector_stores/{vector_store_id}/files")),
        ("POST", _p("/v1/uploads")),
        ("POST", _p("/v1/uploads/{upload_id}/parts")),
        ("POST", _p("/v1/uploads/{upload_id}/complete")),
        ("POST", _p("/v1/uploads/{upload_id}/cancel")),
        ("GET", _p("/v1/models")),
        ("GET", _p("/v1/models/{model}")),
        ("DELETE", _p("/v1/models/{model}")),
        ("DELETE", _p("/v1/chat/completions/{completion_id}")),
        ("POST", _p("/v1/chat/completions/{completion_id}")),
        ("GET", _p("/v1/chat/completions/{completion_id}")),
        ("GET", _p("/v1/chat/completions/{completion_id}/messages")),
    }
)


def _normalize_path(path: str) -> str:
    if path.startswith(f"{OAI_PREFIX}/"):
        p = path
    elif path.startswith("/v1/"):
        p = _p(path)
    else:
        p = path
    return (
        p.replace("{job_id}", "{fine_tuning_job_id}")
        .replace("{store_id}", "{vector_store_id}")
    )


def _feature_name(path: str) -> str:
    parts = path.replace(f"{OAI_PREFIX}/", "").replace("/v1/", "").split("/")
    return parts[0].replace("_", " ").title() if parts else "OpenAI API"


def _pick_handler(method: str, path: str) -> Callable:
    feature = _feature_name(path)
    if path.startswith(f"{OAI_PREFIX}/organization") or path.startswith(f"{OAI_PREFIX}/projects"):
        return make_not_supported("OpenAI Admin API")
    if path.startswith(f"{OAI_PREFIX}/realtime"):
        return make_not_supported("Realtime API")
    if path.startswith(f"{OAI_PREFIX}/conversations"):
        return make_not_supported("Conversations API")
    if path.startswith(f"{OAI_PREFIX}/containers"):
        return make_not_supported("Containers API")
    if path.startswith(f"{OAI_PREFIX}/evals"):
        return make_not_supported("Evals API")
    if path.startswith(f"{OAI_PREFIX}/skills"):
        return make_not_supported("Skills API")
    if path.startswith(f"{OAI_PREFIX}/chatkit"):
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
