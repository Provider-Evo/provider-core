from __future__ import annotations

"""会话清理混入。"""

import time

from src.foundation.logger import get_logger

logger = get_logger(__name__)


class SessionCleanupMixin:
    """提供过期会话清理能力。"""

    def cleanup_stale(
        self,
        destroyed_max_age_seconds: int = 86400,
        alive_max_age_seconds=None,
    ) -> int:
        """清除过期会话；可选清理长期存活但无 registry 的 alive 元数据。"""
        count = 0
        now = time.time()
        for meta in self.list_all():
            status = meta.get("status")
            updated = meta.get("updated_at", 0)
            sid = meta.get("session_id", "")
            if status == "destroyed" and now - updated > destroyed_max_age_seconds:
                self.delete(sid)
                count += 1
                logger.info("已清理过期 destroyed 会话: %s", sid)
                continue
            if (
                alive_max_age_seconds is not None
                and status == "alive"
                and now - updated > alive_max_age_seconds
            ):
                self.save(session_id=sid, status="stale", kind=meta.get("kind", "local"))
                count += 1
                logger.info("已标记 stale 会话: %s", sid)
        return count

    def save_output_seq(self, session_id: str, seq: int) -> None:
        meta_path = self._meta_path(session_id)
        data = self._load_existing_meta(meta_path)
        if not data:
            data = {"session_id": session_id}
        data["output_seq"] = seq
        data["updated_at"] = time.time()
        self._write_meta_file(meta_path, data, session_id, data.get("status", "alive"))

    def get_output_seq(self, session_id: str) -> int:
        meta = self.load(session_id)
        if not meta:
            return 0
        try:
            return int(meta.get("output_seq", 0))
        except (TypeError, ValueError):
            return 0

    def cleanup_stale_legacy(self, max_age_seconds: int = 86400) -> int:
        return self.cleanup_stale(destroyed_max_age_seconds=max_age_seconds)
