"""跨进程共享内存通信层。"""
from __future__ import annotations

import json
import struct
from multiprocessing import shared_memory
from typing import Any, Optional

from src.logger import get_logger

logger = get_logger(__name__)

__all__ = ["SharedMemoryManager"]

# 共享内存默认大小（1MB）
_DEFAULT_SIZE = 1024 * 1024

# 头部长度（4 字节，存储数据长度）
_HEADER_SIZE = 4


class SharedMemoryManager:
    """管理跨进程共享内存的读写操作。

    数据格式：
    - 前 4 字节：uint32，存储后续数据的长度
    - 后续字节：JSON 序列化的数据
    """

    def __init__(self, name: str, size: int = _DEFAULT_SIZE, create: bool = True) -> None:
        """初始化共享内存。

        Args:
            name: 共享内存名称。
            size: 共享内存大小（字节）。
            create: 是否创建新的共享内存。False 时连接已存在的共享内存。
        """
        try:
            self._shm = shared_memory.SharedMemory(name=name, create=create, size=size)
            self._name = name
            self._size = size
            logger.debug("共享内存 [%s] 已初始化，大小: %d 字节", name, size)
        except FileNotFoundError:
            # 共享内存不存在，尝试创建
            logger.info("共享内存 [%s] 不存在，创建新实例", name)
            self._shm = shared_memory.SharedMemory(name=name, create=True, size=size)
            self._name = name
            self._size = size

    @property
    def name(self) -> str:
        """返回共享内存名称。"""
        return self._name

    def write(self, data: dict) -> None:
        """写入数据到共享内存。

        Args:
            data: 要写入的字典数据。
        """
        try:
            serialized = json.dumps(data, ensure_ascii=False).encode("utf-8")
            if len(serialized) + _HEADER_SIZE > self._size:
                logger.warning(
                    "数据大小 (%d 字节) 超过共享内存容量 (%d 字节)",
                    len(serialized) + _HEADER_SIZE,
                    self._size,
                )
                return

            header = struct.pack("<I", len(serialized))
            self._shm.buf[:_HEADER_SIZE] = header
            self._shm.buf[_HEADER_SIZE : _HEADER_SIZE + len(serialized)] = serialized
            logger.debug("已写入共享内存 [%s]，数据大小: %d 字节", self._name, len(serialized))
        except Exception as exc:
            logger.error("写入共享内存失败: %s", exc)

    def read(self) -> Optional[dict]:
        """从共享内存读取数据。

        Returns:
            读取的字典数据，如果为空则返回 None。
        """
        try:
            header = bytes(self._shm.buf[:_HEADER_SIZE])
            length = struct.unpack("<I", header)[0]
            if length == 0:
                return None

            data = bytes(self._shm.buf[_HEADER_SIZE : _HEADER_SIZE + length])
            return json.loads(data.decode("utf-8"))
        except Exception as exc:
            logger.error("读取共享内存失败: %s", exc)
            return None

    def close(self) -> None:
        """关闭共享内存（不删除）。"""
        try:
            self._shm.close()
            logger.debug("共享内存 [%s] 已关闭", self._name)
        except Exception as exc:
            logger.warning("关闭共享内存失败: %s", exc)

    def unlink(self) -> None:
        """删除共享内存。"""
        try:
            self._shm.unlink()
            logger.debug("共享内存 [%s] 已删除", self._name)
        except Exception as exc:
            logger.warning("删除共享内存失败: %s", exc)

    def __del__(self) -> None:
        """析构函数。"""
        self.close()
