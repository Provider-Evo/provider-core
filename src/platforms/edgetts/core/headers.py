"""Edge TTS 请求头构造。"""

from __future__ import annotations

import secrets
from typing import Dict


CHROMIUM_FULL_VERSION: str = "143.0.3650.75"
CHROMIUM_MAJOR_VERSION: str = CHROMIUM_FULL_VERSION.split(".", 1)[0]

BASE_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{}.0.0.0 Safari/537.36 Edg/{}.0.0.0".format(
            CHROMIUM_MAJOR_VERSION, CHROMIUM_MAJOR_VERSION
        )
    ),
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

WSS_HANDSHAKE_HEADERS: Dict[str, str] = {
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
}
WSS_HANDSHAKE_HEADERS.update(BASE_HEADERS)


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 HTTP 请求头。

    Args:
        token: 预留的鉴权令牌（edge tts 当前无需）。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
        "User-Agent": BASE_HEADERS["User-Agent"],
        "Accept": "*/*",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Host": "speech.platform.bing.com",
        "Cookie": "muid={};".format(secrets.token_hex(16).upper()),
    }
    if token:
        headers["Authorization"] = token
    return headers


def build_wss_headers() -> Dict[str, str]:
    """构建 WebSocket 握手请求头。

    Returns:
        WebSocket 握手请求头字典。
    """
    h = dict(WSS_HANDSHAKE_HEADERS)
    h["Cookie"] = "muid={};".format(secrets.token_hex(16).upper())
    return h
