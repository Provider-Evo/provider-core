from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, List, Optional

from src.logger import get_logger

__all__ = ["ModelsCache"]
logger = get_logger(__name__)

_PERSIST_ROOT = Path(__file__).parent.parent.parent / "persist"


class ModelsCache:
    """平台模型列表缓存管理器。

    负责：
    1. 从 persist/{platform}/models.json 读取缓存
    2. 定时调用 fetch_fn 刷新远程模型列表
    3. 根据 fetch_enabled 决定覆盖或追加策略
    4. 更新后回调 on_update
    """

    def __init__(
        self,
        platform: str,
        fallback_models: List[str],
        fetch_enabled: bool = True,
    ) -> None:
        """初始化模型缓存。

        Args:
            platform: 平台标识名。
            fallback_models: 硬编码兜底模型列表。
            fetch_enabled: True=覆盖，False=只增不减。
        """
        self._platform = platform
        self._fallback = list(fallback_models)
        self._fetch_enabled = fetch_enabled
        self._models: List[str] = list(fallback_models)
        self._cache_path = _PERSIST_ROOT / platform / "models.json"
        self._refreshing = False

    async def load(self) -> List[str]:
        """从缓存文件加载模型列表。

        Returns:
            缓存的模型列表，无缓存则返回兜底列表。
        """
        try:
            if self._cache_path.is_file():
                text = self._cache_path.read_text(encoding="utf-8")
                data = json.loads(text)
                models = data.get("models", [])
                if models:
                    self._models = list(models)
                    logger.info(
                        "[%s] 从缓存加载 %d 个模型",
                        self._platform,
                        len(self._models),
                    )
        except Exception as e:
            logger.warning("[%s] 模型缓存加载失败: %s", self._platform, e)
        return list(self._models)

    async def save(self, models: List[str]) -> None:
        """保存模型列表到缓存文件。

        Args:
            models: 要保存的模型列表。
        """
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            data: dict = {"models": models, "updated_at": int(time.time())}
            self._cache_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("[%s] 模型缓存保存失败: %s", self._platform, e)

    def _merge(self, remote: List[str]) -> List[str]:
        """根据策略合并模型列表。

        Args:
            remote: 远程获取的模型列表。

        Returns:
            合并后的模型列表。
        """
        if self._fetch_enabled:
            return list(remote) if remote else list(self._models)
        existing = set(self._models)
        merged = list(self._models)
        for m in remote:
            if m not in existing:
                merged.append(m)
                existing.add(m)
        return merged

    async def start_refresh_loop(
        self,
        fetch_fn: Callable[[], Awaitable[List[str]]],
        interval: int = 86400,
        on_update: Optional[Callable[[List[str]], Awaitable[None]]] = None,
    ) -> None:
        """启动定时刷新循环（永久运行）。

        Args:
            fetch_fn: 异步函数，返回远程模型列表。
            interval: 刷新间隔（秒），默认 86400（24 小时）。
            on_update: 更新回调，接收新模型列表。
        """
        while True:
            await self._do_refresh(fetch_fn, on_update)
            await asyncio.sleep(interval)

    async def _do_refresh(
        self,
        fetch_fn: Callable[[], Awaitable[List[str]]],
        on_update: Optional[Callable[[List[str]], Awaitable[None]]] = None,
    ) -> None:
        """执行一次刷新。

        Args:
            fetch_fn: 异步函数，返回远程模型列表。
            on_update: 更新回调。
        """
        if self._refreshing:
            return
        self._refreshing = True
        try:
            remote = await fetch_fn()
            if remote:
                merged = self._merge(remote)
                self._models = merged
                await self.save(merged)
                if on_update is not None:
                    await on_update(merged)
                logger.info(
                    "[%s] 模型列表已刷新: %d 个", self._platform, len(merged)
                )
        except Exception as e:
            logger.warning("[%s] 模型列表刷新失败: %s", self._platform, e)
        finally:
            self._refreshing = False

    @property
    def models(self) -> List[str]:
        """当前模型列表。

        Returns:
            模型名列表。
        """
        return list(self._models)
