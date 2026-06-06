from __future__ import annotations

from typing import Dict, List

BASE_URL: str = "https://www.perplexity.ai"
AUTH_ENDPOINT: str = f"{BASE_URL}/api/auth/session"
CHAT_PATH: str = "/rest/sse/perplexity_ask"

CAPS: Dict[str, bool] = {
    "chat": True,
    "thinking": True,
    "search": True,
}
