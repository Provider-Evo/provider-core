# -*- coding: utf-8 -*-
from __future__ import annotations

import aiohttp.web

from src.routes.entropy.models import list_capabilities, list_models, retrieve_model
from src.routes.entropy.turns import count_turn_tokens, create_turn
from src.routes.shared.prefix import ENT_PREFIX

__all__ = ["setup_routes"]


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册 Entropy 主体 /v1/* 路由。"""
    app.router.add_post(f"{ENT_PREFIX}/turns", create_turn)
    app.router.add_post(f"{ENT_PREFIX}/turns/count-tokens", count_turn_tokens)
    app.router.add_get(f"{ENT_PREFIX}/models", list_models)
    app.router.add_get(f"{ENT_PREFIX}/models/{{model_id}}", retrieve_model)
    app.router.add_get(f"{ENT_PREFIX}/capabilities", list_capabilities)

    from src.entropy.catalog.registry import register_entropy_catalog_routes

    register_entropy_catalog_routes(app)
