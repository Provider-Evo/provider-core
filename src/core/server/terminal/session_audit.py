"""
session_audit 模块。

职责：
    终端会话审计日志索引——记录会话开始时间、host、kind 与状态变更，
    供 WebUI 录像审计功能查询、分页列出、删除。不触碰离线输出文件。

对外接口：
    ``__all__`` 列出对外可导入的符号集合。

依赖：
    仅依赖 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.foundation.logger import get_logger
from src.foundation.paths import persist_dir as default_persist_dir

__all__ = ["SessionAuditStore", "get_audit_store"]

logger = get_logger(__name__)

_store: Optional["SessionAuditStore"] = None


class SessionAuditStore:
    """持久化终端会话审计日志（单一 JSON 文件索引）。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._store_path = self.root / "audit_log.json"

    def _load(self) -> Dict[str, Any]:
        if not self._store_path.exists():
            return {"entries": []}
        try:
            return json.loads(self._store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug("审计日志读取失败，回退为空: %s", self._store_path, exc_info=True)
            return {"entries": []}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self._store_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.debug("审计日志写入失败: %s", self._store_path, exc_info=True)

    def record_start(self, session_id: str, host: str, kind: str) -> None:
        """记录会话开始的审计条目。"""
        data = self._load()
        entries: List[Dict[str, Any]] = list(data.get("entries", []))
        now = time.time()
        entries.append({
            "session_id": session_id,
            "host": host,
            "kind": kind,
            "login_time": now,
            "status": "alive",
            "updated_at": now,
        })
        data["entries"] = entries
        self._save(data)

    def record_status(self, session_id: str, status: str) -> None:
        """更新已存在审计条目的状态。"""
        data = self._load()
        entries: List[Dict[str, Any]] = list(data.get("entries", []))
        for entry in entries:
            if entry.get("session_id") == session_id:
                entry["status"] = status
                entry["updated_at"] = time.time()
                break
        data["entries"] = entries
        self._save(data)

    def list_page(self, page: int, page_size: int) -> Dict[str, Any]:
        """按 login_time 降序分页返回审计条目。"""
        entries = list(self._load().get("entries", []))
        entries.sort(key=lambda e: e.get("login_time", 0), reverse=True)
        total = len(entries)
        page = max(1, page)
        page_size = max(1, page_size)
        start = (page - 1) * page_size
        items = entries[start:start + page_size]
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        """按 session_id 返回单条审计条目，未找到返回 None。"""
        for entry in self._load().get("entries", []):
            if entry.get("session_id") == session_id:
                return entry
        return None

    def delete(self, session_id: str) -> bool:
        """删除单条审计条目，返回是否找到并删除。"""
        data = self._load()
        before = list(data.get("entries", []))
        after = [e for e in before if e.get("session_id") != session_id]
        if len(after) == len(before):
            return False
        data["entries"] = after
        self._save(data)
        return True


def get_audit_store(root: Optional[Path] = None) -> SessionAuditStore:
    """获取或创建模块级 SessionAuditStore 单例。"""
    global _store
    if _store is not None:
        return _store
    if root is None:
        root = default_persist_dir("terminal", "audit")
    _store = SessionAuditStore(root)
    return _store
