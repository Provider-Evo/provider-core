from __future__ import annotations

"""Credential helpers for the standalone MVP chat script."""

import os
import sys
from pathlib import Path
from typing import Tuple

try:
    from ..accounts import ACCOUNTS
except ImportError:
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from accounts import ACCOUNTS


def get_credentials() -> Tuple[str, str]:
    """Return credentials from environment variables or the first account."""
    email = os.environ.get("QWEN_EMAIL", "").strip()
    password = os.environ.get("QWEN_PASSWORD", "").strip()
    if email and password:
        return email, password
    if not ACCOUNTS:
        raise SystemExit("no Qwen accounts configured")
    return ACCOUNTS[0].username, ACCOUNTS[0].password
