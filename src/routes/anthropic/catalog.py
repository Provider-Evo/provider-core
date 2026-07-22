
import json
from pathlib import Path
from typing import Callable, FrozenSet, Set, Tuple

import aiohttp.web

from src.foundation.logger import get_logger
from src.routes.shared.handler import (
    make_empty_list,
    make_not_found,
    make_not_supported,
)

__all__ = ["register_anthropic_catalog_routes"]

logger = get_logger(__name__)

RouteKey = Tuple[str, str]

_CATALOG_PATH = Path(__file__).resolve().parent / "route_catalog.json"

from src.routes.shared.prefix import ANT_PREFIX, ant_path as _ant

_MANUAL: FrozenSet[RouteKey] = frozenset(
    {
        ("POST", _ant("/v1/messages")),
        ("POST", _ant("/v1/messages/count_tokens")),
        ("GET", _ant("/v1/messages/batches")),
        ("POST", _ant("/v1/messages/batches")),
        ("GET", _ant("/v1/messages/batches/{message_batch_id}")),
        ("POST", _ant("/v1/messages/batches/{message_batch_id}/cancel")),
        ("GET", _ant("/v1/messages/batches/{message_batch_id}/results")),
        ("GET", _ant("/v1/models")),
        ("GET", _ant("/v1/models/{model_id}")),
    }
)


def _normalize_path(path: str) -> str:
    if path.startswith(ANT_PREFIX):
        return path
    return _ant(path)


def _pick_handler(method: str, path: str) -> Callable:
    if path.startswith(f"{ANT_PREFIX}/organizations") or path.startswith(
        f"{ANT_PREFIX}/organization"
    ):
        return make_not_supported("Anthropic Admin API")
    if (
        path.startswith(f"{ANT_PREFIX}/agents")
        or path.startswith(f"{ANT_PREFIX}/sessions")
        or path.startswith(f"{ANT_PREFIX}/environments")
    ):
        return make_not_supported("Anthropic Managed Agents")
    if path.startswith(f"{ANT_PREFIX}/files") or path.startswith(f"{ANT_PREFIX}/skills"):
        return make_not_supported("Anthropic Beta API")
    if path.startswith(f"{ANT_PREFIX}/experimental"):
        return make_not_supported("Anthropic Prompts API")
    if method == "GET" and "{" in path:
        return make_not_found("Resource")
    if method == "GET":
        return make_empty_list()
    return make_not_supported("Anthropic API")


def _register_anthropic_catalog_entry(
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


def register_anthropic_catalog_routes(app: aiohttp.web.Application) -> int:
    """注册 Anthropic 官方端点 catalog 中尚未绑定的路由。"""
    if not _CATALOG_PATH.is_file():
        logger.warning("anthropic route_catalog.json 缺失，跳过 bulk 注册")
        return 0
    routes = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    registered: Set[RouteKey] = set()
    count = 0
    for entry in routes:
        method = str(entry["method"]).upper()
        path = _normalize_path(str(entry["path"]))
        key: RouteKey = (method, path)
        if key in _MANUAL or key in registered:
            continue
        handler = _pick_handler(method, path)
        if not _register_anthropic_catalog_entry(app, method, path, handler):
            continue
        registered.add(key)
        count += 1
    logger.info("Anthropic catalog 批量注册 %d 条端点", count)
    return count
