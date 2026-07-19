"""
client 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-plugin.Provider-Gtts-Adapter.provider_gtts.core.client
- 文件名：client.py
- 父包：provider-plugin/Provider-Gtts-Adapter/provider_gtts/core

职责：

    提供运行期凭证占位（API keys / accounts / session cookies 等）。
    真实凭证由 git 仓库外的 accounts.py 或 .env-like override 提供；
    本文件只暴露字段名与默认空值，供 SDK 与插件入口在导入失败时回退。

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


import asyncio
from typing import Any, Dict, List, Optional

import aiohttp

from src.core.dispatch.cand import Candidate, make_id
from src.foundation.logger import get_logger
from .consts import CAPS, MODELS
from .stream.tts import TtsService

logger = get_logger(__name__)

# gTTS 为公开接口，无需真实凭证；保留占位候选项以复用候选项调度逻辑。
API_KEYS: List[Optional[str]] = [None]


class Client:
    """gTTS HTTP 协调器。"""

    def __init__(self) -> None:
        """初始化协调器。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._candidates: List[Candidate] = []
        self._bg_tasks: List[asyncio.Task] = []
        self._closing: bool = False
        # 子服务在 init_immediate() 中实例化
        self._tts: Optional[TtsService] = None

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即执行的初始化。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        self._rebuild_candidates()
        self._build_services(session)
        logger.debug("gtts 初始化完成")

    def _build_services(self, session: aiohttp.ClientSession) -> None:
        """构建子服务实例。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._tts = TtsService(
            session=session,
            proxy_resolver=self._get_proxy_kwarg,
        )

    def _get_proxy_kwarg(self) -> Optional[str]:
        """返回代理 URL 或 None（gTTS 通常不使用代理）。

        Returns:
            代理 URL 或 None。
        """
        return None

    def _rebuild_candidates(self) -> None:
        """根据当前账号状态重建候选项列表。"""
        self._candidates = [
            Candidate(
                id=make_id("gtts", (key or "gtts")[:12]),
                platform="gtts",
                resource_id=(key or "gtts")[:12],
                models=list(MODELS),
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
        ]

    async def candidates(self) -> List[Candidate]:
        """返回候选列表。

        Returns:
            候选项列表。
        """
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """确保候选数量。

        Args:
            count: 期望候选数量。

        Returns:
            实际候选数量。
        """
        return len(API_KEYS)

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """语音合成委托给 TTS 服务。

        Args:
            candidate: 候选项。
            input_text: 输入文本。
            model: 模型名。
            voice: 声音名（保留参数）。
            **kw: 额外参数。

        Returns:
            音频字节。

        Raises:
            RuntimeError: 客户端未初始化时抛出。
        """
        if self._tts is None:
            raise RuntimeError("gtts 客户端未初始化")
        return await self._tts.synthesize(candidate, input_text)

    async def close(self) -> None:
        """关闭客户端，取消后台任务。"""
        self._closing = True
        for task in self._bg_tasks:
            task.cancel()
        for task in self._bg_tasks:
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("gtts 后台任务已取消")

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
)

from .payload import (
    build_payload,
)

__all__ = [
    "build_headers",
    "build_payload",
]

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
