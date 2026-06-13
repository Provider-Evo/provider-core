from __future__ import annotations

from typing import Any, Dict

from .models import MODEL_ALIASES

_SUPPORTED_BLOCK_USE_CASES: list[str] = [
    "answer_modes",
    "media_items",
    "knowledge_cards",
    "inline_entity_cards",
    "place_widgets",
    "finance_widgets",
    "prediction_market_widgets",
    "sports_widgets",
    "flight_status_widgets",
    "news_widgets",
    "shopping_widgets",
    "jobs_widgets",
    "search_result_widgets",
    "inline_images",
    "inline_assets",
    "placeholder_cards",
    "diff_blocks",
    "inline_knowledge_cards",
    "entity_group_v2",
    "refinement_filters",
    "canvas_mode",
    "maps_preview",
    "answer_tabs",
    "price_comparison_widgets",
    "preserve_latex",
    "generic_onboarding_widgets",
    "in_context_suggestions",
    "inline_claims",
]


def _resolve_model(model: str) -> str:
    """Resolve a model name through the alias table.

    Args:
        model: The raw model name from the request.

    Returns:
        The resolved model name.
    """
    if not model:
        return "auto"
    return MODEL_ALIASES.get(model, model)


def _build_base_params(model: str, prompt: str) -> Dict[str, Any]:
    """Build the base params dict for a new (non-followup) query.

    Args:
        model: Resolved model name.
        prompt: User prompt text.

    Returns:
        Base params dictionary.
    """
    return {
        "attachments": [],
        "language": "en-US",
        "timezone": "America/Los_Angeles",
        "search_focus": "internet",
        "sources": ["web"],
        "search_recency_filter": None,
        "frontend_context_uuid": None,
        "mode": "copilot",
        "model_preference": model,
        "is_related_query": False,
        "is_sponsored": False,
        "prompt_source": "user",
        "query_source": "home",
        "followup_source": None,
        "is_incognito": False,
        "local_search_enabled": False,
        "use_schematized_api": True,
        "send_back_text_in_streaming_api": False,
        "supported_block_use_cases": list(_SUPPORTED_BLOCK_USE_CASES),
        "client_coordinates": None,
        "mentions": [],
        "dsl_query": prompt,
        "skip_search_enabled": True,
        "is_nav_suggestions_disabled": False,
        "source": "default",
        "always_search_override": False,
        "override_no_search": False,
        "should_ask_for_mcp_tool_confirmation": True,
        "browser_agent_allow_once_from_toggle": False,
        "force_enable_browser_agent": False,
        "supported_features": ["browser_agent_permission_banner_v1.1"],
        "version": "2.18",
    }


def _apply_convo_context(params: Dict[str, Any], convo: Dict[str, Any]) -> None:
    """Apply conversation context values into the params dict.

    Args:
        params: The params dict to mutate.
        convo: Conversation context dictionary.
    """
    params["frontend_uid"] = convo.get("frontend_uid")
    params["frontend_context_uuid"] = convo.get("frontend_context_uuid")


def _apply_followup(
    params: Dict[str, Any],
    convo: Dict[str, Any],
) -> Dict[str, Any]:
    """Mutate params for a followup query and return the full data payload.

    Args:
        params: The base params dict.
        convo: Conversation context dictionary.

    Returns:
        The full data payload with followup fields.
    """
    params["last_backend_uuid"] = convo.get("last_backend_uuid")
    params["read_write_token"] = convo.get("read_write_token")
    params["query_source"] = "followup"
    params["followup_source"] = "link"
    return {"params": params, "query_str": params.get("dsl_query", "")}


def build_payload(
    prompt: str,
    model: str,
    *,
    followup: bool = False,
    convo: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Build the complete request payload for Perplexity API.

    Args:
        prompt: The user's prompt text.
        model: The model name (may be aliased).
        followup: Whether this is a followup query.
        convo: Optional conversation context dict.

    Returns:
        The full request payload dictionary.
    """
    resolved_model = _resolve_model(model)
    convo = convo or {}

    params = _build_base_params(resolved_model, prompt)
    _apply_convo_context(params, convo)

    if followup:
        return _apply_followup(params, convo)

    data: Dict[str, Any] = {"params": params, "query_str": prompt}
    data["params"]["frontend_uid"] = convo.get("frontend_uid")
    return data
