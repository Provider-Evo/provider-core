"""payloads 模块 — Provider 适配器层。

职责：
    集中放置 provider 请求 payload 模板与序列化函数。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import Any, Dict, List


def _extract_content_parts(
    content: List[Any],
) -> "tuple[List[str], List[str]]":
    """从多模态消息内容中提取文本片段与 base64 图片数据。"""
    text_parts: List[str] = []
    images: List[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            text_parts.append(part.get("text", ""))
            continue
        if part.get("type") != "image_url":
            continue
        url = part.get("image_url", {}).get("url", "")
        if url.startswith("data:") and ";base64," in url:
            images.append(url.split(";base64,", 1)[1])
    return text_parts, images


def build_image_messages(
    messages: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """将 OpenAI 格式的消息转换为 Ollama 格式。

    处理多模态消息中的 image_url，提取 base64 数据。

    Args:
        messages: OpenAI 格式的消息列表。

    Returns:
        Ollama 格式的消息列表。
    """
    if not messages:
        return []

    result: List[Dict[str, Any]] = []
    for msg in messages:
        content = msg.get("content", "")
        role = msg.get("role", "user")

        if isinstance(content, str):
            result.append({"role": role, "content": content})
            continue

        if isinstance(content, list):
            text_parts, images = _extract_content_parts(content)
            entry: Dict[str, Any] = {
                "role": role,
                "content": "\n".join(text_parts),
            }
            if images:
                entry["images"] = images
            result.append(entry)
            continue

        result.append({"role": role, "content": str(content)})

    return result


def build_chat_payload(
    messages: List[Dict[str, Any]],
    model: str = "",
    stream: bool = True,
    **kw: Any,
) -> Dict[str, Any]:
    """构建 Ollama 聊天请求体。

    Args:
        messages: Ollama 格式的消息列表。
        model: 模型名。
        stream: 是否流式。
        **kw: 额外参数（temperature, top_p, max_tokens, stop）。

    Returns:
        请求体字典。
    """
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": stream,
    }

    opts: Dict[str, Any] = {}
    if kw.get("temperature") is not None:
        opts["temperature"] = kw["temperature"]
    if kw.get("top_p") is not None:
        opts["top_p"] = kw["top_p"]
    if kw.get("max_tokens") is not None:
        opts["num_predict"] = kw["max_tokens"]
    if kw.get("stop"):
        opts["stop"] = kw["stop"]
    if opts:
        payload["options"] = opts

    return payload

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .sse import (
    parse_ollama_line,
)

__all__ = [
    "parse_ollama_line",
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

from .sse import (
    parse_ollama_line,
)
__all__ = [
    "parse_ollama_line",
]
