"""headers 模块 — Provider 适配器层。

职责：
    集中放置 provider HTTP 请求头构造逻辑。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


from typing import Dict


def build_headers(api_key: str) -> Dict[str, str]:
    """构建 Chutes 接口请求头。

    Args:
        api_key: Chutes API Key。

    Returns:
        完整请求头字典。
    """
    return {
        "Authorization": "Bearer {}".format(api_key),
        "Content-Type": "application/json",
    }
