
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.foundation.logger import get_logger
from src.foundation.paths import persist_dir as default_persist_dir

__all__ = ["CommonCommandsStore", "get_commands_store"]

logger = get_logger(__name__)

_store: Optional["CommonCommandsStore"] = None


class CommonCommandsStore:
    """持久化终端常用命令列表（单一 JSON 文件）。"""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._store_path = self.root / "commands.json"

    def _load(self) -> Dict[str, Any]:
        if not self._store_path.exists():
            return {"commands": []}
        try:
            return json.loads(self._store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.debug(
                "常用命令读取失败，回退为空: %s", self._store_path, exc_info=True
            )
            return {"commands": []}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self._store_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.debug("常用命令写入失败: %s", self._store_path, exc_info=True)

    def list_all(self) -> List[Dict[str, Any]]:
        """列出所有常用命令。"""
        return list(self._load().get("commands", []))

    def upsert(
        self,
        *,
        name: str,
        command: str,
        auto_enter: bool = False,
        command_id: Optional[str] = None,
    ) -> str:
        """新增或更新一条常用命令，返回 command_id。"""
        data = self._load()
        commands: List[Dict[str, Any]] = list(data.get("commands", []))
        cid = command_id or uuid.uuid4().hex
        now = time.time()
        replaced = False
        for idx, existing in enumerate(commands):
            if existing.get("id") == cid:
                entry = dict(existing)
                entry["name"] = name
                entry["command"] = command
                entry["auto_enter"] = auto_enter
                entry["updated_at"] = now
                commands[idx] = entry
                replaced = True
                break
        if not replaced:
            commands.append(
                {
                    "id": cid,
                    "name": name,
                    "command": command,
                    "auto_enter": auto_enter,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        data["commands"] = commands
        self._save(data)
        return cid

    def delete(self, command_id: str) -> bool:
        """删除一条常用命令，返回是否找到并删除。"""
        data = self._load()
        before = list(data.get("commands", []))
        after = [c for c in before if c.get("id") != command_id]
        if len(after) == len(before):
            return False
        data["commands"] = after
        self._save(data)
        return True

    def export_all(self) -> Dict[str, Any]:
        """导出全部常用命令供 JSON 下载。"""
        return {"commands": self.list_all()}

    def import_many(self, commands: List[Dict[str, Any]]) -> int:
        """批量导入常用命令；按 id 匹配则更新，否则新增。返回导入数量。"""
        count = 0
        for item in commands:
            name = str(item.get("name", ""))
            command = str(item.get("command", ""))
            cid = item.get("id")
            auto_enter = bool(item.get("auto_enter", False))
            self.upsert(
                name=name, command=command, auto_enter=auto_enter, command_id=cid
            )
            count += 1
        return count


def get_commands_store(root: Optional[Path] = None) -> CommonCommandsStore:
    """获取或创建模块级 CommonCommandsStore 单例。"""
    global _store
    if _store is not None:
        return _store
    if root is None:
        root = default_persist_dir("terminal", "commands")
    _store = CommonCommandsStore(root)
    return _store
