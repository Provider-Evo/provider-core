from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://www.perplexity.ai"
AUTH_ENDPOINT: str = f"{BASE_URL}/api/auth/session"
CHAT_PATH: str = "/rest/sse/perplexity_ask"

# 模型列表（摘自 provider 描述）
MODELS: List[str] = [
    "auto",
    "turbo",
    "gpt41",
    "gpt5",
    "gpt5_thinking",
    "o3",
    "o3pro",
    "claude2",
    "claude37sonnetthinking",
    "claude40opus",
    "claude40opusthinking",
    "claude41opusthinking",
    "claude45sonnet",
    "claude45sonnetthinking",
    "experimental",
    "grok",
    "grok4",
    "gemini2flash",
    "pplx_pro",
    "pplx_pro_upgraded",
    "pplx_alpha",
    "pplx_beta",
    "comet_max_assistant",
    "o3_research",
    "o3pro_research",
    "claude40sonnet_research",
    "claude40sonnetthinking_research",
    "claude40opus_research",
    "claude40opusthinking_research",
    "o3_labs",
    "o3pro_labs",
    "claude40sonnetthinking_labs",
    "claude40opusthinking_labs",
    "o4mini",
    "o1",
    "gpt4o",
    "gpt45",
    "gpt4",
    "o3mini",
    "claude35haiku",
    "llama_x_large",
    "mistral",
    "claude3opus",
    "gemini",
    "pplx_reasoning",
    "r1",
]

MODEL_ALIASES: Dict[str, str] = {
    "gpt-5": "gpt5",
    "gpt-5-thinking": "gpt5_thinking",
    "r1-1776": "r1",
}


def build_headers(token: str = "", referer: str | None = None, request_id: str | None = None) -> Dict[str, str]:
    headers = {
        "accept": "text/event-stream",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": BASE_URL,
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    }
    if referer:
        headers["referer"] = referer
    if request_id:
        headers["x-request-id"] = request_id
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def build_payload(prompt: str, model: str, *, followup: bool = False, convo: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not model:
        model = "auto"
    if model in MODEL_ALIASES:
        model = MODEL_ALIASES[model]

    convo = convo or {}
    frontend_uid = convo.get("frontend_uid")
    frontend_context_uuid = convo.get("frontend_context_uuid")
    last_backend_uuid = convo.get("last_backend_uuid")
    read_write_token = convo.get("read_write_token")
    thread_url_slug = convo.get("thread_url_slug")

    params: Dict[str, Any] = {
        "attachments": [],
        "language": "en-US",
        "timezone": "America/Los_Angeles",
        "search_focus": "internet",
        "sources": ["web"],
        "search_recency_filter": None,
        "frontend_uuid": frontend_uid,
        "mode": "copilot",
        "model_preference": model,
        "is_related_query": False,
        "is_sponsored": False,
        "frontend_context_uuid": frontend_context_uuid,
        "prompt_source": "user",
        "query_source": "home" if not followup else "followup",
        "followup_source": "link" if followup else None,
        "is_incognito": False,
        "local_search_enabled": False,
        "use_schematized_api": True,
        "send_back_text_in_streaming_api": False,
        "supported_block_use_cases": [
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
        ],
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

    if followup:
        params.update(
            {
                "last_backend_uuid": last_backend_uuid,
                "read_write_token": read_write_token,
                "query_source": "followup",
                "followup_source": "link",
            }
        )

    data = {"params": params, "query_str": prompt}
    if not followup:
        data["params"]["frontend_uid"] = frontend_uid
    return data


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    try:
        obj = json.loads(data_str)
    except json.JSONDecodeError:
        return None

    # usage only
    if obj.get("choices") == [] and obj.get("usage"):
        return {"usage": obj["usage"]}

    if "blocks" in obj:
        # accumulate reasoning/answers via blocks is complex; here只返回纯文本增量
        for block in obj.get("blocks", []):
            diff = block.get("diff_block") or {}
            if diff.get("field") == "markdown_block":
                for patch in diff.get("patches", []):
                    value = patch.get("value")
                    if isinstance(value, dict):
                        value = value.get("answer") or ""
                    if isinstance(value, str) and value:
                        return value
    choices = obj.get("choices") or []
    if choices:
        delta = choices[0].get("delta") or {}
        content = delta.get("content")
        if content:
            return content
    return None
