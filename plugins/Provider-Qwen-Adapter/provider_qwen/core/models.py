from __future__ import annotations

"""Qwen /api/v2/models 响应解析。"""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

_KEYS: Tuple[str, ...] = ("id", "modelId", "model_id", "name")


@dataclass
class QwenModelInfo:
    """单个 Qwen 模型的网关元数据。"""

    id: str
    name: str = ""
    context_length: Optional[int] = None
    chat: bool = True
    vision: bool = False
    thinking: bool = False
    search: bool = False
    image_gen: bool = False
    image_edit: bool = False
    video_gen: bool = False
    audio_gen: bool = False
    audio_in: bool = False
    artifacts: bool = False
    continuation: bool = False

    def capability_dict(self) -> Dict[str, bool]:
        return {
            key: bool(value)
            for key, value in asdict(self).items()
            if key not in ("id", "name", "context_length") and value
        }


def _iter_model_items(raw: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                yield item
            elif isinstance(item, str) and item.strip():
                yield {"id": item.strip()}
        return
    if not isinstance(raw, dict):
        return

    blocks: List[Any] = []
    data = raw.get("data")
    if isinstance(data, list):
        blocks.append(data)
    elif isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, list):
            blocks.append(inner)
        nested = data.get("models")
        if isinstance(nested, list):
            blocks.append(nested)
    simple = raw.get("models")
    if isinstance(simple, list):
        for item in simple:
            if isinstance(item, dict):
                yield item
            elif isinstance(item, str) and item.strip():
                yield {"id": item.strip()}

    for block in blocks:
        for item in block:
            if isinstance(item, dict):
                yield item
            elif isinstance(item, str) and item.strip():
                yield {"id": item.strip()}


def _model_id(item: Dict[str, Any]) -> Optional[str]:
    for key in _KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    info = item.get("info")
    if isinstance(info, dict):
        for key in _KEYS:
            value = info.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _int_field(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_model_item(item: Dict[str, Any]) -> Optional[QwenModelInfo]:
    model_id = _model_id(item)
    if not model_id:
        return None

    info = item.get("info") if isinstance(item.get("info"), dict) else {}
    meta = info.get("meta") if isinstance(info.get("meta"), dict) else {}
    caps = meta.get("capabilities") if isinstance(meta.get("capabilities"), dict) else {}
    chat_types = meta.get("chat_type") if isinstance(meta.get("chat_type"), list) else []
    chat_type_set = {str(x).lower() for x in chat_types}
    modalities = meta.get("modality") if isinstance(meta.get("modality"), list) else []
    modality_set = {str(x).lower() for x in modalities}
    mcp = meta.get("mcp") if isinstance(meta.get("mcp"), list) else []
    mcp_set = {str(x).lower() for x in mcp}

    display_name = str(item.get("name") or info.get("name") or model_id)
    context_length = _int_field(meta.get("max_context_length"))
    if context_length is None:
        context_length = _int_field(meta.get("context_length"))

    vision = bool(caps.get("vision")) or "image" in modality_set
    thinking = bool(caps.get("thinking"))
    search = bool(caps.get("search")) or "search" in chat_type_set
    video_gen = bool(caps.get("video")) or "t2v" in chat_type_set
    audio_gen = bool(caps.get("audio"))
    audio_in = audio_gen or "audio" in modality_set
    image_gen = "t2i" in chat_type_set or "image-generation" in mcp_set
    image_edit = "image_edit" in chat_type_set
    artifacts = "artifacts" in chat_type_set or "web_dev" in chat_type_set

    return QwenModelInfo(
        id=model_id,
        name=display_name,
        context_length=context_length,
        vision=vision,
        thinking=thinking,
        search=search,
        image_gen=image_gen,
        image_edit=image_edit,
        video_gen=video_gen,
        audio_gen=audio_gen,
        audio_in=audio_in,
        artifacts=artifacts,
        continuation=True,
    )


def parse_models_response(raw: Any) -> List[QwenModelInfo]:
    """解析 Qwen models 端点响应为模型元数据列表。"""
    result: List[QwenModelInfo] = []
    seen: Set[str] = set()
    for item in _iter_model_items(raw):
        parsed = _parse_model_item(item)
        if parsed is None or parsed.id in seen:
            continue
        seen.add(parsed.id)
        result.append(parsed)
    return result


def parse_models_catalog(raw: Any) -> Dict[str, QwenModelInfo]:
    """解析为 model_id → QwenModelInfo 索引。"""
    return {item.id: item for item in parse_models_response(raw)}


def catalog_to_persist(catalog: Dict[str, QwenModelInfo]) -> Dict[str, Dict[str, Any]]:
    return {model_id: asdict(info) for model_id, info in catalog.items()}


def catalog_from_persist(raw: Any) -> Dict[str, QwenModelInfo]:
    if not isinstance(raw, dict):
        return {}
    out: Dict[str, QwenModelInfo] = {}
    for model_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        fields = {k: payload[k] for k in QwenModelInfo.__dataclass_fields__ if k in payload}
        fields["id"] = str(model_id)
        out[model_id] = QwenModelInfo(**fields)
    return out


def extract_model_ids(raw: Any) -> List[str]:
    """从 models 响应提取去重后的 model id 列表。"""
    return [item.id for item in parse_models_response(raw)]


def union_capabilities(infos: Iterable[QwenModelInfo]) -> Dict[str, bool]:
    """合并多个模型能力为候选项级能力布尔字典。"""
    merged: Dict[str, bool] = {"chat": True}
    for info in infos:
        merged.update(info.capability_dict())
    return merged
