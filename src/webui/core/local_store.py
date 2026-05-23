from __future__ import annotations

"""WebUI 本地存储。"""

import json
import os
from typing import Dict, Optional, Union

from src.logger import get_logger

LOCAL_STORE_FILE_PATH = "data/local_store.json"
logger = get_logger(__name__)
StoreValue = Union[str, list, dict, int, float, bool]

__all__ = ["LOCAL_STORE_FILE_PATH", "LocalStoreManager", "local_storage"]


class LocalStoreManager:
    """JSON 本地存储管理器。"""

    def __init__(self, local_store_path: Optional[str] = None) -> None:
        self.file_path = local_store_path or LOCAL_STORE_FILE_PATH
        self.store: Dict[str, StoreValue] = {}
        self.load_local_store()

    def __getitem__(self, item: str) -> Optional[StoreValue]:
        return self.store.get(item)

    def __setitem__(self, key: str, value: StoreValue) -> None:
        self.store[key] = value
        self.save_local_store()

    def __delitem__(self, key: str) -> None:
        if key in self.store:
            del self.store[key]
            self.save_local_store()
        else:
            logger.warning("尝试删除不存在的键: %s", key)

    def __contains__(self, item: str) -> bool:
        return item in self.store

    def load_local_store(self) -> None:
        """加载本地存储。"""
        if os.path.exists(self.file_path):
            logger.debug("加载本地存储数据: %s", self.file_path)
            try:
                with open(self.file_path, "r", encoding="utf-8") as file_obj:
                    self.store = json.load(file_obj)
            except json.JSONDecodeError:
                logger.warning("本地存储 JSON 损坏，正在重建: %s", self.file_path)
                self.store = {}
                self.save_local_store()
            return
        logger.info("本地存储不存在，正在创建: %s", self.file_path)
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        self.save_local_store()

    def save_local_store(self) -> None:
        """保存本地存储。"""
        logger.debug("保存本地存储数据: %s", self.file_path)
        with open(self.file_path, "w", encoding="utf-8") as file_obj:
            json.dump(self.store, file_obj, ensure_ascii=False, indent=4)


local_storage = LocalStoreManager(LOCAL_STORE_FILE_PATH)
