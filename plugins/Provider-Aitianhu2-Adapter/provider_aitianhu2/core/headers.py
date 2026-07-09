"""AItianhu2 请求头构造模块。

提供统一的 HTTP 请求头构建函数。
"""

from __future__ import annotations

from typing import Dict, Optional

from .constants import (
    BASE_URL,
    BUILD_HASH,
    USER_AGENT,
)


def build_headers(
    device_id: str,
    referer: Optional[str] = None,
) -> Dict[str, str]:
    """构建与 HAR 精确匹配的公共请求头。

    Args:
        device_id: 设备标识。
        referer: 引用页面 URL（可选，默认为 BASE_URL/）。

    Returns:
        HTTP 请求头字典。
    """
    return {
        "accept":              "*/*",
        "accept-encoding":     "gzip, deflate, br, zstd",
        "accept-language":     "zh-CN,zh;q=0.9",
        "content-type":        "application/json",
        "oai-client-version":  BUILD_HASH,
        "oai-device-id":       device_id,
        "oai-language":        "zh-CN",
        "origin":              BASE_URL,
        "referer":             referer or f"{BASE_URL}/",
        "sec-ch-ua":           (
            '"Google Chrome";v="149", "Chromium";v="149", '
            '"Not)A;Brand";v="24"'
        ),
        "sec-ch-ua-mobile":    "?0",
        "sec-ch-ua-platform":  '"Windows"',
        "sec-fetch-dest":      "empty",
        "sec-fetch-mode":      "cors",
        "sec-fetch-site":      "same-origin",
        "user-agent":          USER_AGENT,
    }
