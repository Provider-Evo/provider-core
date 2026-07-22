from __future__ import annotations

"""Anthropic 兼容路由包。"""

import aiohttp.web

from src.routes.anthropic.batches import (
    cancel_message_batch,
    create_message_batch,
    list_message_batches,
    retrieve_message_batch,
    retrieve_message_batch_results,
)
from src.routes.anthropic.catalog import register_anthropic_catalog_routes
from src.routes.anthropic.handler import (
    count_tokens,
    list_models,
    messages_handler,
    retrieve_model,
)
from src.routes.shared.prefix import ant_path as _p

__all__ = ["setup_routes"]


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有 Anthropic 兼容路由（/v1/anthropic/*）。"""
    app.router.add_post(_p("/v1/messages"), messages_handler)
    app.router.add_post(_p("/v1/messages/count_tokens"), count_tokens)

    app.router.add_post(_p("/v1/messages/batches"), create_message_batch)
    app.router.add_get(_p("/v1/messages/batches"), list_message_batches)
    app.router.add_get(
        _p("/v1/messages/batches/{message_batch_id}"), retrieve_message_batch
    )
    app.router.add_post(
        _p("/v1/messages/batches/{message_batch_id}/cancel"), cancel_message_batch
    )
    app.router.add_get(
        _p("/v1/messages/batches/{message_batch_id}/results"),
        retrieve_message_batch_results,
    )

    app.router.add_get(_p("/anthropic/v1/models"), list_models)
    app.router.add_get(_p("/anthropic/v1/models/{model_id}"), retrieve_model)

    register_anthropic_catalog_routes(app)
