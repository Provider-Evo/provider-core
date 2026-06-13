# src/core/fncall/prompt/inject.py
"""协议感知的 fncall prompt 注入函数。

从 src/core/tools.py 的 inject_fncall 迁移，增加 protocol 参数，
将 prompt 渲染委托给 protocol.render_prompt()。
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from src.core.config import get_config
from src.core.fncall.base import ToolProtocol
from src.core.fncall.prompt.history import (
    _format_conversation_history,
    _normalize_messages,
)
from src.core.fncall.shared.loop_detect import (
    LoopDetectionResult,
    detect_tool_loop,
)
from src.core.fncall.shared.normalization import (
    format_tool_descs,
    normalize_content,
)
from src.core.fncall.shared.uuid7 import _uuid7
from src.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt 转储
# ---------------------------------------------------------------------------


def _maybe_dump_prompt(prompt: str) -> None:
    """若配置开启 print_prompt 或 record_prompt，将 prompt 写入 logs/prompts/ 目录。"""
    try:
        cfg = get_config()
        if not (cfg.fncall.print_prompt or cfg.fncall.record_prompt):
            return
    except Exception:
        return

    try:
        dump_dir = "logs/prompts"
        os.makedirs(dump_dir, exist_ok=True)
        dump_path = os.path.join(dump_dir, f"{_uuid7()}.txt")
        with open(dump_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        logger.debug("fncall prompt 已写入 %s", dump_path)
    except Exception as exc:
        logger.warning("写入 fncall prompt 失败: %s", exc)


# ---------------------------------------------------------------------------
# 核心注入函数
# ---------------------------------------------------------------------------


def inject_fncall(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    protocol: ToolProtocol,
    lang: str = "en",
    user_system_prompt: str = "",
    loop_detection_threshold: int = 3,
) -> List[Dict[str, Any]]:
    """将工具定义注入消息列表，构建为单条 user 消息送给 LLM。

    与原始 inject_fncall 不同，此版本接受一个 protocol 参数，
    将 prompt 渲染委托给 protocol.render_prompt()。
    """
    if not tools:
        return list(messages)

    normalized = _normalize_messages(list(messages))

    loop_warning: str = ""
    if loop_detection_threshold > 0:
        loop_result = detect_tool_loop(normalized, loop_detection_threshold)
        if loop_result.is_looping:
            logger.warning(
                "inject_fncall: 检测到工具调用循环（重复 %d 次，指纹=%s）",
                loop_result.repeat_count,
                loop_result.fingerprint,
            )
            loop_warning = loop_result.suggestion

    last_user_idx: Optional[int] = None
    for i in range(len(normalized) - 1, -1, -1):
        if (normalized[i].get("role") or "user") == "user":
            last_user_idx = i
            break

    if last_user_idx is not None:
        history_messages: List[Dict[str, Any]] = (
            normalized[:last_user_idx] + normalized[last_user_idx + 1:]
        )
        current_user_message: str = normalize_content(
            normalized[last_user_idx].get("content", "")
        )
    else:
        history_messages = normalized
        current_user_message = ""

    tool_descs = format_tool_descs(tools)
    history_text = _format_conversation_history(history_messages, protocol=protocol).strip()

    prompt = protocol.render_prompt(
        tool_descs=tool_descs,
        lang=lang,
        user_system_prompt=user_system_prompt,
        history_text=history_text,
        loop_warning=loop_warning,
        current_user_message=current_user_message,
    )

    _maybe_dump_prompt(prompt)

    return [{"role": "user", "content": prompt}]
