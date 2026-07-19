"""local_store 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 local_store 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import json
import os
from typing import Dict, Optional, Union

from src.foundation.logger import get_logger
from src.foundation.paths import persist_json_dir

LOCAL_STORE_FILE_PATH = str(persist_json_dir() / "local_store.json")
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
