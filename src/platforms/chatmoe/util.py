"""ChatMoe 工具函数"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional, Union

BASE_URL: str = "https://chatmoe.cn"
CHAT_PATH: str = "/api/chat"


def build_headers(token: str) -> Dict[str, str]:
    """构建请求头。

    Args:
        token: API Key 或 Bearer Token。

    Returns:
        请求头字典。
    """
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "authorization": token,
        "content-type": "application/json",
        "origin": "https://chatmoe.cn",
        "referer": "https://chatmoe.cn/",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/141.0.0.0 Safari/537.36"
        ),
        "sec-ch-ua": '"Google Chrome";v="141","Not?A_Brand";v="8","Chromium";v="141"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }


def build_payload(
    messages: List[Dict[str, Any]],
    model: str,
    *,
    stream: bool = True,
    thinking: bool = False,
    search: bool = False,
) -> Dict[str, Any]:
    """构建聊天请求体。

    Args:
        messages: 消息列表。
        model: 模型名称（ChatMoe 内部固定，此参数保留兼容性）。
        stream: 是否流式输出。
        thinking: 是否启用深度思考。
        search: 是否启用联网搜索。

    Returns:
        请求体字典。
    """
    return {
        "stream": stream,
        "user_id": str(uuid.uuid4()),
        "tools": [
            {
                "type": "web_search",
                "web_search": {
                    "search_engine": "search_std",
                    "enable": search,
                    "search_intent": True,
                },
            }
        ],
        "thinking": {"type": "enabled" if thinking else "disabled"},
        "messages": [
            {
                "role": m.get("role", "user"),
                "content": m.get("content", ""),
            }
            for m in messages
        ],
        "type": "text",
        "style": "default",
        "provider": "chatmoe_z",
    }


def parse_sse_line(
    data_str: str,
    *,
    thinking_started: bool = False,
    thinking_ended: bool = False,
    thinking_enabled: bool = False,
) -> Optional[Union[str, Dict[str, Any]]]:
    """解析单条 SSE data 字符串，返回 yield 值或 None。

    注意：ChatMoe 的 SSE 解析包含 thinking 状态机，状态由调用方维护，
    此函数为无状态版本，仅解析 JSON 并提取字段，状态逻辑在 client.py 中处理。

    Args:
        data_str: SSE data 字段内容（去除 "data:" 前缀）。
        thinking_started: 调用方传入的 thinking 开始状态（未使用，保留接口一致性）。
        thinking_ended: 调用方传入的 thinking 结束状态（未使用，保留接口一致性）。
        thinking_enabled: 是否启用 thinking 模式（未使用，保留接口一致性）。

    Returns:
        解析后的 yield 值，解析失败或无内容返回 None。
    """
    try:
        return json.loads(data_str)
    except (json.JSONDecodeError, ValueError):
        return None
