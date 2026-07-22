# -*- coding: utf-8 -*-
from __future__ import annotations

"""Entropy catalog 路由注册（stub/未实现端点）。"""

import json
from pathlib import Path
from typing import Callable, Set, Tuple

import aiohttp.web

from src.foundation.logger import get_logger
from src.routes.shared.handler import make_not_supported
from src.routes.shared.prefix import ENT_PREFIX

logger = get_logger(__name__)

RouteKey = Tuple[str, str]
_CATALOG_PATH = Path(__file__).resolve().parent / "entropy_catalog.json"

_MANUAL: Set[RouteKey] = {
    ("POST", f"{ENT_PREFIX}/turns"),
    ("POST", f"{ENT_PREFIX}/turns/count-tokens"),
    ("GET", f"{ENT_PREFIX}/models"),
    ("GET", f"{ENT_PREFIX}/models/{{model_id}}"),
    ("GET", f"{ENT_PREFIX}/capabilities"),
}


def register_entropy_catalog_routes(app: aiohttp.web.Application) -> int:
    if not _CATALOG_PATH.is_file():
        logger.warning("entropy_catalog.json 缺失，跳过 bulk 注册")
        return 0
    routes = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
    count = 0
    for entry in routes:
        method = str(entry["method"]).upper()
        path = str(entry["path"])
        key = (method, path)
        if key in _MANUAL:
            continue
        handler = make_not_supported("Entropy API")
        if method == "GET":
            app.router.add_get(path, handler)
        elif method == "POST":
            app.router.add_post(path, handler)
        elif method == "DELETE":
            app.router.add_delete(path, handler)
        else:
            continue
        count += 1
    return count
