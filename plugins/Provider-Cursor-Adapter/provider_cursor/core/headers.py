"""Cursor 平台请求头构造。"""

from __future__ import annotations

from typing import Dict


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 Chrome 浏览器指纹请求头。

    从 cursor-client.ts getChromeHeaders() 移植。
    token 参数保留接口兼容性，Cursor 不使用 API Key 鉴权。

    Args:
        token: 鉴权令牌（Cursor 平台忽略此参数）。

    Returns:
        请求头字典。
    """
    return {
        "Content-Type": "application/json",
        "sec-ch-ua-platform": '"Windows"',
        "x-path": "/api/chat",
        "sec-ch-ua": (
            '"Chromium";v="140","Not=A?Brand";v="24","Google Chrome";v="140"'
        ),
        "x-method": "POST",
        "sec-ch-ua-bitness": '"64"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-arch": '"x86"',
        "sec-ch-ua-platform-version": '"19.0.0"',
        "origin": "https://cursor.com",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://cursor.com/",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "priority": "u=1,i",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0.0.0 Safari/537.36"
        ),
        "x-is-human": "",
    }
