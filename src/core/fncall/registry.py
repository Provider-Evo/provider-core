"""协议注册 + 获取（复用 echotools，保留项目配置绑定）。"""
from __future__ import annotations

from typing import Dict, Optional

from echotools.fncall.registry import (
    _ensure_registered,
    _get_custom_protocol,
    _mapping_logged,
)
from src.logger import get_logger
from echotools.protocol.base import (
    ToolProtocol,
    _PROTOCOL_REGISTRY,
    get_protocol_by_id,
)

__all__ = ["get_protocol", "list_protocols"]

logger = get_logger(__name__)


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
    # 从项目配置自动补充缺省值
    try:
        from src.core.config import get_config
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
            default_protocol = "xml"

    # 优先级：protocol_id（API 请求显式指定）> fncall_mapping（管理员配置）> default_protocol（全局默认）
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
    return sorted(_PROTOCOL_REGISTRY.keys())
