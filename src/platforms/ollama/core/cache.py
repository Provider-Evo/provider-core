from __future__ import annotations

"""Ollama 服务器发现缓存持久化。"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Tuple

from .constants import REFRESH_INTERVAL

_SRV_FILE: Path = Path("persist/ollama/servers.json")
_REG_FILE: Path = Path("persist/ollama/registry.json")


def save_cache(servers: Dict[str, Any], registry: Dict[str, Any]) -> None:
    """保存服务器和注册表到本地文件。

    使用原子写模式（先写 .tmp 再 os.replace）。

    Args:
        servers: 服务器字典。
        registry: 模型注册表。
    """
    for f in (_SRV_FILE, _REG_FILE):
        f.parent.mkdir(parents=True, exist_ok=True)

    tmp = str(_SRV_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            {"servers": servers, "last_refresh": time.time()},
            f,
            indent=2,
        )
    os.replace(tmp, str(_SRV_FILE))

    tmp = str(_REG_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            {"models": registry, "last_refresh": time.time()},
            f,
            indent=2,
        )
    os.replace(tmp, str(_REG_FILE))


def load_cache() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """从本地文件加载服务器和注册表。

    Returns:
        (服务器字典, 模型注册表) 元组。
    """
    srv: Dict[str, Any] = {}
    reg: Dict[str, Any] = {}
    if _SRV_FILE.exists():
        try:
            srv = json.loads(
                _SRV_FILE.read_text(encoding="utf-8")
            ).get("servers", {})
        except Exception:
            srv = {}
    if _REG_FILE.exists():
        try:
            reg = json.loads(
                _REG_FILE.read_text(encoding="utf-8")
            ).get("models", {})
        except Exception:
            reg = {}
    return srv, reg


def needs_refresh() -> bool:
    """判断是否需要重新发现服务器。

    Returns:
        True 表示需要刷新。
    """
    if not _SRV_FILE.exists():
        return True
    try:
        d = json.loads(_SRV_FILE.read_text(encoding="utf-8"))
        return time.time() - d.get("last_refresh", 0) >= REFRESH_INTERVAL
    except Exception:
        return True
