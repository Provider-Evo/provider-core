# -*- coding: utf-8 -*-
"""仓储模块。

提供抽象仓储接口(AbstractRepository)与两个内存实现:
InMemoryFileRecordRepository、InMemoryTransferTaskRepository。
"""
from __future__ import annotations

import abc
from typing import Generic, TypeVar

from .domain import FileRecord, TransferTask

# ---------------------------------------------------------------------------
# 类型变量
# ---------------------------------------------------------------------------
TEntity = TypeVar("TEntity")


# ===========================================================================
# 抽象仓储
# ===========================================================================

class AbstractRepository(abc.ABC, Generic[TEntity]):
    """抽象仓储接口。"""

    @abc.abstractmethod
    def save(self, entity: TEntity) -> None:
        """保存实体。"""

    @abc.abstractmethod
    def find_by_id(self, entity_id: str) -> TEntity | None:
        """根据 ID 查找实体。"""

    @abc.abstractmethod
    def find_all(self) -> list[TEntity]:
        """查找所有实体。"""

    @abc.abstractmethod
    def delete(self, entity_id: str) -> bool:
        """删除实体,返回是否成功。"""

    @abc.abstractmethod
    def exists(self, entity_id: str) -> bool:
        """检查实体是否存在。"""


# ===========================================================================
# 内存仓储实现
# ===========================================================================

class InMemoryFileRecordRepository(AbstractRepository[FileRecord]):
    """文件记录内存仓储实现。

    >>> repo = InMemoryFileRecordRepository()
    >>> fr = FileRecord(name="test.txt", size=100)
    >>> repo.save(fr)
    >>> repo.exists(fr.id)
    True
    >>> repo.find_by_id(fr.id).name
    'test.txt'
    >>> repo.delete(fr.id)
    True
    """

    def __init__(self) -> None:
        self._store: dict[str, FileRecord] = {}

    def save(self, entity: FileRecord) -> None:
        """保存文件记录。"""
        self._store[entity.id] = entity

    def find_by_id(self, entity_id: str) -> FileRecord | None:
        """根据 ID 查找。"""
        return self._store.get(entity_id)

    def find_all(self) -> list[FileRecord]:
        """获取所有记录。"""
        return list(self._store.values())

    def delete(self, entity_id: str) -> bool:
        """删除记录。"""
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False

    def exists(self, entity_id: str) -> bool:
        """检查是否存在。"""
        return entity_id in self._store


class InMemoryTransferTaskRepository(AbstractRepository[TransferTask]):
    """传输任务内存仓储实现。

    >>> repo = InMemoryTransferTaskRepository()
    >>> tt = TransferTask(direction="upload")
    >>> repo.save(tt)
    >>> repo.exists(tt.id)
    True
    """

    def __init__(self) -> None:
        self._store: dict[str, TransferTask] = {}

    def save(self, entity: TransferTask) -> None:
        """保存任务。"""
        self._store[entity.id] = entity

    def find_by_id(self, entity_id: str) -> TransferTask | None:
        """根据 ID 查找。"""
        return self._store.get(entity_id)

    def find_all(self) -> list[TransferTask]:
        """获取所有任务。"""
        return list(self._store.values())

    def delete(self, entity_id: str) -> bool:
        """删除任务。"""
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False

    def exists(self, entity_id: str) -> bool:
        """检查是否存在。"""
        return entity_id in self._store
