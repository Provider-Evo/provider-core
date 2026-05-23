from __future__ import annotations

"""代理支持模块——自动检测环境变量，支持 HTTP/HTTPS/SOCKS5 代理。

代理优先级：
1. 环境变量（大写优先于小写）
   - HTTP_PROXY / http_proxy
   - HTTPS_PROXY / https_proxy
   - ALL_PROXY / all_proxy
2. config.toml 中的 proxy_server
3. 停用代理

支持的代理协议：
- http://host:port
- https://host:port
- socks5://host:port
- socks5h://host:port  （远程 DNS 解析）
- socks4://host:port
"""

import builtins
import os
import re
import ssl
import warnings
from typing import Any, Dict, List, Optional, Pattern, Tuple

from src.core.config import get_config
from src.logger import get_logger

warnings.filterwarnings("ignore", message="Unclosed connection")
warnings.filterwarnings("ignore", module="aiohttp.connector")
logger = get_logger(__name__)
__all__ = ["activate", "deactivate", "is_active", "get_proxy_server", "get_proxy_dict"]

_IP_RE = re.compile(r"^(https?://)?(\d{1,3}\.){3}\d{1,3}(:\d+)?(/|$)")
_PROTOCOL_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_active = False

# 按协议类型存储的代理地址
_proxies: Dict[str, str] = {}  # {"http": "...", "https": "..."}


def _get_proxy_cfg() -> Tuple[str, bool, List[Pattern]]:
    """从中央配置获取代理配置。

    Returns:
        (proxy_server, proxy_enabled, proxy_url_patterns)
    """
    try:
        cfg = get_config().proxy
        return cfg.proxy_server, cfg.proxy_enabled, cfg.proxy_url_patterns
    except Exception:
        return "", False, []


PROXY_SERVER, _ENABLED, _PATTERNS = _get_proxy_cfg()


def _detect_env_proxies() -> Dict[str, str]:
    """从环境变量检测代理地址，支持多种命名格式。

    优先级：大写 HTTP_PROXY > 小写 http_proxy > ALL_PROXY 回退

    Returns:
        {"http": "url", "https": "url"} 字典。
    """
    result: Dict[str, str] = {}

    # 检测 HTTP 代理
    http_proxy = (
        os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
        or ""
    )
    if http_proxy:
        result["http"] = http_proxy

    # 检测 HTTPS 代理
    https_proxy = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or ""
    )
    if https_proxy:
        result["https"] = https_proxy

    # ALL_PROXY 作为 fallback
    all_proxy = (
        os.environ.get("ALL_PROXY")
        or os.environ.get("all_proxy")
        or ""
    )
    if all_proxy:
        result.setdefault("http", all_proxy)
        result.setdefault("https", all_proxy)

    return result


def _resolve_proxies() -> Dict[str, str]:
    """解析最终使用的代理配置。

    优先级：
    1. 环境变量（HTTP_PROXY, HTTPS_PROXY, ALL_PROXY）
    2. config.toml 中的 proxy_server（需 proxy_enabled=true）
    3. 空字典（无代理）

    Returns:
        {"http": "url", "https": "url"} 字典。
    """
    # 先检查环境变量
    env_proxies = _detect_env_proxies()
    if env_proxies:
        return env_proxies

    # 回退到 config.toml（需 proxy_enabled=true）
    if PROXY_SERVER and _ENABLED:
        return {"http": PROXY_SERVER, "https": PROXY_SERVER}

    return {}


def _normalize_proxy_url(url: str) -> str:
    """规范化代理 URL。

    - 无协议前缀时默认添加 http://
    - 保持 socks5://, socks5h://, socks4:// 等协议不变

    Args:
        url: 原始代理 URL。

    Returns:
        规范化后的 URL。
    """
    if not url:
        return url
    url = url.strip()
    # 已有协议前缀，原样返回
    if _PROTOCOL_RE.match(url):
        return url
    # 无协议前缀，默认 http
    return "http://" + url


def _is_ip(url: str) -> bool:
    """判断 URL 是否为直接 IP 地址。

    Args:
        url: URL 字符串。

    Returns:
        是否为 IP 地址。
    """
    return bool(_IP_RE.match(url))


def _should_proxy_url(url: str) -> bool:
    """判断指定 URL 是否应该走代理。

    逻辑：
    1. 代理未启用或无代理服务器 → 不走代理
    2. URL 是 IP 地址 → 不走代理
    3. proxy_urls 为空 → 所有 URL 都走代理
    4. proxy_urls 有值 → 正则匹配，命中的走代理

    Args:
        url: 请求 URL。

    Returns:
        是否应该走代理。
    """
    if not _active or not _proxies:
        return False

    if _is_ip(url):
        return False

    # proxy_urls 为空时，所有非 IP URL 都走代理
    if not _PATTERNS:
        return True

    # 有配置时，正则匹配，命中就走代理
    return any(p.search(url) for p in _PATTERNS)


def _patch_requests() -> None:
    """Patch requests 库以使用代理。"""
    try:
        import requests as _r  # type: ignore[import]

        _r.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    except (ImportError, AttributeError):
        return

    _orig = _r.Session.request

    def _p(self: Any, method: str, url: str, *a: Any, **kw: Any) -> Any:
        if not _should_proxy_url(str(url)):
            return _orig(self, method, url, *a, **kw)
        if "proxies" not in kw:
            kw["proxies"] = dict(_proxies)
            kw["verify"] = False
        return _orig(self, method, url, *a, **kw)

    _r.Session.request = _p  # type: ignore[method-assign]


def _is_socks_proxy(url: str) -> bool:
    """判断代理 URL 是否为 SOCKS 协议。

    Args:
        url: 代理 URL。

    Returns:
        是否为 SOCKS 代理。
    """
    return url.lower().startswith(("socks5://", "socks5h://", "socks4://"))


def _make_aiohttp_connector_for_proxy(
    proxy_url: Optional[str] = None,
) -> Any:
    """为指定代理 URL 创建合适的 aiohttp connector。

    HTTP/HTTPS 代理：使用原生 TCPConnector + proxy 参数。
    SOCKS 代理：使用 aiohttp_socks 的 SocksConnector。

    Args:
        proxy_url: 代理 URL，可为 None。

    Returns:
        connector 实例。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    if proxy_url and _is_socks_proxy(proxy_url):
        try:
            from aiohttp_socks import SocksConnector  # type: ignore[import]
            return SocksConnector(
                socks_url=proxy_url,
                ssl=ctx,
                limit=200,
                force_close=False,
            )
        except ImportError:
            logger.warning(
                "aiohttp-socks 未安装，SOCKS 代理不可用。请运行: pip install aiohttp-socks"
            )

    return TCPConnector(ssl=ctx, limit=200, force_close=False)


def _patch_aiohttp() -> None:
    """Patch aiohttp 以使用代理。

    支持 HTTP、HTTPS、SOCKS5 等多种代理协议。
    - HTTP/HTTPS 代理：使用 aiohttp 原生 proxy 参数
    - SOCKS5/SOCKS5H/SOCKS4 代理：使用 aiohttp-socks 的 SocksConnector

    SOCKS 代理需要安装 aiohttp-socks 库。
    """
    try:
        import aiohttp as _a
        from aiohttp import ClientSession, TCPConnector
    except ImportError:
        return

    _oi = ClientSession.__init__
    _or = ClientSession._request  # type: ignore[attr-defined]
    _oc = ClientSession.close

    def _pi(self: Any, *a: Any, **kw: Any) -> None:
        """Patch __init__：创建合适的 connector 并记录代理配置。"""
        if "connector" not in kw:
            primary_proxy = None
            if _active:
                primary_proxy = _proxies.get("https") or _proxies.get("http")
            kw["connector"] = _make_aiohttp_connector_for_proxy(primary_proxy)
        _oi(self, *a, **kw)
        self._proxy_dict = dict(_proxies) if _active else {}
        self._has_socks_connector = (
            _is_socks_proxy(self._proxy_dict.get("https", ""))
            or _is_socks_proxy(self._proxy_dict.get("http", ""))
        ) if _active else False

    async def _pr(self: Any, method: str, url: Any, **kw: Any) -> Any:
        """Patch _request：根据 URL 协议选择代理。"""
        if not _should_proxy_url(str(url)):
            return await _or(self, method, url, **kw)

        if "proxy" not in kw and not getattr(self, "_has_socks_connector", False):
            # 仅对非 SOCKS connector 设置 proxy 参数
            url_str = str(url)
            if url_str.startswith("https://"):
                kw["proxy"] = self._proxy_dict.get("https") or self._proxy_dict.get("http")
            else:
                kw["proxy"] = self._proxy_dict.get("http") or self._proxy_dict.get("https")

        return await _or(self, method, url, **kw)

    async def _pc(self: Any) -> None:
        """Patch close：安全关闭 session。"""
        try:
            await _oc(self)
        except Exception as e:
            logger.debug("aiohttp session 关闭异常: %s", e)

    ClientSession.__init__ = _pi  # type: ignore[method-assign]
    ClientSession._request = _pr  # type: ignore[attr-defined]
    ClientSession.close = _pc  # type: ignore[method-assign]


def activate() -> None:
    """激活代理。

    自动检测环境变量和配置文件，解析代理地址并激活。
    支持 HTTP、HTTPS、SOCKS5 等多种代理协议。
    """
    global _active, _proxies
    _proxies = _resolve_proxies()
    # 规范化所有代理 URL
    _proxies = {k: _normalize_proxy_url(v) for k, v in _proxies.items() if v}
    _active = bool(_proxies)

    if _active:
        proxy_desc = ", ".join(
            "{}={}".format(k, v) for k, v in sorted(_proxies.items())
        )
        logger.info("代理已激活: %s", proxy_desc)
    else:
        logger.info("代理未激活：无可用代理配置")


def deactivate() -> None:
    """停用代理。"""
    global _active, _proxies
    _active = False
    _proxies = {}
    logger.info("代理已停用")


def is_active() -> bool:
    """返回代理是否激活。

    Returns:
        是否激活。
    """
    return _active


def get_proxy_server() -> str:
    """返回代理服务器地址（兼容旧接口，返回第一个代理地址）。

    Returns:
        代理服务器 URL。
    """
    if _proxies:
        return _proxies.get("http") or _proxies.get("https") or ""
    return PROXY_SERVER


def get_proxy_dict() -> Dict[str, str]:
    """返回代理字典。

    Returns:
        {"http": "...", "https": "..."} 字典。
    """
    return dict(_proxies) if _active else {}


def _init() -> None:
    """模块初始化——patch 并按配置激活。"""
    _patch_requests()
    _patch_aiohttp()
    activate()


_init()
