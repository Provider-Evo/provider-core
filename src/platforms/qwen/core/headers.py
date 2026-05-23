"""HTTP 请求头构建工具。

封装 Qwen 各类接口（聊天 / 登录 / 停止 / SSE）的请求头组装。
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, Optional

from .bxua import generate_bxua
from .cookies import generate_cookies
from .endpoints import (
    BASE_URL,
    BAXIA_SDK_VERSION,
    FRONTEND_VERSION,
    SEC_CH_UA,
    USE_LOCAL_MODE,
    USER_AGENT,
    USER_AGENT_MOBILE,
)
from .fp import generate_fingerprint


def build_cookie_string(
    token: str,
    cookies: Optional[Dict[str, Any]] = None,
) -> str:
    """构建 Cookie 请求头字符串。

    Args:
        token: Bearer 令牌。
        cookies: Cookie 字典；``None`` 表示自动生成。

    Returns:
        分号分隔的 Cookie 字符串。
    """
    if cookies is None:
        cookies = generate_cookies()
    return "; ".join(
        [
            "token={}".format(token),
            "ssxmod_itna={}".format(cookies.get("ssxmod_itna", "")),
            "ssxmod_itna2={}".format(cookies.get("ssxmod_itna2", "")),
        ]
    )


def build_headers(
    token: str,
    *,
    chat_id: Optional[str] = None,
    include_sse: bool = False,
    fingerprint: Optional[str] = None,
    cookies: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    """构建通用 Qwen 请求头。

    Args:
        token: Bearer 令牌。
        chat_id: 对话 ID，用于 ``Referer``。
        include_sse: 是否包含 SSE 相关头。
        fingerprint: 指纹字符串；``None`` 表示自动生成。
        cookies: Cookie 字典；``None`` 表示自动生成。

    Returns:
        请求头字典。
    """
    if USE_LOCAL_MODE or chat_id is None:
        referer = "{}/c/local".format(BASE_URL)
    else:
        referer = "{}/c/{}".format(BASE_URL, chat_id)

    fp = fingerprint or generate_fingerprint()
    if cookies is None:
        cookies = generate_cookies(fp)

    headers: Dict[str, str] = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Cookie": build_cookie_string(token, cookies),
        "Host": "chat.qwen.ai",
        "Origin": BASE_URL,
        "Referer": referer,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Timezone": time.strftime("%a %b %d %Y %H:%M:%S GMT%z"),
        "User-Agent": USER_AGENT,
        "Version": FRONTEND_VERSION,
        "X-Request-Id": str(uuid.uuid4()),
        "authorization": "Bearer {}".format(token),
        "bx-ua": generate_bxua(fp),
        "bx-v": BAXIA_SDK_VERSION,
        "sec-ch-ua": SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "source": "web",
    }
    if include_sse:
        headers["X-Accel-Buffering"] = "no"
    return headers


def build_login_headers() -> Dict[str, str]:
    """构建登录接口专用请求头。

    Returns:
        登录请求头字典。
    """
    return {
        "Host": "chat.qwen.ai",
        "Content-Type": "application/json;charset=UTF-8",
        "User-Agent": USER_AGENT_MOBILE,
        "Accept": "*/*",
        "Origin": BASE_URL,
        "Referer": "{}/auth?action=signin".format(BASE_URL),
    }


def build_stop_headers(token: str) -> Dict[str, str]:
    """构建停止生成请求头。

    Args:
        token: Bearer 令牌。

    Returns:
        停止生成请求头字典。
    """
    return {
        "Accept": "application/json",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Host": "chat.qwen.ai",
        "Origin": BASE_URL,
        "Referer": "{}/c/local".format(BASE_URL),
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": USER_AGENT,
        "X-Request-Id": str(uuid.uuid4()),
        "authorization": "Bearer {}".format(token),
        "source": "web",
    }
