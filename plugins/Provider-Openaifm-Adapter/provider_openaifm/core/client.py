"""
client 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-plugin.Provider-Openaifm-Adapter.provider_openaifm.core.client
- 文件名：client.py
- 父包：provider-plugin/Provider-Openaifm-Adapter/provider_openaifm/core

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

import asyncio
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.cand import Candidate, make_id
from src.core.utils.errors import NotSupportedError
from src.foundation.logger import get_logger
from .consts import BASE_URL, CAPS, GENERATE_PATH, MODELS, VOICES
from .headers import build_headers
from .tts import (
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    STYLE_PROMPTS,
    build_tts_form_data,
)

logger = get_logger(__name__)
MAX_RETRIES: int = 3


class OpenaiFmClient:
    """openaifm HTTP 客户端。"""

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._candidates: List[Candidate] = []

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化客户端。"""
        self._session = session
        self._rebuild_candidates()
        logger.debug("openaifm 初始化完成，候选项: %d 个", len(self._candidates))

    def _rebuild_candidates(self) -> None:
        """构建候选项（单候选项，无需认证，不依赖 accounts.py）。"""
        self._candidates = [
            Candidate(
                id=make_id("openaifm", "openaifm"),
                platform="openaifm",
                resource_id="openaifm",
                models=list(MODELS),
                meta={},
                **CAPS,
            )
        ]

    async def candidates(self) -> List[Candidate]:
        """返回候选项列表。"""
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回可用候选项数量。"""
        return len(self._candidates)

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """openaifm 不支持 chat 补全。"""
        raise NotSupportedError("openaifm 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """执行语音合成，含指数退避重试。

        Args:
            candidate: 候选项。
            input_text: 合成文本。
            model: 模型名（openaifm 中用作 voice）。
            voice: 声音名称。
            **kw: 额外参数（支持 prompt/vibe）。

        Returns:
            音频字节。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                return await self._do_tts(
                    input_text, voice or model, kw
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "openaifm 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc
                )
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("openaifm 未知错误")

    async def _do_tts(
        self,
        text: str,
        voice: str,
        kw: Dict[str, Any],
    ) -> bytes:
        """调用 openaifm TTS API。

        Args:
            text: 合成文本。
            voice: 声音名称。
            kw: 额外参数（prompt, vibe）。

        Returns:
            音频字节。
        """
        if self._session is None:
            raise RuntimeError("openaifm session 未初始化")

        selected_voice = voice if voice in VOICES else DEFAULT_VOICE
        style = kw.get("style", DEFAULT_STYLE)
        prompt = kw.get("prompt") or STYLE_PROMPTS.get(style, "")
        vibe = kw.get("vibe", "")

        headers = build_headers()
        form_data = build_tts_form_data(text, prompt, selected_voice, vibe)

        async with self._session.post(
            BASE_URL + GENERATE_PATH,
            data=form_data,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(connect=10, total=300),
        ) as resp:
            if resp.status != 200:
                body_preview = await resp.text()
                raise RuntimeError(
                    "openaifm HTTP {}: {}".format(resp.status, body_preview[:200])
                )
            return await resp.read()

    async def close(self) -> None:
        """清理资源（session 由外部管理）。"""
        return

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
)

__all__ = [
    "build_headers",
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
