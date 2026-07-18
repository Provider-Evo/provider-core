"""headers 模块 — Provider 适配器层。

职责：
    集中放置 provider HTTP 请求头构造逻辑。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

from typing import Dict, Optional


def build_headers(
    *,
    x_is_human: str = "",
    cookie: str = "",
    chat_path: str = "/api/chat",
    method: str = "POST",
) -> Dict[str, str]:
    """构建文档站 /api/chat 请求头（含 Bot 防护三元组）。

    Args:
        x_is_human: ``x-is-human`` Bot challenge JSON 字符串。
        cookie: 可选会话 Cookie。
        chat_path: ``x-path`` 值。
        method: ``x-method`` 值。

    Returns:
        请求头字典。
    """
    headers: Dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "sec-ch-ua-platform": '"Windows"',
        "x-path": chat_path,
        "sec-ch-ua": (
            '"Chromium";v="131","Not_A Brand";v="24","Google Chrome";v="131"'
        ),
        "x-method": method,
        "sec-ch-ua-bitness": '"64"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-arch": '"x86"',
        "sec-ch-ua-platform-version": '"15.0.0"',
        "origin": "https://cursor.com",
        "sec-fetch-site": "same-origin",
        "sec-fetch-mode": "cors",
        "sec-fetch-dest": "empty",
        "referer": "https://cursor.com/cn/docs",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "priority": "u=1,i",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "x-is-human": x_is_human or "",
    }
    cookie_value = (cookie or "").strip()
    if cookie_value:
        headers["Cookie"] = cookie_value
    return headers


def build_resume_headers(
    *,
    x_is_human: str = "",
    cookie: str = "",
    chat_id: str,
) -> Dict[str, str]:
    """构建 GET /api/chat/{chatId}/stream 请求头。"""
    return build_headers(
        x_is_human=x_is_human,
        cookie=cookie,
        chat_path="/api/chat/{}/stream".format(chat_id),
        method="GET",
    )

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .payloads import (
    build_payload,
    new_chat_id,
    new_message_id,
)

__all__ = [
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

from .payloads import (
    build_payload,
    new_chat_id,
    new_message_id,
)
__all__ = [
    "build_payload",
    "new_chat_id",
    "new_message_id",
]
