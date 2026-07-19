"""security 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 security 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.foundation.logger import get_logger
from src.foundation.paths import persist_dir

__all__ = ["TokenManager"]

logger = get_logger(__name__)

_WEBUI_AUTH_FILE = "webui_auth.json"


class TokenManager:
    """类 TokenManager。"""

    """Manages the WebUI access token (webui_token).

    The token is stored in ``persist/webui/webui_auth.json`` and is
    separate from the API keys used for backend model routing.
    """

    def __init__(self) -> None:
        self._auth_dir = persist_dir("webui")
        self._auth_path = self._auth_dir / _WEBUI_AUTH_FILE
        self._token: Optional[str] = None
        self._load_or_create()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def token(self) -> str:
        """中文说明：token。

        Return the current webui_token (always non-empty after init)."""
        assert self._token is not None
        return self._token

    def verify(self, candidate: str) -> bool:
        """中文说明：verify。

        Constant-time compare *candidate* against the stored token."""
        if not candidate or not self._token:
            return False
        return secrets.compare_digest(candidate, self._token)

    def update(self, new_token: str) -> str:
        """中文说明：update。

        Replace the token with *new_token* (min 10 chars). Returns the new token."""
        if len(new_token) < 10:
            raise ValueError("Token must be at least 10 characters")
        self._token = new_token
        self._save()
        return self._token

    def regenerate(self) -> str:
        """中文说明：regenerate。

        Generate a fresh random token and persist it."""
        self._token = secrets.token_hex(32)
        self._save()
        return self._token

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_or_create(self) -> None:
        """Load existing token or create a new one."""
        if self._auth_path.is_file():
            try:
                data: Dict[str, Any] = json.loads(
                    self._auth_path.read_text(encoding="utf-8")
                )
                self._token = data.get("access_token")
                if self._token:
                    return
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning("Failed to load webui auth file: %s", exc)

        # First run — generate
        self._token = secrets.token_hex(32)
        self._save()
        logger.info("Generated new webui_token (first 8 chars): %s…", self._token[:8])

    def _save(self) -> None:
        """Persist the current token to disk."""
        self._auth_dir.mkdir(parents=True, exist_ok=True)
        now = time.strftime("%Y-%m-%dT%H:%M:%S")
        data: Dict[str, Any] = {
            "access_token": self._token,
            "created_at": now,
            "updated_at": now,
        }
        self._auth_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


# Singleton — importable from anywhere
token_manager = TokenManager()
