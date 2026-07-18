"""Provider Coplan Util 包。"""
from __future__ import annotations

import secrets
from typing import Any, Dict, List

# ── Brand constants (merged from brand.py) ──
BRAND_NAME = "entropy"
BRAND_TITLE = "Entropy"
KEY_PREFIX = "sk-ent-"

_KEY_BODY_BYTES = 76
_KEY_SAMPLE_BODY = secrets.token_urlsafe(_KEY_BODY_BYTES)
KEY_BODY_LENGTH = len(_KEY_SAMPLE_BODY)
KEY_TOTAL_LENGTH = len(KEY_PREFIX) + KEY_BODY_LENGTH


def generate_api_key() -> str:
    """生成 sk-ent-* API 密钥。"""
    return KEY_PREFIX + secrets.token_urlsafe(_KEY_BODY_BYTES)


from provider_coplan_util.stores import StrategyStore, CatalogStore, StrategyMarketStore, UsageStore, UserStore, UserKeyStore
from provider_coplan_util.auth import SessionStore, verify_admin_credentials, resolve_request_model, is_coplan_api_key, resolve_gateway_request, CoplanStandaloneServer
from provider_coplan_util.routing import (
    SPEC_VERSION, ROUTING_STRATEGIES, STRATEGY_PREFIX,
    alias_count, route_count, strategy_public_id,
    active_plans, default_active_plan_id, highest_active_plan_id, resolve_user_active_plan,
    load_strategy_groups, build_public_payload,
    DEFAULT_USER_STRATEGY_TEMPLATE,
    build_strategy_template, compile_strategy_source, spec_to_source_code,
)

__all__ = [
    "BRAND_NAME",
    "BRAND_TITLE",
    "KEY_PREFIX",
    "KEY_BODY_LENGTH",
    "KEY_TOTAL_LENGTH",
    "generate_api_key",
    "StrategyStore",
    "CatalogStore",
    "StrategyMarketStore",
    "UsageStore",
    "UserStore",
    "UserKeyStore",
    "SessionStore",
    "verify_admin_credentials",
    "resolve_request_model",
    "is_coplan_api_key",
    "resolve_gateway_request",
    "SPEC_VERSION",
    "ROUTING_STRATEGIES",
    "STRATEGY_PREFIX",
    "alias_count",
    "route_count",
    "strategy_public_id",
    "active_plans",
    "default_active_plan_id",
    "highest_active_plan_id",
    "resolve_user_active_plan",
    "load_strategy_groups",
    "build_public_payload",
    "DEFAULT_USER_STRATEGY_TEMPLATE",
    "build_strategy_template",
    "compile_strategy_source",
    "spec_to_source_code",
]
