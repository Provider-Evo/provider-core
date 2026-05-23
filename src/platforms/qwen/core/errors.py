"""Qwen 平台内部异常定义。"""

from __future__ import annotations


class QwenError(Exception):
    """Qwen 平台基础异常。"""


class WAFBlockedError(QwenError):
    """Qwen 请求被 WAF 拦截时抛出。

    特征：响应 ``Content-Type`` 包含 ``text/html`` 或返回挑战页面。
    """


class TokenExpiredError(QwenError):
    """账号 token 已失效，应触发重新登录。"""
