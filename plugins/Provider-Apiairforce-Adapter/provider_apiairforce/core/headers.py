

from typing import Dict

from .consts import BASE_URL


def build_headers(token: str = "") -> Dict[str, str]:
    """构建请求头，apiairforce 默认无需鉴权。

    Args:
        token: API 密钥，可选。

    Returns:
        HTTP 请求头字典。
    """
    headers: Dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": BASE_URL,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
