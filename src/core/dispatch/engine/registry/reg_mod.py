"""平台注册表 — /v1/models 格式的模型聚合逻辑。"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.core.dispatch.cand import ALL_CAPABILITIES, Candidate
from src.foundation.logger import get_logger

__all__ = ["RegistryModelsMixin"]
logger = get_logger(__name__)


def _merge_candidate_caps(
    cand: Candidate, model_caps: Dict[str, Dict[str, bool]], model_ctx: Dict[str, int]
) -> None:
    cand_caps = {cap: True for cap in ALL_CAPABILITIES if getattr(cand, cap, False)}
    meta = cand.meta
    per_model_ctx = meta.get("model_context") if isinstance(meta, dict) else None
    per_model_caps = meta.get("model_capabilities") if isinstance(meta, dict) else None

    for model_name in cand.models or []:
        merged = model_caps.setdefault(model_name, {})
        merged.update(cand_caps)
        if isinstance(per_model_caps, dict):
            caps_for_model = per_model_caps.get(model_name)
            if isinstance(caps_for_model, dict):
                merged.update(
                    {key: True for key, value in caps_for_model.items() if value}
                )

        ctx_val: Optional[int] = None
        if isinstance(per_model_ctx, dict) and model_name in per_model_ctx:
            ctx_val = int(per_model_ctx[model_name])
        elif cand.context_length is not None:
            ctx_val = int(cand.context_length)
        if ctx_val is not None:
            prev = model_ctx.get(model_name)
            model_ctx[model_name] = max(prev, ctx_val) if prev is not None else ctx_val


def _build_model_entry(
    model_name: str,
    platform: str,
    default_caps: Dict[str, Any],
    model_caps: Dict[str, Dict[str, bool]],
    model_ctx: Dict[str, int],
    ctx_len: Optional[int],
) -> Dict[str, Any]:
    caps = dict(default_caps)
    caps.update(model_caps.get(model_name, {}))
    lower = model_name.lower()
    if "whisper" in lower or "transcribe" in lower:
        caps["audio_transcription"] = True
    entry: Dict[str, Any] = {
        "id": model_name,
        "object": "model",
        "created": int(time.time()),
        "owned_by": platform,
        "capabilities": caps,
    }
    per_ctx = model_ctx.get(model_name)
    if per_ctx is not None:
        entry["context_length"] = per_ctx
    elif ctx_len is not None:
        entry["context_length"] = ctx_len
    return entry


class RegistryModelsMixin:
    """/v1/models 格式的模型聚合。"""

    async def _collect_platform_model_meta(
        self, adapter: Any, platform: str
    ) -> "tuple[Dict[str, Dict[str, bool]], Dict[str, int]]":
        model_caps: Dict[str, Dict[str, bool]] = {}
        model_ctx: Dict[str, int] = {}
        try:
            candidates = await adapter.candidates()
        except Exception as exc:
            logger.debug("读取平台 [%s] 候选项失败: %s", platform, exc)
            return model_caps, model_ctx

        for cand in candidates:
            if not isinstance(cand, Candidate):
                continue
            _merge_candidate_caps(cand, model_caps, model_ctx)
        return model_caps, model_ctx

    async def all_models(self) -> List[Dict[str, Any]]:
        """收集所有模型及其能力信息（/v1/models 格式）。"""
        out: List[Dict[str, Any]] = []
        seen: set = set()
        for a in self.adapters.values():
            platform = a.name if hasattr(a, "name") else ""
            default_caps = (
                dict(a.default_capabilities)
                if hasattr(a, "default_capabilities")
                else {}
            )
            ctx_len = a.context_length if hasattr(a, "context_length") else None

            model_caps, model_ctx = await self._collect_platform_model_meta(a, platform)

            try:
                model_names = list(a.supported_models)
            except Exception as exc:
                logger.warning("读取平台 [%s] 模型列表失败: %s", platform, exc)
                continue

            for m in model_names:
                if m in seen:
                    continue
                seen.add(m)
                out.append(
                    _build_model_entry(
                        m, platform, default_caps, model_caps, model_ctx, ctx_len
                    )
                )
        return out

    async def list_models(self) -> List[Dict[str, Any]]:
        return await self.all_models()
