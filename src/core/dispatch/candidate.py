from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = ["Candidate", "make_id", "ALL_CAPABILITIES", "context_for_model", "filter_candidates_by_context"]


def context_for_model(candidate: "Candidate", model: str) -> Optional[int]:
    """返回候选项对指定模型的有效上下文长度。"""
    meta = candidate.meta if isinstance(candidate.meta, dict) else {}
    model_context = meta.get("model_context")
    if isinstance(model_context, dict) and model in model_context:
        raw = model_context.get(model)
        if raw is not None:
            return int(raw)
    return candidate.context_length


def filter_candidates_by_context(
    candidates: List["Candidate"],
    model: str,
    min_context: int,
) -> List["Candidate"]:
    """筛掉已知上下文不足的候选项；未暴露长度视为满足；全被筛掉则回退全部。"""
    if min_context <= 0:
        return list(candidates)
    kept: List[Candidate] = []
    for cand in candidates:
        ctx = context_for_model(cand, model)
        if ctx is None or ctx >= min_context:
            kept.append(cand)
    return kept if kept else list(candidates)


ALL_CAPABILITIES: tuple = (
    "chat",
    "vision",
    "image_gen",
    "image_edit",
    "image_variation",
    "video_gen",
    "audio_gen",
    "audio_in",
    "audio_transcription",
    "audio_translation",
    "embedding",
    "research",
    "thinking",
    "search",
    "code_exec",
    "artifacts",
    "tools",
    "native_tools",
    "upload",
    "continuation",
    "moderation",
    "rerank",
    "batch",
    "fine_tuning",
    "files",
    "assistants",
    "threads",
    "runs",
    "vector_stores",
    "realtime",
    "responses",
)


def make_id(platform: str, resource_id: str = "") -> str:
    """生成候选项 ID。

    提供 resource_id 时生成确定性 ID（重启后不变），
    否则回退到随机 UUID。

    Args:
        platform: 平台标识名。
        resource_id: 平台资源标识（可选）。

    Returns:
        ID 字符串，格式 {platform}_{hash12}。
    """
    if resource_id:
        h = hashlib.sha256(
            "{}:{}".format(platform, resource_id).encode()
        ).hexdigest()[:12]
        return "{}_{}".format(platform, h)
    return "{}_{}".format(platform, uuid.uuid4().hex[:12])


@dataclass
class Candidate:
    """候选项，包含全部能力布尔字段及元数据。"""

    id: str
    platform: str
    resource_id: str

    # 核心能力
    chat: bool = False
    vision: bool = False
    tools: bool = False
    native_tools: bool = False
    thinking: bool = False
    search: bool = False
    continuation: bool = False

    # 生成能力
    image_gen: bool = False
    image_edit: bool = False
    image_variation: bool = False
    video_gen: bool = False
    audio_gen: bool = False

    # 音频输入
    audio_in: bool = False
    audio_transcription: bool = False
    audio_translation: bool = False

    # 向量与检索
    embedding: bool = False
    rerank: bool = False

    # 高级能力
    research: bool = False
    code_exec: bool = False
    artifacts: bool = False
    moderation: bool = False
    responses: bool = False

    # 文件与存储
    upload: bool = False
    files: bool = False
    vector_stores: bool = False

    # 批处理与微调
    batch: bool = False
    fine_tuning: bool = False

    # Assistants API
    assistants: bool = False
    threads: bool = False
    runs: bool = False

    # 实时
    realtime: bool = False

    # 上下文长度（None=未知）
    context_length: Optional[int] = None

    # 元数据
    models: List[str] = field(default_factory=list)
    available: bool = True
    busy: bool = False
    cooldown: float = 0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def has_capability(self, cap: str) -> bool:
        """检查是否具备指定能力。

        Args:
            cap: 能力名称。

        Returns:
            是否具备该能力。
        """
        return bool(getattr(self, cap, False))

    def to_model_dict(self, owned_by: str = "") -> Dict[str, Any]:
        """转换为 /v1/models 响应中的模型条目格式。

        Args:
            owned_by: 所属平台名。

        Returns:
            模型字典。
        """
        caps: Dict[str, bool] = {}
        for cap in ALL_CAPABILITIES:
            val = getattr(self, cap, False)
            if val:
                caps[cap] = True

        result: Dict[str, Any] = {
            "object": "model",
            "created": int(time.time()),
            "owned_by": owned_by or self.platform,
            "capabilities": caps,
        }
        if self.context_length is not None:
            result["context_length"] = self.context_length
        return result
