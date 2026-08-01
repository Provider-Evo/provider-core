
from __future__ import annotations

from typing import Dict, Optional

from echotools.exec.fncall.registry import _ensure_registered, _mapping_logged
from echotools.exec.protocol.base import (
    ToolProtocol,
    get_protocol_by_id,
)

from src.foundation.logger import get_logger

__all__ = [
    "get_protocol",
    "list_protocols",
    "set_custom_protocol_factory",
    "clear_custom_protocol_factory",
]

logger = get_logger(__name__)

_custom_factory = None
_custom_instance: Optional[ToolProtocol] = None


def set_custom_protocol_factory(factory) -> None:
    global _custom_factory, _custom_instance
    _custom_factory = factory
    _custom_instance = None


def clear_custom_protocol_factory() -> None:
    global _custom_factory, _custom_instance
    _custom_factory = None
    _custom_instance = None


def _get_custom_protocol(
    prompt_en: str = "", prompt_zh: str = ""
) -> ToolProtocol:
    global _custom_instance
    if _custom_instance is not None:
        return _custom_instance
    if _custom_factory is not None:
        _custom_instance = _custom_factory(prompt_en, prompt_zh)
        return _custom_instance
    raise ValueError("custom 协议未注册；请启用 Provider-Fncall-Util 插件")


def get_protocol(
    protocol_id: str = "",
    *,
    default_protocol: str = "",
    custom_prompt_en: str = "",
    custom_prompt_zh: str = "",
    platform_id: str = "",
    mapping: Optional[Dict[str, str]] = None,
) -> ToolProtocol:
    """获取协议（自动从项目配置读取默认协议和平台映射）。"""
    try:
        from src.foundation.config import get_config

        _fc = get_config().fncall
        if not default_protocol:
            default_protocol = _fc.protocol
        if not mapping and platform_id:
            mapping = _fc.fncall_mapping
        if not custom_prompt_en:
            custom_prompt_en = getattr(_fc, "custom_prompt_en", "") or ""
        if not custom_prompt_zh:
            custom_prompt_zh = getattr(_fc, "custom_prompt_zh", "") or ""
    except Exception:
        if not default_protocol:
            default_protocol = "entml"

    if not protocol_id:
        if platform_id and mapping:
            mapped = mapping.get(platform_id)
            if mapped:
                key = f"{platform_id}:{mapped}"
                if key not in _mapping_logged:
                    logger.debug("平台 %s -> 协议 %s", platform_id, mapped)
                    _mapping_logged.add(key)
                protocol_id = mapped
        if not protocol_id:
            protocol_id = default_protocol
    if protocol_id == "custom":
        return _get_custom_protocol(custom_prompt_en, custom_prompt_zh)
    _ensure_registered()
    return get_protocol_by_id(protocol_id)


def list_protocols() -> list:
    """全部协议 ID。"""
    _ensure_registered()
    from echotools.exec.protocol.base import _PROTOCOL_REGISTRY

    return sorted(_PROTOCOL_REGISTRY.keys())
