"""Cursor 平台常量定义。"""

from __future__ import annotations

# ── 服务端点 ────────────────────────────────────────────────────────────────────
BASE_URL: str = "https://cursor.com"
CHAT_PATH: str = "/api/chat"
MODELS_JS_URL: str = (
    "https://cursor.com/docs-static/_next/static/chunks/"
    "0-csozqjkxrjx.js?dpl=dpl_GQxtQrtiDVrCgdV9XQsYwb7VxPPP"
)

# ── 模型列表 ────────────────────────────────────────────────────────────────────
MODELS: list[str] = [
    "anthropic/claude-sonnet-4",
    "anthropic/claude-sonnet-4-thinking",
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-sonnet-4-6-thinking",
    "anthropic/claude-sonnet-4-6-long",
    "anthropic/claude-sonnet-4-5",
    "anthropic/claude-sonnet-4-5-thinking",
    "anthropic/claude-sonnet-4-5-long",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-opus-4-6-thinking",
    "anthropic/claude-opus-4-5",
    "anthropic/claude-opus-4-5-thinking",
    "anthropic/claude-opus-4-6-fast",
    "anthropic/claude-opus-4-6-fast-thinking",
    "anthropic/claude-haiku-4-5",
    "anthropic/claude-sonnet-4-1m",
    "anthropic/claude-sonnet-4-1m-thinking",
    "google/gemini-3.1-pro",
    "google/gemini-3.1-long",
    "google/gemini-3-pro",
    "google/gemini-3-long",
    "google/gemini-3-flash",
    "google/gemini-3-pro-image-preview",
    "google/gemini-2.5-flash",
    "openai/gpt-5.1",
    "openai/gpt-5-codex",
    "openai/gpt-5-mini",
    "openai/gpt-5-fast",
    "openai/gpt-5.2",
    "openai/gpt-5.2-codex",
    "openai/gpt-5.4",
    "openai/gpt-5.4-fast",
    "openai/gpt-5.4-long",
    "openai/gpt-5.4-mini",
    "openai/gpt-5.4-nano",
    "openai/gpt-5.3-codex",
    "openai/gpt-5.1-codex",
    "openai/gpt-5.1-codex-mini",
    "openai/gpt-5.1-codex-max",
    "xai/grok-4-20",
    "xai/grok-4-20-long",
    "moonshot/kimi-k2.5",
    "cursor/composer-1",
    "cursor/composer-1.5",
    "cursor/composer-2",
    "cursor/composer-2-fast",
]

# ── 能力字典 ────────────────────────────────────────────────────────────────────
CAPS: dict[str, bool] = {
    "chat": True,
    "thinking": True,
    "continuation": True,
}

# ── 模型获取 ────────────────────────────────────────────────────────────────────
FETCH_MODELS_ENABLED: bool = True
MODEL_FETCH_INTERVAL: int = 86400
