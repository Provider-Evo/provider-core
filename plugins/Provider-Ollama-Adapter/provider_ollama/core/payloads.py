


from typing import Any, Dict, List


def _extract_content_parts(
    content: List[Any],
) -> "tuple[List[str], List[str]]":
    """从多模态消息内容中提取文本片段与 base64 图片数据。"""
    text_parts: List[str] = []
    images: List[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            text_parts.append(part.get("text", ""))
            continue
        if part.get("type") != "image_url":
            continue
        url = part.get("image_url", {}).get("url", "")
        if url.startswith("data:") and ";base64," in url:
            images.append(url.split(";base64,", 1)[1])
    return text_parts, images


def build_image_messages(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将 OpenAI 格式的消息转换为 Ollama 格式。

    处理多模态消息中的 image_url，提取 base64 数据。

    Args:
        messages: OpenAI 格式的消息列表。

    Returns:
        Ollama 格式的消息列表。
    """
    if not messages:
        return []

    result: List[Dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "user")

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            text_parts, images = _extract_content_parts(content)
            entry: Dict[str, Any] = {
                "role": role,
                "content": "\n".join(text_parts),
            }
            if images:
                entry["images"] = images
            result.append(entry)
            continue

        result.append({"role": role, "content": str(content)})

    return result


def build_chat_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建 Ollama 聊天请求体。

    Args:
        messages: Ollama 格式的消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 额外参数（temperature, top_p, max_tokens, stop）。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }

    opts: Dict[str, Any] = {}
    if kw.get("temperature") is not None:
        opts["temperature"] = kw["temperature"]
    if kw.get("top_p") is not None:
        opts["top_p"] = kw["top_p"]
    if kw.get("max_tokens") is not None:
        opts["num_predict"] = kw["max_tokens"]
    if kw.get("stop"):
        opts["stop"] = kw["stop"]
    if opts:
        payload["options"] = opts

    return payload

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .sse import (
    parse_ollama_line,
)

__all__ = [
    "parse_ollama_line",
]
