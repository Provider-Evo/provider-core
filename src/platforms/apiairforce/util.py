from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://api.airforce"
CHAT_PATH: str = "/v1/chat/completions"
MODELS_PATH: str = "/v1/models"


def build_headers(token: str = "") -> Dict[str, str]:
    """构建请求头，apiairforce 默认无需鉴权。"""
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    *,
    stream: bool = False,
    temperature: Optional[float] = None,
    **kw: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    # 透传额外参数（如 top_p 等）
    for k, v in kw.items():
        if v is not None:
            payload[k] = v
    return payload


def parse_sse_line(data_str: str) -> Optional[Union[str, Dict[str, Any]]]:
    """解析 SSE data 行，返回文本增量或 usage。"""
    try:
        obj = json.loads(data_str)
    except json.JSONDecodeError:
        return None

    # 终止块
    if obj.get("choices") == [] and obj.get("usage"):
        return {"usage": obj["usage"]}

    choices = obj.get("choices") or []
    if not choices:
        return None

    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if content:
        return content
    return None
