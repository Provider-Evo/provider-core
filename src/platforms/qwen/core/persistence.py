from __future__ import annotations

"""Qwen 账号、Cookie 与代理状态持久化。"""

import json
import time
from pathlib import Path
from typing import Any, Dict

from src.core.utils.io_utils import atomic_write_text, read_text_if_exists
from src.logger import get_logger

from ..accounts import Account
from .endpoints import COOKIE_REFRESH_INTERVAL, PERSIST_PATH
from .proxy import ProxyState

logger = get_logger(__name__)


def load_persist(
    account_states: Dict[str, Account],
    cookies: Dict[str, Any],
    proxy: ProxyState,
) -> Dict[str, Any]:
    """从磁盘加载状态。"""
    raw = read_text_if_exists(Path(PERSIST_PATH))
    if raw is None:
        return cookies
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Qwen 持久化加载失败: %s", exc)
        return cookies

    _restore_accounts(account_states, data.get("accounts") or {})
    cookies = _restore_cookies(cookies, data.get("cookies") or {})
    proxy_state = data.get("proxy") or {}
    if isinstance(proxy_state, dict):
        proxy.load(
            proxy_state.get("enabled"),
        )
    loaded = sum(1 for account in account_states.values() if account.token)
    logger.debug("Qwen: 从持久化恢复 %d 个账号 token", loaded)
    return cookies


def save_persist(
    account_states: Dict[str, Account],
    cookies: Dict[str, Any],
    proxy: ProxyState,
) -> None:
    """将状态原子写入磁盘。"""
    payload = {
        "accounts": _build_accounts_payload(account_states),
        "cookies": _build_cookie_payload(cookies),
        "proxy": proxy.to_dict(),
        "updated": time.time(),
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    existing = read_text_if_exists(Path(PERSIST_PATH))
    if existing == content:
        return
    atomic_write_text(Path(PERSIST_PATH), content)


def _build_accounts_payload(
    account_states: Dict[str, Account],
) -> Dict[str, Any]:
    """按账号插入顺序构建稳定持久化负载。"""
    return {
        username: {
            "token": account.token,
            "user_id": account.user_id,
            "password_hash": account.password_hash,
            "token_expires": account.token_expires,
            "memory_disabled": account.memory_disabled,
            "context_length": account.context_length,
            "is_login": account.is_login,
        }
        for username, account in account_states.items()
    }


def _build_cookie_payload(cookies: Dict[str, Any]) -> Dict[str, Any]:
    """构建 cookie 持久化负载。"""
    result = {
        key: value
        for key, value in cookies.items()
        if key != "timestamp"
    }
    result["timestamp"] = time.time()
    return result


def _restore_accounts(
    account_states: Dict[str, Account],
    saved: Dict[str, Any],
) -> None:
    """将磁盘记录回写到现存账号对象上。"""
    for username, info in saved.items():
        if username not in account_states or not isinstance(info, dict):
            continue
        account = account_states[username]
        account.token = str(info.get("token", ""))
        account.user_id = str(info.get("user_id", ""))
        account.password_hash = str(info.get("password_hash", ""))
        account.token_expires = float(info.get("token_expires", 0))
        account.memory_disabled = bool(info.get("memory_disabled", False))
        account.context_length = info.get("context_length")
        account.is_login = bool(info.get("is_login", account.is_login))


def _restore_cookies(
    current: Dict[str, Any],
    saved: Dict[str, Any],
) -> Dict[str, Any]:
    """若磁盘 cookie 未过期则取之。"""
    if not isinstance(saved, dict) or not saved.get("ssxmod_itna"):
        return current
    age = time.time() - float(saved.get("timestamp", 0))
    if age >= COOKIE_REFRESH_INTERVAL:
        return current
    logger.info("Qwen: 从持久化恢复 Cookie")
    return {
        key: value
        for key, value in saved.items()
        if key != "timestamp"
    }
