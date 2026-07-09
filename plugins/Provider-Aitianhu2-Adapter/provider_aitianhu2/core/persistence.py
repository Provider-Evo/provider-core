"""AItianhu2 状态持久化。

支持多账号：``state.json`` 形如
``{"accounts": {"<key>": {...}}, "carids": {...}, "updated": ...}``。
旧版单账号扁平格式（顶层 ``device_id`` + ``cookies``）在首次加载时
透明迁移——按 ``api_key_hint``（缺失则用 ``"legacy"``）作为键包进
``accounts`` 字典。
"""

from __future__ import annotations

import json
import time
from http.cookies import Morsel
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
from yarl import URL

from src.core.utils.io_utils import atomic_write_text, read_text_if_exists
from src.logger import get_logger

from .constants import BASE_URL

logger = get_logger(__name__)

PERSIST_PATH = Path("persist/aitianhu2/state.json")
PERSIST_INTERVAL = 60
_COOKIE_NAMES = ("gfsessionid", "SERVERID", "superSponsor", "carid")


def _empty_state() -> Dict[str, Any]:
    return {"accounts": {}, "carids": None, "updated": 0}


def _migrate_legacy(data: Dict[str, Any]) -> Dict[str, Any]:
    """把旧版单账号扁平格式包进 ``accounts`` 字典。"""
    key = data.get("api_key_hint") or "legacy"
    return {
        "accounts": {key: data},
        "carids": data.get("carids"),
        "updated": data.get("updated", 0),
    }


def load_all_persist() -> Dict[str, Any]:
    """加载 ``state.json``，始终返回新格式
    ``{"accounts": {...}, "carids": {...}, "updated": float}``。

    * 文件不存在或 JSON 损坏 → 返回空骨架。
    * 旧扁平格式 → 透明迁移到 ``accounts`` 字典。
    """
    raw = read_text_if_exists(PERSIST_PATH)
    if raw is None:
        return _empty_state()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("AItianhu2 持久化解析失败: %s", exc)
        return _empty_state()
    if not isinstance(data, dict):
        return _empty_state()
    if "accounts" not in data and "device_id" in data:
        data = _migrate_legacy(data)
    if "accounts" not in data:
        data["accounts"] = {}
    data.setdefault("carids", None)
    data.setdefault("updated", 0)
    return data


def load_account_state(account_key: str) -> Dict[str, Any]:
    """取出单个账号的持久化状态；不存在则返回空字典。"""
    state = load_all_persist()
    accounts = state.get("accounts") or {}
    acc = accounts.get(account_key)
    return dict(acc) if isinstance(acc, dict) else {}


def restore_cookie_jar(
    session: aiohttp.ClientSession,
    cookies: Dict[str, str],
) -> None:
    """将持久化 cookie 恢复到会话中。

    使用 Morsel 对象设置正确的 path 属性，确保 cookie 能被发送到所有端点。
    """
    if not cookies:
        return

    jar = session.cookie_jar
    for name, value in cookies.items():
        if name not in _COOKIE_NAMES or not value:
            continue
        morsel = Morsel()
        morsel.set(name, value, value)
        morsel["path"] = "/"
        jar.update_cookies({name: morsel}, response_url=URL(BASE_URL))


def extract_cookie_state(session: aiohttp.ClientSession) -> Dict[str, str]:
    """从会话中提取需持久化的 cookie。"""
    cookies = session.cookie_jar.filter_cookies(URL(BASE_URL))
    result: Dict[str, str] = {}
    for name in _COOKIE_NAMES:
        morsel = cookies.get(name)
        if morsel is not None and morsel.value:
            result[name] = morsel.value
    return result


def save_all_persist(
    accounts: Dict[str, Dict[str, Any]],
    *,
    carids: Optional[Dict[str, Any]] = None,
) -> None:
    """原子写回整个 ``state.json``。

    Args:
        accounts: ``{account_key: account_payload}`` 字典。每个 account_payload
                  至少包含 ``device_id``、``authenticated``、``cookies``、
                  ``session_authed_at``。
        carids: 共享 carids 缓存 ``{"ids": [...], "fetched_at": float}``；
                为 ``None`` 时保留磁盘上既有值。
    """
    existing = load_all_persist()
    payload: Dict[str, Any] = {
        "accounts": dict(accounts),
        "carids": carids if carids is not None else existing.get("carids"),
        "updated": time.time(),
    }
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    existing_raw = read_text_if_exists(PERSIST_PATH)
    if existing_raw == content:
        return
    atomic_write_text(PERSIST_PATH, content)


def save_account_persist(
    account_key: str,
    session: aiohttp.ClientSession,
    *,
    device_id: str,
    authenticated: bool,
    models: List[str],
    api_key_hint: str,
    session_authed_at: float = 0,
    account_id: str = "",
    account_id_fetched_at: float = 0,
) -> None:
    """更新单个账号的持久化条目并原子写回磁盘。

    其它账号的状态保留不动；共享 carids 也保留。
    """
    state = load_all_persist()
    accounts = state.get("accounts") or {}
    accounts[account_key] = {
        "device_id": device_id,
        "authenticated": authenticated,
        "models": list(models),
        "api_key_hint": api_key_hint,
        "cookies": extract_cookie_state(session),
        "session_authed_at": session_authed_at,
        "account_id": account_id,
        "account_id_fetched_at": account_id_fetched_at,
        "updated": time.time(),
    }
    save_all_persist(accounts, carids=state.get("carids"))


# ---------------------------------------------------------------------------
# 旧 API：保留供尚未迁移的调用方使用。新代码请用 save_account_persist。
# ---------------------------------------------------------------------------
def load_persist() -> Dict[str, Any]:
    """加载首个账号的旧扁平格式状态（兼容旧调用方）。"""
    state = load_all_persist()
    accounts = state.get("accounts") or {}
    if not accounts:
        return {}
    first_key = next(iter(accounts))
    data = dict(accounts[first_key])
    if state.get("carids"):
        data["carids"] = state["carids"]
    return data


def save_persist(
    session: aiohttp.ClientSession,
    *,
    device_id: str,
    authenticated: bool,
    models: List[str],
    api_key_hint: str,
    session_authed_at: float = 0,
    carids: Optional[Dict[str, Any]] = None,
) -> None:
    """单账号扁平写入（兼容旧调用方）。"""
    payload: Dict[str, Any] = {
        "device_id": device_id,
        "authenticated": authenticated,
        "models": list(models),
        "api_key_hint": api_key_hint,
        "cookies": extract_cookie_state(session),
        "session_authed_at": session_authed_at,
        "updated": time.time(),
    }
    if carids is not None:
        payload["carids"] = carids
    content = json.dumps(payload, ensure_ascii=False, indent=2)
    existing = read_text_if_exists(PERSIST_PATH)
    if existing == content:
        return
    atomic_write_text(PERSIST_PATH, content)
