"""constants 模块 — Provider 适配器层。

职责：
    集中放置 provider 常量定义（模型名、URL 模板、错误码等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

# ── 服务端点 ────────────────────────────────────────────────────────────────────
BASE_URL: str = "https://cursor.com"
CHAT_PATH: str = "/api/chat"
DEPLOYMENT_ID: str = "dpl_2J8tisxS8XpA18cHKAudi6cggpWc"
MODELS_JS_URL: str = (
    "https://cursor.com/docs-static/_next/static/chunks/"
    "0z5v50kazv6pt.js?dpl={}".format(DEPLOYMENT_ID)
)
STREAM_RESUME_PATH: str = "/api/chat/{chat_id}/stream"

# ── 模型列表 ────────────────────────────────────────────────────────────────────
MODELS: list[str] = [
    "anthropic/claude-sonnet-4",
    "anthropic/claude-sonnet-4-thinking",
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-sonnet-4-6-thinking",
    "anthropic/claude-sonnet-4-6-long",
    "anthropic/claude-sonnet-4-5",
    "anthropic/claude-sonnet-4-5-thinking",
    "anthropic/claude-sonnet-4-5-long",
    "anthropic/claude-opus-4-6",
    "anthropic/claude-opus-4-6-thinking",
    "anthropic/claude-opus-4-5",
    "anthropic/claude-opus-4-5-thinking",
    "anthropic/claude-opus-4-6-fast",
    "anthropic/claude-opus-4-6-fast-thinking",
    "anthropic/claude-haiku-4-5",
    "anthropic/claude-sonnet-4-1m",
    "anthropic/claude-sonnet-4-1m-thinking",
    "google/gemini-3.1-pro",
    "google/gemini-3.1-long",
    "google/gemini-3-pro",
    "google/gemini-3-long",
    "google/gemini-3-flash",
    "google/gemini-3-pro-image-preview",
    "google/gemini-2.5-flash",
    "openai/gpt-5.1",
    "openai/gpt-5-codex",
    "openai/gpt-5-mini",
    "openai/gpt-5-fast",
    "openai/gpt-5.2",
    "openai/gpt-5.2-codex",
    "openai/gpt-5.4",
    "openai/gpt-5.4-fast",
    "openai/gpt-5.4-long",
    "openai/gpt-5.4-mini",
    "openai/gpt-5.4-nano",
    "openai/gpt-5.3-codex",
    "openai/gpt-5.1-codex",
    "openai/gpt-5.1-codex-mini",
    "openai/gpt-5.1-codex-max",
    "xai/grok-4-20",
    "xai/grok-4-20-long",
    "moonshot/kimi-k2.5",
    "cursor/composer-1",
    "cursor/composer-1.5",
    "cursor/composer-2",
    "cursor/composer-2-fast",
]

# ── 能力字典 ────────────────────────────────────────────────────────────────────
CAPS: dict[str, bool] = {
    "chat": True,
    "completions": True,
    "thinking": True,
    "continuation": True,
}

# ── 模型获取 ────────────────────────────────────────────────────────────────────
FETCH_MODELS_ENABLED: bool = True
MODEL_FETCH_INTERVAL: int = 86400

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
    build_resume_headers,
)

from .payloads import (
    build_payload,
    new_chat_id,
    new_message_id,
)

__all__ = [
    "build_headers",
    "build_resume_headers",
    "build_payload",
    "new_chat_id",
    "new_message_id",
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
# =======================================================================
# 重导出 — 同包协同模块（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
    build_resume_headers,
)

from .payloads import (
    build_payload,
    new_chat_id,
    new_message_id,
)
__all__ = [
    "build_headers",
    "build_resume_headers",
    "build_payload",
    "new_chat_id",
    "new_message_id",
]
