# -*- coding: utf-8 -*-
"""领域模型与规约模块。

包含领域值对象(FileHash、TransferInfo)、实体(FileRecord)、
聚合根(TransferTask)以及规约模式(Specification 及其组合与具体实现)。
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from .exceptions import ValidationError
from .utils import generate_id

# ---------------------------------------------------------------------------
# 类型变量
# ---------------------------------------------------------------------------
T = TypeVar("T")


# ===========================================================================
# 领域值对象
# ===========================================================================

@dataclass(frozen=True)
class FileHash:
    """文件哈希值对象。

    Attributes:
        md5: MD5 十六进制摘要。
        sha1: SHA1 十六进制摘要。

    >>> fh = FileHash(md5="abc", sha1="def")
    >>> fh.md5
    'abc'
    """

    md5: str
    sha1: str

    def __post_init__(self) -> None:
        if not self.md5:
            raise ValidationError("MD5 哈希不能为空", field="md5", reason="空值")
        if not self.sha1:
            raise ValidationError("SHA1 哈希不能为空", field="sha1", reason="空值")

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {"md5": self.md5, "sha1": self.sha1}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileHash:
        """从字典反序列化。"""
        return cls(md5=data["md5"], sha1=data["sha1"])

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> FileHash:
        """从 JSON 字符串反序列化。"""
        return cls.from_dict(json.loads(raw))


@dataclass(frozen=True)
class TransferInfo:
    """传输信息值对象。

    Attributes:
        tid: 任务 ID。
        bid: Box ID。
        ufileid: 文件 ID。
        token: 共享令牌。

    >>> ti = TransferInfo(tid="t1", bid="b1", ufileid="u1")
    >>> ti.tid
    't1'
    """

    tid: str
    bid: str = ""
    ufileid: str = ""
    token: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {"tid": self.tid, "bid": self.bid, "ufileid": self.ufileid, "token": self.token}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferInfo:
        """从字典反序列化。"""
        return cls(
            tid=data.get("tid", ""),
            bid=data.get("bid", ""),
            ufileid=data.get("ufileid", ""),
            token=data.get("token", ""),
        )

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> TransferInfo:
        """从 JSON 反序列化。"""
        return cls.from_dict(json.loads(raw))


# ===========================================================================
# 领域实体
# ===========================================================================

@dataclass
class FileRecord:
    """文件记录实体。

    Attributes:
        id: 唯一标识。
        name: 文件名。
        size: 文件大小(字节)。
        hash_info: 文件哈希信息。
        status: 文件状态。
        created_at: 创建时间戳。

    >>> fr = FileRecord(name="test.txt", size=100, hash_info=FileHash(md5="a", sha1="b"))
    >>> fr.name
    'test.txt'
    """

    name: str
    size: int
    hash_info: FileHash | None = None
    status: str = "pending"
    id: str = field(default_factory=generate_id)
    created_at: float = field(default_factory=time.time)

    def mark_uploaded(self) -> None:
        """标记为已上传。"""
        self.status = "uploaded"

    def mark_failed(self, reason: str = "") -> None:
        """标记为失败。

        Args:
            reason: 失败原因。
        """
        self.status = f"failed: {reason}" if reason else "failed"

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "hash_info": self.hash_info.to_dict() if self.hash_info else None,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileRecord:
        """从字典反序列化。"""
        hi = FileHash.from_dict(data["hash_info"]) if data.get("hash_info") else None
        return cls(
            name=data["name"],
            size=data["size"],
            hash_info=hi,
            status=data.get("status", "pending"),
            id=data.get("id", generate_id()),
            created_at=data.get("created_at", time.time()),
        )

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> FileRecord:
        """从 JSON 反序列化。"""
        return cls.from_dict(json.loads(raw))


# ===========================================================================
# 聚合根
# ===========================================================================

@dataclass
class TransferTask:
    """传输任务聚合根。

    Attributes:
        id: 唯一标识。
        direction: 传输方向('upload'或'download')。
        files: 文件列表。
        transfer_info: 传输信息。
        events: 领域事件列表。

    >>> tt = TransferTask(direction="upload")
    >>> tt.add_file(FileRecord(name="a.txt", size=10))
    >>> len(tt.files)
    1
    """

    direction: str
    files: list[FileRecord] = field(default_factory=list)
    transfer_info: TransferInfo | None = None
    id: str = field(default_factory=generate_id)
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.direction not in ("upload", "download"):
            raise ValidationError(
                "传输方向必须为 'upload' 或 'download'",
                field="direction",
                value=self.direction,
            )

    def add_file(self, file_record: FileRecord) -> None:
        """添加文件到任务。

        Args:
            file_record: 文件记录。
        """
        self.files.append(file_record)
        self.events.append({
            "type": "file_added",
            "file_id": file_record.id,
            "file_name": file_record.name,
            "timestamp": time.time(),
        })

    def complete(self) -> None:
        """标记任务完成。"""
        for f in self.files:
            if "failed" not in f.status:
                f.mark_uploaded()
        self.events.append({
            "type": "task_completed",
            "task_id": self.id,
            "timestamp": time.time(),
        })

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "direction": self.direction,
            "files": [f.to_dict() for f in self.files],
            "transfer_info": self.transfer_info.to_dict() if self.transfer_info else None,
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferTask:
        """从字典反序列化。"""
        tt = cls(
            direction=data["direction"],
            id=data.get("id", generate_id()),
        )
        tt.files = [FileRecord.from_dict(fd) for fd in data.get("files", [])]
        if data.get("transfer_info"):
            tt.transfer_info = TransferInfo.from_dict(data["transfer_info"])
        tt.events = data.get("events", [])
        return tt


# ===========================================================================
# 规约模式 (Specification Pattern)
# ===========================================================================

class Specification(Generic[T]):
    """规约模式基类,支持 & | ~ 组合。

    >>> class IsPositiveSpec(Specification[int]):
    ...     def is_satisfied_by(self, candidate: int) -> bool:
    ...         return candidate > 0
    >>> class IsEvenSpec(Specification[int]):
    ...     def is_satisfied_by(self, candidate: int) -> bool:
    ...         return candidate % 2 == 0
    >>> spec = IsPositiveSpec() & IsEvenSpec()
    >>> spec.is_satisfied_by(4)
    True
    >>> spec.is_satisfied_by(-2)
    False
    """

    def is_satisfied_by(self, candidate: T) -> bool:
        """检查候选对象是否满足规约。

        Args:
            candidate: 候选对象。

        Returns:
            是否满足。
        """
        raise NotImplementedError("子类必须实现此方法")

    def __and__(self, other: Specification[T]) -> Specification[T]:
        return _AndSpec(self, other)

    def __or__(self, other: Specification[T]) -> Specification[T]:
        return _OrSpec(self, other)

    def __invert__(self) -> Specification[T]:
        return _NotSpec(self)


class _AndSpec(Specification[T]):
    """与规约。"""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class _OrSpec(Specification[T]):
    """或规约。"""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class _NotSpec(Specification[T]):
    """非规约。"""

    def __init__(self, spec: Specification[T]) -> None:
        self._spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)


class FileSizeSpec(Specification[FileRecord]):
    """文件大小规约: 检查文件大小是否不超过指定限制。

    Args:
        max_bytes: 最大字节数。

    >>> spec = FileSizeSpec(1024)
    >>> spec.is_satisfied_by(FileRecord(name="a.txt", size=500))
    True
    >>> spec.is_satisfied_by(FileRecord(name="b.bin", size=2000))
    False
    """

    def __init__(self, max_bytes: int) -> None:
        self._max = max_bytes

    def is_satisfied_by(self, candidate: FileRecord) -> bool:
        return candidate.size <= self._max


class FileNamePatternSpec(Specification[FileRecord]):
    """文件名正则规约。

    Args:
        pattern: 正则表达式模式。

    >>> spec = FileNamePatternSpec(r".*\\.txt$")
    >>> spec.is_satisfied_by(FileRecord(name="doc.txt", size=10))
    True
    """

    def __init__(self, pattern: str) -> None:
        self._re = re.compile(pattern)

    def is_satisfied_by(self, candidate: FileRecord) -> bool:
        return bool(self._re.match(candidate.name))
