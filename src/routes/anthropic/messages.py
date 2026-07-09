from __future__ import annotations

"""Anthropic 兼容路由——aiohttp.web 实现"""

import aiohttp.web

from src.routes.anthropic.handlers import (
    count_tokens,
    list_models,
    messages_handler,
    retrieve_model,
)

__all__ = ["setup_routes"]


# ═══════════════════════════════════════════════════════════════════════════
# 路由注册
# ═══════════════════════════════════════════════════════════════════════════


def setup_routes(app: aiohttp.web.Application) -> None:
    """注册所有 Anthropic 兼容路由。

    覆盖路由：
    - POST /v1/messages（带版本前缀）
    - POST /messages（无版本前缀，兼容旧客户端）
    - GET  /anthropic/v1/models（避免与 OpenAI /v1/models 冲突）
    - GET  /anthropic/v1/models/{model_id}
    - POST /v1/messages/count_tokens

    Args:
        app: aiohttp.web.Application 实例。
    """
    # Messages（核心端点，双路径）
    app.router.add_post("/v1/messages", messages_handler)
    app.router.add_post("/messages", messages_handler)

    # Token 计数
    app.router.add_post(
        "/v1/messages/count_tokens", count_tokens
    )

    # Models（使用 Anthropic 专属前缀，避免与 OpenAI /v1/models 冲突）
    app.router.add_get("/anthropic/v1/models", list_models)
    app.router.add_get("/anthropic/v1/models/{model_id}", retrieve_model)
