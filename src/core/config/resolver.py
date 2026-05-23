from __future__ import annotations

"""共享模型名称解析器。

从合并后的 model_mapping 配置中解析模型别名。
所有路由文件应使用此模块，而非各自实现 _resolve_model。
"""

from src.core.config import get_config

__all__ = ["resolve_model"]


def resolve_model(model: str, protocol: str = "openai") -> str:
    """使用合并后的 model_mapping 配置解析模型别名。

    优先级（已在配置加载时合并）：
    1. 协议级映射：[anthropic.model_mapping] / [openai.model_mapping]
    2. 根级协议映射：[model_mapping.anthropic] / [model_mapping.openai]
    3. 根级全局映射：[model_mapping] 中非 anthropic/openai 的键

    Args:
        model: 请求中的原始模型名。
        protocol: 协议名，"anthropic" 或 "openai"。

    Returns:
        映射后的模型名，若无映射则返回原始名。
    """
    cfg = get_config()
    mm = cfg.model_mapping
    protocol_map = getattr(mm, protocol, {})
    return protocol_map.get(model, model)
