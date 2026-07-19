"""headers 模块 — Provider 适配器层。

职责：
    集中放置 provider HTTP 请求头构造逻辑。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


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
