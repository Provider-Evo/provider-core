from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

__all__ = ["AppConfig", "get_config", "reload_config", "start_config_watcher"]
logger = logging.getLogger(__name__)

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


@dataclass
class ServerCfg:
    host: str = "0.0.0.0"
    port: int = 1337
    debug: bool = False


@dataclass
class AuthCfg:
    enabled: bool = False
    keys: List[str] = field(default_factory=list)
    group_list_type: str = "blacklist"
    group_list: List[str] = field(default_factory=list)


@dataclass
class GatewayCfg:
    concurrent_enabled: bool = True
    concurrent_count: int = 3
    min_tokens: int = 10


@dataclass
class ProxyCfg:
    proxy_server: str = ""
    proxy_enabled: bool = False
    proxy_urls: List[str] = field(default_factory=list)


@dataclass
class FncallCfg:
    call_start_tag: str = "<function_calls>"
    call_end_tag: str = "</function_calls>"
    tools_start_tag: str = "<tools>"
    tools_end_tag: str = "</tools>"


@dataclass
class PlatformEntry:
    enabled: bool = True
    api_key: str = ""


@dataclass
class PlatformsProxyCfg:
    enabled_platforms: List[str] = field(default_factory=list)


@dataclass
class PlatformsCfg:
    platform_list_type: str = "blacklist"
    platform_list: List[str] = field(default_factory=list)
    entries: Dict[str, PlatformEntry] = field(default_factory=dict)


@dataclass
class DebugCfg:
    level: str = "INFO"


@dataclass
class AppConfig:
    server: ServerCfg = field(default_factory=ServerCfg)
    auth: AuthCfg = field(default_factory=AuthCfg)
    gateway: GatewayCfg = field(default_factory=GatewayCfg)
    proxy: ProxyCfg = field(default_factory=ProxyCfg)
    fncall: FncallCfg = field(default_factory=FncallCfg)
    platforms: PlatformsCfg = field(default_factory=PlatformsCfg)
    platforms_proxy: PlatformsProxyCfg = field(default_factory=PlatformsProxyCfg)
    debug: DebugCfg = field(default_factory=DebugCfg)


_cfg: Optional[AppConfig] = None
_path: Optional[Path] = None
_mtime: float = 0.0


def _find() -> Optional[Path]:
    env = os.environ.get("CONFIG_PATH")
    if env and Path(env).is_file():
        return Path(env)
    for b in [Path(__file__).parent.parent.parent, Path.cwd()]:
        c = b / "config.toml"
        if c.is_file():
            return c.resolve()
    return None


def _parse(path: Path) -> AppConfig:
    if tomllib is None:
        logger.warning("tomllib/tomli 不可用")
        return AppConfig()
    with open(str(path), "rb") as f:
        raw = tomllib.load(f)
    s = raw.get("server", {})
    auth_raw = raw.get("auth", {})
    proxy_raw = raw.get("proxy", {})
    fncall_raw = raw.get("fncall", {})
    platforms_raw = raw.get("platforms", {})
    pp_raw = raw.get("platforms_proxy", {})
    debug_raw = raw.get("debug", {})

    platforms = PlatformsCfg()
    platforms.platform_list_type = platforms_raw.get("platform_list_type", "blacklist")
    platforms.platform_list = list(platforms_raw.get("platform_list", []))
    for key, val in raw.items():
        if key.startswith("platforms.") and key != "platforms":
            name = key.split(".", 1)[1]
            if isinstance(val, dict):
                platforms.entries[name] = PlatformEntry(
                    enabled=bool(val.get("enabled", True)),
                    api_key=str(val.get("api_key", "")),
                )

    pp = PlatformsProxyCfg(enabled_platforms=list(pp_raw.get("enabled_platforms", [])))

    return AppConfig(
        server=ServerCfg(s.get("host", "0.0.0.0"), int(s.get("port", 1337)), bool(s.get("debug", False))),
        auth=AuthCfg(
            bool(auth_raw.get("enabled", False)),
            list(auth_raw.get("keys", [])),
            str(auth_raw.get("group_list_type", "blacklist")),
            list(auth_raw.get("group_list", [])),
        ),
        gateway=GatewayCfg(
            bool(raw.get("gateway", {}).get("concurrent_enabled", True)),
            int(raw.get("gateway", {}).get("concurrent_count", 3)),
            int(raw.get("gateway", {}).get("min_tokens", 10)),
        ),
        proxy=ProxyCfg(
            str(proxy_raw.get("proxy_server", "")),
            bool(proxy_raw.get("proxy_enabled", False)),
            list(proxy_raw.get("proxy_urls", [])),
        ),
        fncall=FncallCfg(
            fncall_raw.get("call_start_tag", "<function_calls>"),
            fncall_raw.get("call_end_tag", "</function_calls>"),
            fncall_raw.get("tools_start_tag", "<tools>"),
            fncall_raw.get("tools_end_tag", "</tools>"),
        ),
        platforms=platforms,
        platforms_proxy=pp,
        debug=DebugCfg(level=str(debug_raw.get("level", "INFO"))),
    )


def _load() -> AppConfig:
    global _cfg, _path, _mtime
    p = _find()
    if p is None:
        logger.warning("未找到 config.toml")
        _cfg = AppConfig()
        return _cfg
    try:
        _cfg = _parse(p)
        _path, _mtime = p, p.stat().st_mtime
        logger.info("配置已加载: %s", p)
    except Exception as e:
        logger.error("config.toml 加载失败: %s", e)
        if _cfg is None:
            _cfg = AppConfig()
    return _cfg


def get_config() -> AppConfig:
    global _cfg
    if _cfg is None:
        _load()
    return _cfg


def reload_config() -> AppConfig:
    return _load()


async def start_config_watcher(interval: float = 2.0) -> None:
    global _mtime
    while True:
        await asyncio.sleep(interval)
        if _path and _path.exists():
            try:
                mt = _path.stat().st_mtime
                if mt > _mtime:
                    logger.info("config.toml 变更，重载")
                    _load()
            except Exception:
                pass
