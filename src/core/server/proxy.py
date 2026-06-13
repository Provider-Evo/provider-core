"""代理支持模块 → echotools ProxyManager 封装。"""
from __future__ import annotations

import os
import warnings
from typing import Dict

from echotools.proxy.manager import ProxyManager

warnings.filterwarnings("ignore", message="Unclosed connection")
warnings.filterwarnings("ignore", module="aiohttp.connector")

_mgr = ProxyManager()


def _load_from_config() -> None:
    try:
        from src.core.config import get_config
        cfg = get_config().proxy
        _mgr.configure(
            proxy_server=cfg.proxy_server,
            enabled=cfg.proxy_enabled,
            url_patterns=cfg.proxy_url_patterns,
        )
    except Exception:
        pass


def activate() -> None:
    _load_from_config()
    _mgr.activate()


def deactivate() -> None:
    _mgr.deactivate()


def is_active() -> bool:
    return _mgr.is_active()


def get_proxy_server() -> str:
    proxies = _mgr.get_proxy_dict()
    return proxies.get("http") or proxies.get("https") or ""


def get_proxy_dict() -> Dict[str, str]:
    return _mgr.get_proxy_dict()


def _init() -> None:
    _mgr.patch_requests()
    _mgr.patch_aiohttp()
    # Only load proxy config in Worker process (Runner doesn't need it)
    if os.environ.get("WORKER_PROCESS") == "1":
        activate()


_init()
