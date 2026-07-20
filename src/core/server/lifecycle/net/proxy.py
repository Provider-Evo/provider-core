
import os
import warnings
from typing import Dict

from echotools.proxy.manager import ProxyManager

from src.foundation.config import get_config

__all__ = [
    "activate",
    "deactivate",
    "is_active",
    "get_proxy_server",
    "get_proxy_dict",
]

warnings.filterwarnings("ignore", message="Unclosed connection")
warnings.filterwarnings("ignore", module="aiohttp.connector")

_mgr = ProxyManager()


def _load_from_config() -> None:
    """Load proxy configuration from config/main_config.toml."""
    try:
        cfg = get_config().proxy
        _mgr.configure(
            proxy_server=cfg.proxy_server,
            enabled=cfg.proxy_enabled,
            url_patterns=cfg.proxy_url_patterns,
        )
    except Exception:
        pass


def activate() -> None:
    """Activate proxy (load from config and enable)."""
    _load_from_config()
    _mgr.activate()


def deactivate() -> None:
    """Deactivate proxy."""
    _mgr.deactivate()


def is_active() -> bool:
    """Whether proxy is active."""
    return _mgr.is_active()


def get_proxy_server() -> str:
    """Get current proxy server URL.

Returns:
    Proxy server URL, or empty string if not configured."""
    proxies = _mgr.get_proxy_dict()
    return proxies.get("http") or proxies.get("https") or ""


def get_proxy_dict() -> Dict[str, str]:
    """Get proxy dictionary.

Returns:
    ``{"http": "...", "https": "..."}`` proxy configuration."""
    return _mgr.get_proxy_dict()


def _init_proxy() -> None:
    """Initialize proxy support (only activated in Worker process)."""
    _mgr.patch_requests()
    _mgr.patch_aiohttp()
    if os.environ.get("WORKER_PROCESS") == "1":
        activate()


_init_proxy()
