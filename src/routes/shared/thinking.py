from __future__ import annotations

"""思考链（reasoning / thinking）历史回传与请求解析。"""

from src.routes.shared.thinking_core import (
    ThinkingConfig,
    ThinkingLevel,
    ThinkingMode,
    apply_thinking_history_policy,
    extract_reasoning_text,
    level_to_thinking_mode,
    mode_to_thinking_level,
    normalize_thinking_level,
    normalize_thinking_mode,
)
from src.routes.shared.thinking_flavors import (
    resolve_include_thinking_in_history,
    resolve_thinking_config,
    thinking_to_dispatch_kwargs,
)

__all__ = [
    "level_to_thinking_mode",
    "mode_to_thinking_level",
    "normalize_thinking_level",
    "normalize_thinking_mode",
    "ThinkingLevel",
    "ThinkingMode",
    "ThinkingConfig",
    "apply_thinking_history_policy",
    "extract_reasoning_text",
    "resolve_include_thinking_in_history",
    "resolve_thinking_config",
    "thinking_to_dispatch_kwargs",
]
