


from __future__ import annotations

from typing import Dict

from .consts import BASE_URL, CHAT_PATH, IDE_VERSION


def build_headers(
    token: str = "",
    user_id: str = "",
    conversation_id: str = "",
    conversation_request_id: str = "",
    conversation_message_id: str = "",
    request_id: str = "",
) -> Dict[str, str]:
    """构建 CodeBuddy 接口请求头（纯函数，不生成随机值）。

    Args:
        token: Bearer 鉴权令牌。
        user_id: 用户唯一标识。
        conversation_id: 会话 ID。
        conversation_request_id: 会话请求 ID。
        conversation_message_id: 会话消息 ID。
        request_id: 请求 ID。

    Returns:
        完整请求头字典。
    """
    return {
        "Host": "www.codebuddy.ai",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "x-stainless-arch": "x64",
        "x-stainless-lang": "js",
        "x-stainless-os": "Windows",
        "x-stainless-package-version": "5.10.1",
        "x-stainless-retry-count": "0",
        "x-stainless-runtime": "node",
        "x-stainless-runtime-version": "v22.13.1",
        "X-Conversation-ID": conversation_id,
        "X-Conversation-Request-ID": conversation_request_id,
        "X-Conversation-Message-ID": conversation_message_id,
        "X-Request-ID": request_id,
        "X-Agent-Intent": "craft",
        "X-IDE-Type": "CLI",
        "X-IDE-Name": "CLI",
        "X-IDE-Version": IDE_VERSION,
        "Authorization": "Bearer {}".format(token),
        "X-Domain": "www.codebuddy.ai",
        "User-Agent": "CLI/{0} CodeBuddy/{0}".format(IDE_VERSION),
        "X-Product": "SaaS",
        "X-User-Id": user_id,
    }

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .payload import (
    build_payload,
)

from .sse import (
    parse_sse_line,
)

__all__ = [
    "build_payload",
    "parse_sse_line",
]
