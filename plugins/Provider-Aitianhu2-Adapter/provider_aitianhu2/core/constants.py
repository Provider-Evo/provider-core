"""AItianhu2 平台常量定义。

所有字段（BASE_URL / USER_AGENT / BUILD_HASH / ACCOUNT_ID / 超时 / 模型 /
能力）均为静态常量。BASE_URL 等部署端点只在平台代码内维护，不进
``config.toml``（规范详见 ``.agents/provider-guide/references/platform-guide.md``）。
"""

from __future__ import annotations

BASE_URL = "https://www.aitianhu2.top"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)
BUILD_HASH = "prod-9f5aa1f7b48d4577791d0e660bac1111ba132ee6"
ACCOUNT_ID = "dc3721be-2825-46c7-a8b9-d4527db10a43"

# Session hard-expire interval: 24 hours (past this, force re-auth on load)
SESSION_EXPIRY_INTERVAL = 24 * 60 * 60

# Session soft-refresh interval: 22 hours (health-check triggers re-auth
# once the session is older than this, to keep cookies fresh before expiry)
SESSION_REFRESH_INTERVAL = 22 * 60 * 60

# Carids refresh interval: 48 hours (dynamic scrape from landing page)
CARIDS_REFRESH_INTERVAL = 48 * 60 * 60

MODELS = ["gpt-5-5", "gpt-5-5-pro", "gpt-5-5-thinking"]

CAPS = {
    "chat": True,
    "vision": True,
    "image_gen": True,
    "video_gen": False,
    "upload": True,
}
