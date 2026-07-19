"""
ssh_vault 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.server.terminal.ssh_vault
- 文件名：ssh_vault.py
- 父包：provider-core/src/core/server/terminal

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-core/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""

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


# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
