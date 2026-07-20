
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Optional, Tuple

from src.foundation.logger import get_logger
from src.foundation.paths import persist_dir as default_persist_dir

__all__ = ["KnownHostsStore", "get_known_hosts_store", "host_key_fingerprint"]

logger = get_logger(__name__)

_store: Optional["KnownHostsStore"] = None


def host_key_fingerprint(key: object) -> str:
    """Return SHA256 fingerprint string for display (``SHA256:...``)."""
    try:
        import paramiko

        if isinstance(key, paramiko.PKey):
            digest = hashlib.sha256(key.asbytes()).digest()
            encoded = base64.b64encode(digest).decode("ascii").rstrip("=")
            return f"SHA256:{encoded}"
    except Exception:
        pass
    return "unknown"


class KnownHostsStore:
    """Minimal known_hosts persistence (one line per host:port)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _lines(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        mapping: dict[str, str] = {}
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 2)
                if len(parts) < 3:
                    continue
                mapping[parts[0]] = parts[2]
        except OSError:
            logger.debug("read known_hosts failed", exc_info=True)
        return mapping

    def lookup(self, host: str, port: int) -> Optional[str]:
        return self._lines().get(f"[{host}]:{port}") or self._lines().get(host)

    def trust(self, host: str, port: int, key_type: str, key_body: str) -> None:
        label = f"[{host}]:{port}" if port != 22 else host
        line = f"{label} {key_type} {key_body}\n"
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            logger.debug("write known_hosts failed", exc_info=True)

    def verify_or_raise(
        self,
        host: str,
        port: int,
        remote_key: object,
    ) -> Tuple[bool, str]:
        """Return ``(trusted, fingerprint)``; raises if unknown and strict."""
        import paramiko

        fp = host_key_fingerprint(remote_key)
        if not isinstance(remote_key, paramiko.PKey):
            return True, fp
        key_type = remote_key.get_name()
        key_body = remote_key.get_base64()
        stored = self.lookup(host, port)
        if stored is None:
            return False, fp
        expected = f"{key_type} {key_body}"
        if stored.strip() != expected:
            raise paramiko.SSHException(
                f"Host key mismatch for {host}:{port} (expected stored key, got {fp})"
            )
        return True, fp


def get_known_hosts_store(path: Optional[Path] = None) -> KnownHostsStore:
    global _store
    if _store is not None:
        return _store
    if path is None:
        path = default_persist_dir("terminal") / "known_hosts"
    _store = KnownHostsStore(path)
    return _store
