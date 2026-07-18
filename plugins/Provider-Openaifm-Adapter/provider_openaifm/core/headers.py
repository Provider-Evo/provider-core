"""headers 模块 — Provider 适配器层。

职责：
    集中放置 provider HTTP 请求头构造逻辑。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import Dict

from .constants import USER_AGENT


def build_headers() -> Dict[str, str]:
    """构建 HTTP 请求头。

    openai.fm 无需认证，也不手动设置 Content-Type（multipart 由 aiohttp 自动添加）。

    Returns:
        请求头字典。
    """
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "origin": "https://www.openai.fm",
        "referer": "https://www.openai.fm/",
        "User-Agent": USER_AGENT,
        "sec-ch-ua": '"Google Chrome";v="149","Chromium";v="149","Not)A;Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }

__all__ = [
    "build_headers",
]
