"""catalog 模块 — HTTP 入口路由。

职责：
    作为 Provider-Evo 项目标准模块，提供 catalog 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



import json
from pathlib import Path
from typing import Callable, FrozenSet, Set, Tuple

import aiohttp.web

from src.foundation.logger import get_logger
from src.routes.shared.handler import make_empty_list, make_not_found, make_not_supported

__all__ = ["register_anthropic_catalog_routes"]

logger = get_logger(__name__)

RouteKey = Tuple[str, str]

_CATALOG_PATH = Path(__file__).resolve().parent / "route_catalog.json"

_MANUAL: FrozenSet[RouteKey] = frozenset(
    {
        ("POST", "/v1/messages"),
        ("POST", "/messages"),
        ("POST", "/v1/messages/count_tokens"),
        ("GET", "/v1/messages/batches"),
        ("POST", "/v1/messages/batches"),
        ("GET", "/v1/messages/batches/{message_batch_id}"),
        ("POST", "/v1/messages/batches/{message_batch_id}/cancel"),
        ("GET", "/v1/messages/batches/{message_batch_id}/results"),
        ("GET", "/anthropic/v1/models"),
        ("GET", "/anthropic/v1/models/{model_id}"),
    }
)


def _normalize_path(path: str) -> str:
    if not path.startswith("/v1") and not path.startswith("/messages"):
        path = "/v1" + (path if path.startswith("/") else "/" + path)
    elif path.startswith("/messages"):
        path = "/v1" + path
    return path


def _pick_handler(method: str, path: str) -> Callable:
    if path.startswith("/v1/organizations") or path.startswith("/v1/organization"):
        return make_not_supported("Anthropic Admin API")
    if path.startswith("/v1/agents") or path.startswith("/v1/sessions") or path.startswith("/v1/environments"):
        return make_not_supported("Anthropic Managed Agents")
    if path.startswith("/v1/files") or path.startswith("/v1/skills"):
        return make_not_supported("Anthropic Beta API")
    if path.startswith("/v1/experimental"):
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
