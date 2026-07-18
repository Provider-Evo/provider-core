"""headers 模块 — Provider 适配器层。

职责：
    集中放置 provider HTTP 请求头构造逻辑。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


import ssl
from typing import Dict


def make_ssl_ctx() -> ssl.SSLContext:
    """创建禁用证书验证的 SSL 上下文。

    Returns:
        配置为不验证证书和主机名的 SSLContext。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def build_headers(api_key: str) -> Dict[str, str]:
    """构建 HTTP 请求头。

    Args:
        api_key: caiyuesbk 平台 API Key。

    Returns:
        包含鉴权信息和内容类型的请求头字典。
    """
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
