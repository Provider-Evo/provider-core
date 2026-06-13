"""fncall 注入 — 复用 echotools inject_fncall，附加项目配置驱动的 prompt 转储。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from echotools.fncall.prompt.inject import inject_fncall as _echotools_inject
from echotools.protocol.base import ToolProtocol

__all__ = ["inject_fncall"]


def _get_dump_dir() -> Optional[str]:
    try:
        from src.core.config import get_config
        cfg = get_config()
        if cfg.fncall.print_prompt or cfg.fncall.record_prompt:
            return "logs/prompts"
    except Exception:
        pass
    return None


def inject_fncall(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    protocol: ToolProtocol,
    lang: str = "en",
    user_system_prompt: str = "",
    loop_detection_threshold: int = 3,
    dump_prompt: bool = True,
) -> List[Dict[str, Any]]:
    dump_dir = _get_dump_dir() if dump_prompt else None
    return _echotools_inject(
        messages=messages,
        tools=tools,
        protocol=protocol,
        lang=lang,
        user_system_prompt=user_system_prompt,
        loop_detection_threshold=loop_detection_threshold,
        dump_prompt=dump_dir is not None,
        dump_dir=dump_dir,
    )
