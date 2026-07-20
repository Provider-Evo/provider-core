
import base64
import json
import os
import secrets
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.foundation.logger import get_logger
from src.foundation.paths import persist_dir as default_persist_dir

__all__ = ["SshCredentialVault", "get_ssh_vault"]

logger = get_logger(__name__)

_vault: Optional["SshCredentialVault"] = None


class SshCredentialVault:
    """持久化 SSH 连接凭据（XOR + 随机 key，避免 WS 明文传输）。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._key_path = self.root / ".vault.key"
        self._store_path = self.root / "connections.json"

    def _key(self) -> bytes:
        if not self._key_path.exists():
            self._key_path.write_bytes(os.urandom(32))
        return self._key_path.read_bytes()

    def _enc(self, plain: str) -> str:
        if not plain:
            return ""
        key = self._key()
        raw = plain.encode("utf-8")
        xored = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
        return base64.urlsafe_b64encode(xored).decode("ascii")

    def _dec(self, token: str) -> str:
        if not token:
            return ""
        key = self._key()
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
        plain = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
        return plain.decode("utf-8")

    def _load(self) -> Dict[str, Any]:
        if not self._store_path.exists():
            return {"connections": []}
        try:
            return json.loads(self._store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"connections": []}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self._store_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.debug("SSH vault save failed", exc_info=True)

    def list_public(self) -> List[Dict[str, Any]]:
        """List connections without secrets (for UI)."""
        out: List[Dict[str, Any]] = []
        for item in self._load().get("connections", []):
            out.append(
                {
                    "connection_id": item.get("connection_id"),
                    "name": item.get("name"),
                    "host": item.get("host"),
                    "port": item.get("port", 22),
                    "username": item.get("username"),
                    "has_key": bool(item.get("key_enc")),
                    "updated_at": item.get("updated_at"),
                }
            )
        return out

    def upsert(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str = "",
        key_data: str = "",
        name: Optional[str] = None,
        connection_id: Optional[str] = None,
    ) -> str:
        data = self._load()
        connections: List[Dict[str, Any]] = list(data.get("connections", []))
        cid = connection_id or secrets.token_urlsafe(12)
        now = time.time()
        entry = {
            "connection_id": cid,
            "name": name or f"{username}@{host}:{port}",
            "host": host,
            "port": port,
            "username": username,
            "password_enc": self._enc(password),
            "key_enc": self._enc(key_data.strip()),
            "updated_at": now,
        }
        replaced = False
        for idx, existing in enumerate(connections):
            if existing.get("connection_id") == cid:
                connections[idx] = entry
                replaced = True
                break
        if not replaced:
            connections.append(entry)
        data["connections"] = connections
        self._save(data)
        return cid

    def resolve(self, connection_id: str) -> Optional[Dict[str, str]]:
        for item in self._load().get("connections", []):
            if item.get("connection_id") != connection_id:
                continue
            return {
                "host": str(item.get("host", "")),
                "port": str(item.get("port", 22)),
                "username": str(item.get("username", "")),
                "password": self._dec(str(item.get("password_enc", ""))),
                "key_data": self._dec(str(item.get("key_enc", ""))),
                "name": str(item.get("name", "")),
            }
        return None

    def delete(self, connection_id: str) -> bool:
        data = self._load()
        before = list(data.get("connections", []))
        after = [c for c in before if c.get("connection_id") != connection_id]
        if len(after) == len(before):
            return False
        data["connections"] = after
        self._save(data)
        return True


def get_ssh_vault(root: Optional[Path] = None) -> SshCredentialVault:
    global _vault
    if _vault is not None:
        return _vault
    if root is None:
        root = default_persist_dir("terminal") / "vault"
    _vault = SshCredentialVault(root)
    return _vault
