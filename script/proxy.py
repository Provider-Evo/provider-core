"""
HTTP代理模块 - 导入即生效

为所有HTTP请求自动配置代理。
通过注入 builtins 实现全局免导入使用 requests / aiohttp。

用法::

    import proxy

    # 无需手动导入 requests / aiohttp，直接使用
    requests.get("https://httpbin.org/get")   # 自动走代理

    proxy.deactivate()                         # 临时关闭
    requests.get("https://httpbin.org/get")   # 直连

    proxy.activate()                           # 重新开启
    requests.get("https://httpbin.org/get")   # 又走代理
"""

from __future__ import annotations

import builtins
import logging
import re
import warnings
from typing import Any, Optional

# 过滤掉 aiohttp 的 Unclosed connection 警告
warnings.filterwarnings("ignore", message="Unclosed connection")
warnings.filterwarnings("ignore", module="aiohttp.connector")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("proxy")

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------
PROXY_SERVER: str = "http://127.0.0.1:40001"
IP_PATTERN = re.compile(r'^(https?://)?(\d{1,3}\.){3}\d{1,3}(:\d+)?(/|$)')

# ---------------------------------------------------------------------------
# 内部状态
# ---------------------------------------------------------------------------
_active: bool = False


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _is_ip_address(url: str) -> bool:
    """判断URL是否是IP地址访问"""
    return bool(IP_PATTERN.match(url))


# ---------------------------------------------------------------------------
# requests 补丁
# ---------------------------------------------------------------------------
def _patch_requests() -> None:
    """直接补丁 requests 模块"""
    try:
        import requests
    except ImportError:
        logger.warning("requests 库未安装，跳过")
        builtins.requests = None
        return

    original_request = requests.Session.request

    def patched_request(self, method, url, *args, **kwargs):
        if _is_ip_address(str(url)):
            return original_request(self, method, url, *args, **kwargs)
        
        if _active and 'proxies' not in kwargs:
            kwargs['proxies'] = {
                'http': PROXY_SERVER,
                'https': PROXY_SERVER
            }
        return original_request(self, method, url, *args, **kwargs)

    requests.Session.request = patched_request
    builtins.requests = requests
    logger.info("requests 补丁完成，代理服务器: %s", PROXY_SERVER)


# ---------------------------------------------------------------------------
# aiohttp 补丁
# ---------------------------------------------------------------------------
def _patch_aiohttp() -> None:
    """直接补丁 aiohttp 模块"""
    try:
        import aiohttp
        from aiohttp import ClientSession, ClientResponse
        import asyncio
    except ImportError:
        logger.warning("aiohttp 库未安装，跳过")
        builtins.aiohttp = None
        return

    original_init = ClientSession.__init__
    original_request = ClientSession._request

    def patched_init(self, *args, **kwargs):
        # 确保连接器正确配置
        if 'connector' not in kwargs:
            kwargs['connector'] = aiohttp.TCPConnector(force_close=False)
        original_init(self, *args, **kwargs)
        self._default_proxy = PROXY_SERVER if _active else None

    async def patched_request(self, method, url, **kwargs):
        url_str = str(url)
        if _is_ip_address(url_str):
            return await original_request(self, method, url, **kwargs)
        
        if _active and 'proxy' not in kwargs:
            kwargs['proxy'] = self._default_proxy
        
        try:
            return await original_request(self, method, url, **kwargs)
        except Exception as e:
            logger.debug(f"请求异常: {e}")
            raise

    ClientSession.__init__ = patched_init
    ClientSession._request = patched_request
    
    # 确保连接正确关闭
    original_close = ClientSession.close
    
    async def patched_close(self):
        try:
            await original_close(self)
        except Exception:
            pass
    
    ClientSession.close = patched_close
    
    builtins.aiohttp = aiohttp
    logger.info("aiohttp 补丁完成，代理服务器: %s", PROXY_SERVER)


# ---------------------------------------------------------------------------
# 公共 API
# ---------------------------------------------------------------------------
def activate() -> None:
    """激活代理"""
    global _active
    _active = True
    logger.info("代理已激活: %s", PROXY_SERVER)


def deactivate() -> None:
    """停用代理"""
    global _active
    _active = False
    logger.info("代理已停用，恢复直连")


def is_active() -> bool:
    """返回代理是否激活"""
    return _active


# ---------------------------------------------------------------------------
# 模块初始化
# ---------------------------------------------------------------------------
def _init() -> None:
    """初始化补丁"""
    _patch_requests()
    _patch_aiohttp()
    activate()


#_init()