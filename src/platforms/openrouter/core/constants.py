from __future__ import annotations

from typing import Dict, List

BASE_URL: str = "https://openrouter.ai/api/v1"
CHAT_PATH: str = "/chat/completions"
EMBED_PATH: str = "/embeddings"
MODELS_PATH: str = "/models"

RATE_LIMIT_COOLDOWN: int = 30
RECOVERY_INTERVAL: int = 60

MODELS: List[str] = [
    "qwen/qwen3-235b-a22b:free",
    "qwen/qwen3-30b-a3b:free",
    "deepseek/deepseek-r1-0528:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "deepseek/deepseek-r1:free",
    "google/gemini-2.0-flash-exp:free",
    "google/gemini-2.5-flash-preview:free",
    "google/gemini-2.5-flash-preview-05-20:free",
    "google/gemma-3-27b-it:free",
    "google/gemma-3-12b-it:free",
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "microsoft/phi-4:free",
    "microsoft/phi-4-reasoning:free",
    "qwen/qwen3-14b:free",
    "qwen/qwen3-32b:free",
    "qwen/qwen3-8b:free",
    "qwen/qwen3-4b:free",
    "qwen/qwen3-1.7b:free",
    "qwen/qwen3-0.6b:free",
    "qwen/qwen-2.5-72b-instruct:free",
    "qwen/qwq-32b:free",
    "nvidia/llama-3.1-nemotron-70b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free",
]

CAPS: Dict[str, bool] = {
    "chat": True,
    "vision": True,
    "tools": True,
    "thinking": True,
    "search": True,
    "embedding": True,
}

FETCH_MODELS_ENABLED: bool = True
MODEL_FETCH_INTERVAL: int = 86400
