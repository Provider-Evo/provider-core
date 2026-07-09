from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core import Candidate
from src.foundation.logger import get_logger
from src.platforms.capabilities import (
    DefaultAudioMixin,
    DefaultEmbeddingMixin,
    DefaultImageMixin,
    DefaultModerationMixin,
)

__all__ = ["PlatformAdapter"]
logger = get_logger(__name__)

DEFAULT_CONTEXT_LENGTH = 131072

# Moderation category constants
MODERATION_CATEGORIES = {
    "sexual": False,
    "hate": False,
    "harassment": False,
    "self-harm": False,
    "sexual/minors": False,
    "hate/threatening": False,
    "violence/graphic": False,
    "self-harm/intent": False,
    "self-harm/instructions": False,
    "harassment/threatening": False,
    "violence": False,
}

MODERATION_CATEGORY_SCORES = {
    "sexual": 0.0,
    "hate": 0.0,
    "harassment": 0.0,
    "self-harm": 0.0,
    "sexual/minors": 0.0,
    "hate/threatening": 0.0,
    "violence/graphic": 0.0,
    "self-harm/intent": 0.0,
    "self-harm/instructions": 0.0,
    "harassment/threatening": 0.0,
    "violence": 0.0,
}


class PlatformAdapter(
    DefaultEmbeddingMixin,
    DefaultImageMixin,
    DefaultAudioMixin,
    DefaultModerationMixin,
    ABC,
):
    """所有平台适配器的抽象基类。

    设计原则：
    - init() 必须立即返回，不允许阻塞
    - 耗时操作（登录、token 刷新、模型拉取）在后台 Task 中执行
    - candidates() 随时返回当前真实状态
    - 子类按需覆盖可选能力方法；基类默认返回标准空结果，而非抛出异常
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """平台标识名（小写，与目录名一致）。

        Returns:
            平台名字符串。
        """
        ...

    @property
    def supported_models(self) -> List[str]:
        """支持的模型列表（硬编码兜底 + 动态更新）。

        Returns:
            模型名列表。
        """
        return []

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """默认能力字典，用于 /v1/models 输出。

        Returns:
            能力字典。
        """
        return {"chat": True}

    @property
    def context_length(self) -> Optional[int]:
        """上下文长度（默认 128k）。

        Returns:
            最大上下文 token 数或 None。
        """
        return DEFAULT_CONTEXT_LENGTH

    @abstractmethod
    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——必须立即返回。

        耗时操作（登录、验证、模型拉取）应启动后台 Task 异步完成。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        ...

    @abstractmethod
    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项列表（反映实时状态）。

        Returns:
            候选项列表。
        """
        ...

    @abstractmethod
    async def ensure_candidates(self, count: int) -> int:
        """确保至少有 count 个候选项可用。

        Args:
            count: 期望候选项数量。

        Returns:
            当前实际可用数量。
        """
        ...

    @abstractmethod
    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """聊天补全（yield 协议：str 或 dict）。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用 thinking 模式。
            search: 是否启用搜索。
            **kw: 额外参数（temperature、top_p 等）。

        Yields:
            str（文本增量）或 dict（thinking/usage/tool_calls）。
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """关闭适配器，释放资源（后台 Task 需取消）。"""
        ...

    # ── 可选能力方法（Default*Mixin 提供 no-op 默认实现）────────────────────

    async def fetch_remote_models(self) -> List[str]:
        """拉取远程模型列表（子类按需覆盖）。"""
        return []

    async def create_rerank(
        self,
        candidate: Candidate,
        query: str,
        documents: List[str],
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """重排序（默认按原始顺序返回，子类覆盖实现）。

        Args:
            candidate: 候选项。
            query: 查询文本。
            documents: 文档列表。
            model: 模型名。
            **kw: 额外参数。

        Returns:
            重排序结果字典（results/meta 标准格式）。
        """
        return {
            "results": [
                {
                    "index": i,
                    "document": {"text": doc},
                    "relevance_score": 1.0 - i * 0.01,
                }
                for i, doc in enumerate(documents)
            ],
            "meta": {
                "api_version": {"version": "1"},
                "billed_units": {"search_units": len(documents)},
            },
        }

    async def create_video(
        self,
        candidate: Candidate,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """视频生成（默认返回空结果，子类覆盖实现）。

        Args:
            candidate: 候选项。
            prompt: 提示词。
            model: 模型名。
            **kw: 额外参数。

        Returns:
            视频生成结果字典（created/data 标准格式）。
        """

        return {
            "created": int(time.time()),
            "data": [],
        }

    # ── 代理切换方法（可选，默认无操作）──────────────

    def set_proxy_enabled(self, enabled: bool) -> None:
        """设置此平台的代理覆盖开关（可选，默认无操作）。

        只有在 config.toml 的 [platforms_proxy].enabled_platforms 列表中
        的平台才能真正生效，否则无论怎么调用都是无操作。

        Args:
            enabled: True 强制使用代理，False 强制不使用。
        """
        pass

    def is_proxy_allowed(self) -> bool:
        """返回此平台是否被允许使用代理切换。

        由 ``[platforms_proxy]`` 的 ``enabled_platforms`` 与 ``group_list_type``
        共同决定（白名单：仅列表内；黑名单：仅列表外）。

        Returns:
            是否允许代理切换。
        """
        return False

    def is_proxy_enabled(self) -> bool:
        """返回此平台当前是否启用代理覆盖（可选）。

        Returns:
            是否启用代理。
        """
        return False
