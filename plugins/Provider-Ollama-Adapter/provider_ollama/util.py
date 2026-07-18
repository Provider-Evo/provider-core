"""
util 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-plugin.Provider-Ollama-Adapter.provider_ollama.util
- 文件名：util.py
- 父包：provider-plugin/Provider-Ollama-Adapter/provider_ollama

职责：

    提供运行期无关的小工具（路径解析、字符串转换、header 构造、
    payload 模板、SSE 解析等），由 ``provider_*.core.client`` 调用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


from typing import Any, Dict

from provider_ollama.core.adapter.client import (
    BASE_URL,
    CHAT_PATH,
    MAX_WORKERS,
    PAGE_SIZE,
    REFRESH_INTERVAL,
    TIMEOUT,
    OllamaClient,
    build_chat_payload,
    build_image_messages,
    build_registry,
    collect_servers,
    detect_capabilities,
    load_cache,
    needs_refresh,
    parse_ollama_line,
    save_cache,
)
from provider_ollama.core.constants import (
    CAPS,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
)


def build_headers(token: str = "") -> Dict[str, str]:
    """构建 Ollama 请求头。

    Ollama 为本地服务，无需认证头。此函数为接口规范兼容保留。

    Args:
        token: 未使用，仅为接口兼容保留。

    Returns:
        标准请求头字典。
    """
    return {"Content-Type": "application/json"}


def build_payload(
    messages: list,
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建 Ollama 聊天请求体（build_chat_payload 的别名）。

    Args:
        messages: Ollama 格式的消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 额外参数。

    Returns:
        请求体字典。
    """
    return build_chat_payload(messages, model, stream, **kw)


def parse_sse_line(data_str: str) -> Any:
    """解析 Ollama 流式响应行（parse_ollama_line 的别名）。

    Ollama 使用逐行 JSON 而非 SSE 格式。

    Args:
        data_str: JSON 字符串行。

    Returns:
        str（文本片段）、dict（usage）或 None（跳过）。
    """
    return parse_ollama_line(data_str.encode("utf-8"))


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 OllamaAdapter。"""
    if name in ("OllamaAdapter", "Adapter"):
        from provider_ollama.core.adapter.adaptercore import (  # noqa: PLC0415
            OllamaAdapter as _OllamaAdapter,
        )

        return _OllamaAdapter
    if name == "OllamaClient":
        return OllamaClient
    raise AttributeError(
        "module 'provider_ollama.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "OllamaAdapter",
    "Adapter",
    "OllamaClient",
    "BASE_URL",
    "CHAT_PATH",
    "PAGE_SIZE",
    "TIMEOUT",
    "MAX_WORKERS",
    "REFRESH_INTERVAL",
    "CAPS",
    "MODELS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
    "build_headers",
    "build_payload",
    "build_chat_payload",
    "build_image_messages",
    "parse_sse_line",
    "parse_ollama_line",
    "detect_capabilities",
    "collect_servers",
    "build_registry",
    "save_cache",
    "load_cache",
    "needs_refresh",
]

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

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
#
#     - 可扩展性：接口设计支持新字段或新行为的向后兼容追加。
