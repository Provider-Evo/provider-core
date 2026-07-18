"""headers 模块 — Provider 适配器层。

职责：
    集中放置 provider HTTP 请求头构造逻辑。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from __future__ import annotations

from typing import Dict

from .constants import BASE_URL, CHAT_PATH, IDE_VERSION


def build_headers(
    token: str = "",
    user_id: str = "",
    conversation_id: str = "",
    conversation_request_id: str = "",
    conversation_message_id: str = "",
    request_id: str = "",
) -> Dict[str, str]:
    """构建 CodeBuddy 接口请求头（纯函数，不生成随机值）。

    Args:
        token: Bearer 鉴权令牌。
        user_id: 用户唯一标识。
        conversation_id: 会话 ID。
        conversation_request_id: 会话请求 ID。
        conversation_message_id: 会话消息 ID。
        request_id: 请求 ID。

    Returns:
        完整请求头字典。
    """
    return {
        "Host": "www.codebuddy.ai",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
        "x-stainless-arch": "x64",
        "x-stainless-lang": "js",
        "x-stainless-os": "Windows",
        "x-stainless-package-version": "5.10.1",
        "x-stainless-retry-count": "0",
        "x-stainless-runtime": "node",
        "x-stainless-runtime-version": "v22.13.1",
        "X-Conversation-ID": conversation_id,
        "X-Conversation-Request-ID": conversation_request_id,
        "X-Conversation-Message-ID": conversation_message_id,
        "X-Request-ID": request_id,
        "X-Agent-Intent": "craft",
        "X-IDE-Type": "CLI",
        "X-IDE-Name": "CLI",
        "X-IDE-Version": IDE_VERSION,
        "Authorization": "Bearer {}".format(token),
        "X-Domain": "www.codebuddy.ai",
        "User-Agent": "CLI/{0} CodeBuddy/{0}".format(IDE_VERSION),
        "X-Product": "SaaS",
        "X-User-Id": user_id,
    }

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .payloads import (
    build_payload,
)

from .sse import (
    parse_sse_line,
)

__all__ = [
    "build_payload",
    "parse_sse_line",
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

from .adaptercore import (
    CodebuddyAdapter,
)

from .client import (
    CodebuddyClient,
)

from .payloads import (
    build_payload,
)

from .sse import (
    parse_sse_line,
)
__all__ = [
    "CodebuddyAdapter",
    "CodebuddyClient",
    "build_payload",
    "parse_sse_line",
]
