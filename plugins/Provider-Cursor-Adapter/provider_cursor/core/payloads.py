"""payloads 模块 — Provider 适配器层。

职责：
    集中放置 provider 请求 payload 模板与序列化函数。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


def build_payload(
    cursor_messages: List[Dict[str, Any]],
    chat_id: str,
    *,
    model: Optional[str] = None,
    message_id: Optional[str] = None,
    context: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    """构建 Cursor /api/chat 请求体（AI SDK DefaultChatTransport 形态）。

    Args:
        cursor_messages: Cursor UIMessage 列表。
        chat_id: 会话 ID（``crypto.randomUUID()``）。
        model: 模型 ID（网关路由用，服务端可能忽略）。
        message_id: 可选触发消息 ID。
        context: 可选文档上下文块。

    Returns:
        请求体字典。
    """
    body: Dict[str, Any] = {
        "id": chat_id,
        "messages": cursor_messages,
        "trigger": "submit-message",
    }
    if model:
        body["model"] = model
    if message_id:
        body["messageId"] = message_id
    if context:
        body["context"] = context
    return body


def new_chat_id() -> str:
    """生成新的 chatId。"""
    return str(uuid.uuid4())


def new_message_id() -> str:
    """生成新的 messageId。"""
    return str(uuid.uuid4())

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .headers import (
    build_headers,
    build_resume_headers,
)

__all__ = [
    "build_headers",
    "build_resume_headers",
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
__all__ = [
    "build_headers",
    "build_resume_headers",
]
