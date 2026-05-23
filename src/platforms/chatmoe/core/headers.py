from __future__ import annotations

"""ChatMoe 请求头构造。"""

from typing import Dict


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
