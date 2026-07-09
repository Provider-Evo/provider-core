from __future__ import annotations

"""Ollama 模型能力检测。"""

from typing import Any, Dict


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
