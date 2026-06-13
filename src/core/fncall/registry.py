# src/core/fncall/registry.py
"""协议注册 + 配置驱动的协议获取。

get_protocol() 从当前配置中读取 fncall.protocol 字段，返回对应的协议实例。
custom 协议需要配置中的 custom_prompt_en/zh，动态创建。
"""

from __future__ import annotations

from src.core.fncall.base import (
    ToolProtocol,
    _PROTOCOL_REGISTRY,
    get_protocol_by_id,
    register_protocol,
)
from src.logger import get_logger

logger = get_logger(__name__)

# custom 协议实例缓存
_custom_instance: ToolProtocol = None
_registered = False
# 平台映射日志去重
_mapping_logged: set[str] = set()


def _get_custom_protocol(
    prompt_en: str = "",
    prompt_zh: str = "",
) -> ToolProtocol:
    """获取或创建 custom 协议实例。"""
    global _custom_instance
    if _custom_instance is not None:
        return _custom_instance

    from src.core.fncall.protocols.custom import CustomProtocol

    _custom_instance = CustomProtocol(prompt_en=prompt_en, prompt_zh=prompt_zh)
    return _custom_instance


def _ensure_registered() -> None:
    """确保内置协议已注册（仅一次）。"""
    global _registered
    if _registered:
        return
    from src.core.fncall.protocols import _register_all  # noqa: F401

    _register_all()
    _registered = True


def get_protocol(
    protocol_id: str = "",
    custom_prompt_en: str = "",
    custom_prompt_zh: str = "",
    platform_id: str = "",
) -> ToolProtocol:
    """获取协议实例。

    Args:
        protocol_id: 协议 ID。为空时从配置读取。
        custom_prompt_en: custom 协议的英文 prompt 模板。
        custom_prompt_zh: custom 协议的中文 prompt 模板。
        platform_id: 平台 ID。用于查找 fncall_mapping 映射。

    Returns:
        ToolProtocol 实例。
    """
    from src.core.config import get_config

    cfg = get_config()

    if not protocol_id:
        # 先检查平台映射
        if platform_id and cfg.fncall.fncall_mapping:
            mapped = cfg.fncall.fncall_mapping.get(platform_id)
            if mapped:
                protocol_id = mapped
                mapping_key = f"{platform_id}:{protocol_id}"
                if mapping_key not in _mapping_logged:
                    logger.debug("平台 %s 映射到协议: %s", platform_id, protocol_id)
                    _mapping_logged.add(mapping_key)

        # 回退到全局协议
        if not protocol_id:
            protocol_id = cfg.fncall.protocol

    if protocol_id == "custom":
        return _get_custom_protocol(custom_prompt_en, custom_prompt_zh)

    _ensure_registered()
    return get_protocol_by_id(protocol_id)


def list_protocols() -> list:
    """返回所有已注册的协议 ID 列表。"""
    _ensure_registered()
    return sorted(_PROTOCOL_REGISTRY.keys())
