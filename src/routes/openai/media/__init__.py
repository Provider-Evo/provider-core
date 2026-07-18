# -*- coding: utf-8 -*-
from __future__ import annotations

"""OpenAI 兼容路由——媒体子包（uploads + videos 聚合）。"""

from src.routes.openai.media.uploads import (
    create_audio_translation,
    create_embeddings,
    create_image,
    create_image_variation,
    create_moderation,
    create_rerank,
    create_speech,
    create_transcription,
    edit_image,
)
from src.routes.openai.media.videos import (
    create_video,
    create_video_character,
    create_video_edit,
    create_video_extension,
    delete_video,
    legacy_video_generations,
    list_videos,
    remix_video,
    retrieve_video,
    retrieve_video_character,
    retrieve_video_content,
)

__all__ = [
    "create_audio_translation",
    "create_embeddings",
    "create_image",
    "create_image_variation",
    "create_moderation",
    "create_rerank",
    "create_speech",
    "create_transcription",
    "edit_image",
    "create_video",
    "create_video_character",
    "create_video_edit",
    "create_video_extension",
    "delete_video",
    "legacy_video_generations",
    "list_videos",
    "remix_video",
    "retrieve_video",
    "retrieve_video_character",
    "retrieve_video_content",
]
