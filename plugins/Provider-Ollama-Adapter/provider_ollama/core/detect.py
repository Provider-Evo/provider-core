from __future__ import annotations

"""Ollama 模型能力检测。"""

import re
from typing import Any, Dict, Optional


def extract_context_length(detail: Optional[Dict[str, Any]]) -> Optional[int]:
    """从 /api/show 响应解析上下文长度（num_ctx）。"""
    if not detail:
        return None
    model_info = detail.get("model_info") or {}
    for key in ("context_length", "llama.context_length", "gptoss.context_length"):
        raw = model_info.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                pass
    params = detail.get("parameters") or ""
    match = re.search(r"num_ctx\s+(\d+)", params)
    if match:
        return int(match.group(1))
    return None


def detect_capabilities(detail: Dict[str, Any]) -> Dict[str, bool]:
    """从模型详情中检测能力。

    Args:
        detail: /api/show 返回的模型详情。

    Returns:
        能力字典，包含 chat/vision/embedding/tools 布尔值。
    """
    caps: Dict[str, bool] = {
        "chat": True,
        "vision": False,
        "embedding": False,
        "tools": False,
    }
    if not detail:
        return caps

    model_info = detail.get("model_info") or {}
    for k in model_info:
        kl = k.lower()
        if any(x in kl for x in ("vision", "projector", "mmproj", "clip")):
            caps["vision"] = True
            break

    tpl = detail.get("template") or ""
    if "tools" in tpl.lower() or ".Tools" in tpl:
        caps["tools"] = True

    det = detail.get("details") or {}
    for fam in (det.get("families") or []):
        if any(x in fam.lower() for x in ("clip", "vision")):
            caps["vision"] = True

    params = detail.get("parameters") or ""
    if "embedding" in params.lower():
        caps["embedding"] = True

    return caps
