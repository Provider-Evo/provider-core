from __future__ import annotations

"""平台可选能力 Protocol 与默认 no-op mixin。"""

import time
import uuid as _uuid
from typing import Any, Dict, List, Protocol, Union, runtime_checkable

from src.core import Candidate

__all__ = [
    "EmbeddingCapable",
    "ImageCapable",
    "AudioCapable",
    "ModerationCapable",
    "DefaultEmbeddingMixin",
    "DefaultImageMixin",
    "DefaultAudioMixin",
    "DefaultModerationMixin",
]


@runtime_checkable
class EmbeddingCapable(Protocol):
    async def create_embedding(
        self,
        candidate: Candidate,
        input_data: Union[str, List[str]],
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]: ...


@runtime_checkable
class ImageCapable(Protocol):
    async def create_image(
        self, candidate: Candidate, prompt: str, model: str, **kw: Any,
    ) -> Dict[str, Any]: ...


@runtime_checkable
class AudioCapable(Protocol):
    async def create_speech(
        self, candidate: Candidate, input_text: str, model: str, voice: str, **kw: Any,
    ) -> bytes: ...


@runtime_checkable
class ModerationCapable(Protocol):
    async def create_moderation(
        self,
        candidate: Candidate,
        input_data: Union[str, List[str]],
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]: ...


class DefaultEmbeddingMixin:
    async def create_embedding(
        self,
        candidate: Candidate,
        input_data: Union[str, List[str]],
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        inputs = [input_data] if isinstance(input_data, str) else list(input_data)
        return {
            "object": "list",
            "data": [
                {"object": "embedding", "index": i, "embedding": []}
                for i, _ in enumerate(inputs)
            ],
            "model": model,
            "usage": {"prompt_tokens": 0, "total_tokens": 0},
        }


class DefaultImageMixin:
    async def create_image(
        self, candidate: Candidate, prompt: str, model: str, **kw: Any,
    ) -> Dict[str, Any]:
        return {"created": int(time.time()), "data": []}

    async def edit_image(
        self, candidate: Candidate, image: bytes, prompt: str, model: str, **kw: Any,
    ) -> Dict[str, Any]:
        return {"created": int(time.time()), "data": []}

    async def create_image_variation(
        self, candidate: Candidate, image: bytes, model: str, **kw: Any,
    ) -> Dict[str, Any]:
        return {"created": int(time.time()), "data": []}


class DefaultAudioMixin:
    async def create_speech(
        self, candidate: Candidate, input_text: str, model: str, voice: str, **kw: Any,
    ) -> bytes:
        return b""

    async def create_transcription(
        self, candidate: Candidate, audio: bytes, model: str, **kw: Any,
    ) -> Dict[str, Any]:
        return {"text": ""}

    async def create_translation(
        self, candidate: Candidate, audio: bytes, model: str, **kw: Any,
    ) -> Dict[str, Any]:
        return {"text": ""}


class DefaultModerationMixin:
    async def create_moderation(
        self,
        candidate: Candidate,
        input_data: Union[str, List[str]],
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        inputs = [input_data] if isinstance(input_data, str) else list(input_data)
        return {
            "id": "modr-{}".format(_uuid.uuid4().hex[:24]),
            "model": model,
            "results": [
                {
                    "flagged": False,
                    "categories": {k: False for k in (
                        "sexual", "hate", "harassment", "self-harm",
                        "sexual/minors", "hate/threatening", "violence/graphic",
                        "self-harm/intent", "self-harm/instructions",
                        "harassment/threatening", "violence",
                    )},
                    "category_scores": {k: 0.0 for k in (
                        "sexual", "hate", "harassment", "self-harm",
                        "sexual/minors", "hate/threatening", "violence/graphic",
                        "self-harm/intent", "self-harm/instructions",
                        "harassment/threatening", "violence",
                    )},
                }
                for _ in inputs
            ],
        }
