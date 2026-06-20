from __future__ import annotations

"""Terminal session persistence store.

Persists terminal session metadata and offline output to disk so that
shell processes survive server restarts and clients can reconnect to
existing sessions.

Storage layout::

    persist/terminal/
        {session_id}.json      -- session metadata
        {session_id}.output    -- rolling offline output log
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default maximum offline output file size in bytes (5 MB).
_DEFAULT_MAX_OUTPUT_BYTES: int = 5 * 1024 * 1024

# Default retention for destroyed sessions (seconds).
_DEFAULT_DESTROYED_RETENTION: int = 300  # 5 minutes for undo-close


class TerminalSessionStore:
    """Persists terminal session metadata and offline output.

    Parameters
    ----------
    persist_dir:
        Directory where session files are stored.  Created if it does
        not exist.
    max_output_bytes:
        Maximum size of the offline output file per session.  When the
        file exceeds this limit, the oldest content is trimmed.
    """

    def __init__(
        self,
        persist_dir: Path,
        max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self.persist_dir = persist_dir
        self.max_output_bytes = max_output_bytes
        self.persist_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Metadata CRUD
    # ------------------------------------------------------------------

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
    ) -> None:
        """Save or update session metadata."""
        meta_path = self._meta_path(session_id)
        data: Dict[str, Any] = {}
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.debug("Failed to read existing session metadata: %s", meta_path, exc_info=True)
                data = {}
            except Exception:
                logger.warning("Unexpected error reading session metadata: %s", meta_path, exc_info=True)
                data = {}

        data.update(
            {
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
                "updated_at": time.time(),
            }
        )
        # Only set created_at on first save
        if "created_at" not in data:
            data["created_at"] = data["updated_at"]

        # Do NOT persist env vars (may contain secrets)
        # Store a sanitized marker instead
        if env:
            data["_env_keys"] = list(env.keys())

        try:
            meta_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.debug("Failed to save session metadata", exc_info=True)
        except Exception:
            logger.warning("Unexpected error saving session metadata", exc_info=True)

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session metadata.  Returns ``None`` if not found."""
        meta_path = self._meta_path(session_id)
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug("Failed to load session metadata: %s", session_id, exc_info=True)
            return None
        except Exception:
            logger.warning("Unexpected error loading session metadata: %s", session_id, exc_info=True)
            return None

    def delete(self, session_id: str) -> None:
        """Delete session metadata and offline output."""
        for path in (self._meta_path(session_id), self._output_path(session_id)):
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                logger.debug("Failed to delete %s", path, exc_info=True)
            except Exception:
                logger.warning("Unexpected error deleting %s", path, exc_info=True)

    def list_all(self) -> List[Dict[str, Any]]:
        """List all persisted session metadata."""
        results: List[Dict[str, Any]] = []
        for meta_path in sorted(self.persist_dir.glob("*.json")):
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
                results.append(data)
            except (OSError, json.JSONDecodeError):
                logger.debug("Failed to read %s", meta_path, exc_info=True)
            except Exception:
                logger.warning("Unexpected error reading %s", meta_path, exc_info=True)
        return results

    # ------------------------------------------------------------------
    # Offline output management
    # ------------------------------------------------------------------

    def append_output(self, session_id: str, chunk: str) -> None:
        """Append a chunk of terminal output to the offline buffer.

        The output file is trimmed to ``max_output_bytes`` by removing
        the oldest content when it exceeds the limit.
        """
        output_path = self._output_path(session_id)
        try:
            with open(output_path, "a", encoding="utf-8") as f:
                f.write(chunk)

            # Trim if exceeded max size
            if output_path.exists():
                size = output_path.stat().st_size
                if size > self.max_output_bytes:
                    self._trim_output(output_path, size)
        except OSError:
            logger.debug("Failed to append offline output", exc_info=True)
        except Exception:
            logger.warning("Unexpected error appending offline output", exc_info=True)

    def get_offline_output(self, session_id: str) -> str:
        """Read the full offline output buffer."""
        output_path = self._output_path(session_id)
        if not output_path.exists():
            return ""
        try:
            return output_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            logger.debug("Failed to read offline output: %s", session_id, exc_info=True)
            return ""
        except Exception:
            logger.warning("Unexpected error reading offline output: %s", session_id, exc_info=True)
            return ""

    def clear_offline_output(self, session_id: str) -> None:
        """Clear the offline output buffer."""
        output_path = self._output_path(session_id)
        try:
            if output_path.exists():
                output_path.unlink()
        except OSError:
            logger.debug("Failed to clear offline output", exc_info=True)
        except Exception:
            logger.warning("Unexpected error clearing offline output", exc_info=True)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_stale(self, max_age_seconds: int = 86400) -> int:
        """Remove sessions that have been destroyed for longer than *max_age_seconds*.

        Returns the number of sessions cleaned up.
        """
        count = 0
        now = time.time()
        for meta in self.list_all():
            if meta.get("status") == "destroyed":
                updated = meta.get("updated_at", 0)
                if now - updated > max_age_seconds:
                    self.delete(meta["session_id"])
                    count += 1
        return count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _meta_path(self, session_id: str) -> Path:
        return self.persist_dir / f"{session_id}.json"

    def _output_path(self, session_id: str) -> Path:
        return self.persist_dir / f"{session_id}.output"

    def _trim_output(self, path: Path, current_size: int) -> None:
        """Trim the output file to fit within max_output_bytes.

        Removes the oldest content by reading the file, keeping only
        the last ``max_output_bytes`` bytes, and rewriting.
        """
        try:
            # Read the tail portion that fits
            with open(path, "rb") as f:
                f.seek(max(0, current_size - self.max_output_bytes))
                tail = f.read()
            with open(path, "wb") as f:
                f.write(tail)
        except OSError:
            logger.debug("Failed to trim output file", exc_info=True)
        except Exception:
            logger.warning("Unexpected error trimming output file", exc_info=True)


# ------------------------------------------------------------------
# Module-level singleton (initialized on first use)
# ------------------------------------------------------------------

_store: Optional[TerminalSessionStore] = None


def get_terminal_store(persist_dir: Optional[Path] = None) -> TerminalSessionStore:
    """Get or create the module-level TerminalSessionStore singleton.

    If *persist_dir* is ``None``, uses the default persist directory
    relative to the project root.
    """
    global _store
    if _store is not None:
        return _store

    if persist_dir is None:
        # Default: <project_root>/persist/terminal/
        project_root = Path(__file__).resolve().parent.parent.parent
        persist_dir = project_root / "persist" / "terminal"

    _store = TerminalSessionStore(persist_dir)
    return _store
