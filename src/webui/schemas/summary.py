from __future__ import annotations

"""WebUI 摘要格式化。"""

from typing import Any, Dict

__all__ = ["summarize_for_client"]


def summarize_for_client(summary: Dict[str, Any]) -> Dict[str, Any]:
    """对摘要进行轻量格式化。"""
    payload = dict(summary)
    payload.setdefault("service", "Provider-V2")
    payload.setdefault("timestamp", 0)
    payload.setdefault("config", {})
    payload.setdefault("platforms", {})
    payload.setdefault("models", [])
    payload.setdefault("capabilities", {})
    payload.setdefault("counts", {})
    return payload
