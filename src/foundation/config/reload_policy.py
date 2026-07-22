

from typing import Any, Dict, FrozenSet, Sequence, Tuple

from echotools.logger.manager import get_logger

__all__ = [
    "apply_hot_config_side_effects",
    "changed_platform_names",
    "requires_process_restart",
    "resolve_changed_scopes",
    "scope_needs_app_reload",
]

logger = get_logger(__name__)

_PROCESS_RESTART_PATHS: Tuple[str, ...] = (
    "server.host",
    "server.port",
    "server.startup_force_kill_port",
    "server.max_restarts",
    "debug.access_log",
)

_SECTION_SCOPES: Tuple[Tuple[str, str], ...] = (
    ("server", "server"),
    ("proxy", "proxy"),
    ("gateway", "gateway"),
    ("auth", "auth"),
    ("debug", "debug"),
    ("fncall", "fncall"),
    ("http_pool", "http_pool"),
    ("autoupdate", "autoupdate"),
    ("anthropic", "anthropic"),
    ("openai", "openai"),
    ("model_mapping", "model_mapping"),
)

_APP_RELOAD_SCOPES = frozenset(
    {"auth", "gateway", "fncall", "anthropic", "openai", "webui", "model_mapping"},
)

_PLATFORM_CFG_KEYS = frozenset({"platform_list_type", "platform_list"})


def _dig(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _section_changed(old: Dict[str, Any], new: Dict[str, Any], section: str) -> bool:
    return old.get(section) != new.get(section)


def _platforms_cfg_changed(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
    old_p = old.get("platforms") or {}
    new_p = new.get("platforms") or {}
    if not isinstance(old_p, dict) or not isinstance(new_p, dict):
        return old_p != new_p
    for key in _PLATFORM_CFG_KEYS:
        if old_p.get(key) != new_p.get(key):
            return True
    return False


def changed_platform_names(old: Dict[str, Any], new: Dict[str, Any]) -> FrozenSet[str]:
    """返回 ``[platforms.<name>]`` 段发生变更的平台名集合。"""
    old_p = old.get("platforms") or {}
    new_p = new.get("platforms") or {}
    if not isinstance(old_p, dict):
        old_p = {}
    if not isinstance(new_p, dict):
        new_p = {}
    names: set[str] = set()
    all_keys = set(old_p.keys()) | set(new_p.keys())
    for key in all_keys:
        if key in _PLATFORM_CFG_KEYS:
            continue
        if old_p.get(key) != new_p.get(key):
            names.add(str(key).split(".")[0])
    return frozenset(names)


def resolve_changed_scopes(old: Dict[str, Any], new: Dict[str, Any]) -> Tuple[str, ...]:
    """根据配置 diff 推断变更 scope。"""
    scopes: list[str] = []
    for section, scope in _SECTION_SCOPES:
        if _section_changed(old, new, section):
            scopes.append(scope)
    if _platforms_cfg_changed(old, new):
        scopes.append("platforms_cfg")
    for name in changed_platform_names(old, new):
        scoped = "platforms:{}".format(name)
        if scoped not in scopes:
            scopes.append(scoped)
    if not scopes:
        scopes.append("main")
    return tuple(scopes)


def scope_needs_app_reload(scopes: Sequence[str]) -> bool:
    """判断是否需要 L3 ``AppHost.reload_app``。"""
    normalized = set(scopes)
    if normalized & _APP_RELOAD_SCOPES:
        return True
    return any(scope.startswith("platforms:") for scope in normalized)


def requires_process_restart(old: Dict[str, Any], new: Dict[str, Any]) -> bool:
    """判断配置 diff 是否需要整进程重启。"""
    for path in _PROCESS_RESTART_PATHS:
        if _dig(old, path) != _dig(new, path):
            logger.info("配置项 [%s] 变更，需要进程重启", path)
            return True
    if _section_changed(old, new, "http_pool"):
        logger.info("http_pool 变更，需要进程重启")
        return True
    return False


def apply_hot_config_side_effects(
    old: Dict[str, Any],
    new: Dict[str, Any],
) -> None:
    """对可在内存中生效的配置段执行副作用。"""
    if _section_changed(old, new, "proxy"):
        try:
            from src.core.server.lifecycle.net.proxy import activate

            activate()
            logger.info("代理配置已热更新")
        except Exception as exc:
            logger.debug("代理配置热更新失败: %s", exc)
