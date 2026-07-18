from __future__ import annotations

"""会话元数据 CRUD 混入。"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.foundation.logger import get_logger

logger = get_logger(__name__)


class SessionMetadataMixin:
    """提供会话元数据的保存、加载、删除与遍历能力。"""

    def _load_existing_meta(self, meta_path: Path) -> Dict[str, Any]:
        if not meta_path.exists():
            return {}
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug("读取已有会话元数据失败，将覆盖: %s", meta_path, exc_info=True)
            return {}
        except Exception:
            logger.warning("读取会话元数据时发生意外错误，将覆盖: %s", meta_path, exc_info=True)
            return {}

    def _write_meta_file(
        self,
        meta_path: Path,
        data: Dict[str, Any],
        session_id: str,
        status: str,
    ) -> None:
        try:
            meta_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            logger.debug("会话元数据已保存: %s (status=%s)", session_id, status)
        except OSError:
            logger.debug("保存会话元数据失败: %s", session_id, exc_info=True)
        except Exception:
            logger.warning("保存会话元数据时发生意外错误: %s", session_id, exc_info=True)

    def save(
        self,
        session_id: str,
        pid: Optional[int] = None,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        shell: Optional[str] = None,
        cols: int = 80,
        rows: int = 24,
        kind: str = "local",
        ssh_config: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        status: str = "alive",
        backend: Optional[str] = None,
    ) -> None:
        """保存或更新会话元数据；env 仅记录键名不持久化值。"""
        meta_path = self._meta_path(session_id)
        data = self._load_existing_meta(meta_path)
        now = time.time()
        data.update({
            "session_id": session_id,
            "pid": pid,
            "cwd": cwd,
            "shell": shell,
            "cols": cols,
            "rows": rows,
            "kind": kind,
            "ssh_config": ssh_config,
            "name": name,
            "status": status,
            "updated_at": now,
        })
        if "created_at" not in data:
            data["created_at"] = now
        if env:
            data["_env_keys"] = sorted(env.keys())
        if backend is not None:
            data["backend"] = backend
        self._write_meta_file(meta_path, data, session_id, status)

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """加载会话元数据。"""
        meta_path = self._meta_path(session_id)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug("加载会话元数据失败: %s", session_id, exc_info=True)
            return None
        except Exception:
            logger.warning("加载会话元数据时发生意外错误: %s", session_id, exc_info=True)
            return None

    def delete(self, session_id: str) -> None:
        """删除会话元数据及离线输出文件。"""
        for path in (
            self._meta_path(session_id),
            self._output_path(session_id),
        ):
            try:
                if path.exists():
                    path.unlink()
                    logger.debug("已删除文件: %s", path)
            except OSError:
                logger.debug("删除文件失败: %s", path, exc_info=True)
            except Exception:
                logger.warning("删除文件时发生意外错误: %s", path, exc_info=True)

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有已持久化的会话元数据。"""
        results: List[Dict[str, Any]] = []
        for meta_path in sorted(self.persist_dir.glob("*.json")):
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                results.append(data)
            except (OSError, json.JSONDecodeError):
                logger.debug("跳过无法读取的元数据文件: %s", meta_path, exc_info=True)
            except Exception:
                logger.warning(
                    "读取元数据文件时发生意外错误，已跳过: %s",
                    meta_path,
                    exc_info=True,
                )
        return results

    def _meta_path(self, session_id: str) -> Path:
        """返回会话元数据文件路径。"""
        return self.persist_dir / "{0}.json".format(session_id)
