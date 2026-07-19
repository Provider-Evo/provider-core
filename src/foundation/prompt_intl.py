"""Locale-aware prompt template loader (Provider-V2-style prompts/ layout)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.foundation.paths import project_root

__all__ = [
    "DEFAULT_PROMPT_LOCALE",
    "PromptMetadata",
    "clear_prompt_cache",
    "discover_prompt_locales",
    "get_prompts_root",
    "list_prompt_templates",
    "load_prompt",
    "normalize_prompt_locale",
    "resolve_prompt_path",
]

logger = logging.getLogger(__name__)

PROMPTS_ROOT = (project_root / "prompts").resolve()
DEFAULT_PROMPT_LOCALE = "zh-CN"
PROMPT_EXTENSIONS = (".prompt",)
SAFE_SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")

_WEBUI_LOCALE_MAP = {
    "zh": "zh-CN",
    "en": "en-US",
    "ja": "ja-JP",
    "ko": "ko-KR",
}


@dataclass(frozen=True)
class PromptMetadata:
    display_name: str = ""
    advanced: bool = False
    description: str = ""


@dataclass(frozen=True)
class PromptTemplateInfo:
    path: Path
    metadata: PromptMetadata


def get_prompts_root(prompts_root: Path | None = None) -> Path:
    return (prompts_root or PROMPTS_ROOT).resolve()


def normalize_prompt_locale(locale: str | None) -> str:
    raw = (locale or DEFAULT_PROMPT_LOCALE).strip()
    if not raw:
        return DEFAULT_PROMPT_LOCALE
    if raw in _WEBUI_LOCALE_MAP:
        return _WEBUI_LOCALE_MAP[raw]
    if SAFE_SEGMENT_PATTERN.fullmatch(raw):
        return raw
    short = raw.split("-", 1)[0].lower()
    return _WEBUI_LOCALE_MAP.get(short, DEFAULT_PROMPT_LOCALE)


def normalize_prompt_name(name: str) -> str:
    candidate = name.strip()
    for suffix in PROMPT_EXTENSIONS:
        if candidate.endswith(suffix):
            candidate = candidate[: -len(suffix)]
            break
    if (
        candidate in {".", ".."}
        or not candidate
        or not SAFE_SEGMENT_PATTERN.fullmatch(candidate)
    ):
        raise ValueError(f"invalid prompt name: {name!r}")
    return candidate


def discover_prompt_locales(prompts_root: Path | None = None) -> list[str]:
    root = get_prompts_root(prompts_root)
    if not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def _read_metadata_file(metadata_path: Path) -> dict[str, Any]:
    if not metadata_path.is_file():
        return {}
    try:
        if metadata_path.suffix == ".json":
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        else:
            import tomlkit

            data = tomlkit.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("读取 Prompt 元信息失败 %s: %s", metadata_path, exc)
        return {}
    return dict(data) if isinstance(data, dict) else {}


def _coerce_metadata(raw_metadata: Any) -> PromptMetadata:
    if not isinstance(raw_metadata, dict):
        return PromptMetadata()
    display_name = raw_metadata.get("display_name", "")
    advanced = raw_metadata.get("advanced", False)
    description = raw_metadata.get("description", "")
    return PromptMetadata(
        display_name=display_name if isinstance(display_name, str) else "",
        advanced=advanced if isinstance(advanced, bool) else False,
        description=description if isinstance(description, str) else "",
    )


def _load_prompt_metadata(prompt_path: Path) -> PromptMetadata:
    prompt_name = prompt_path.stem
    metadata_sources = (
        prompt_path.with_name(f"{prompt_name}.meta.toml"),
        prompt_path.with_name(f"{prompt_name}.meta.json"),
        prompt_path.parent / ".meta.toml",
        prompt_path.parent / ".meta.json",
    )
    merged: dict[str, Any] = {}
    for metadata_path in reversed(metadata_sources):
        raw = _read_metadata_file(metadata_path)
        section = raw.get(prompt_name)
        if isinstance(section, dict):
            merged.update(section)
        elif any(key in raw for key in ("display_name", "advanced", "description")):
            merged.update(raw)
    return _coerce_metadata(merged)


def _iter_locale_candidates(requested_locale: str) -> list[str]:
    candidates = [requested_locale]
    if requested_locale != DEFAULT_PROMPT_LOCALE:
        candidates.append(DEFAULT_PROMPT_LOCALE)
    return candidates


def resolve_prompt_path(
    name: str,
    locale: str | None = None,
    prompts_root: Path | None = None,
) -> Path:
    root = get_prompts_root(prompts_root)
    normalized_name = normalize_prompt_name(name)
    requested_locale = normalize_prompt_locale(locale)

    for locale_candidate in _iter_locale_candidates(requested_locale):
        locale_dir = root / locale_candidate
        for suffix in PROMPT_EXTENSIONS:
            candidate = (locale_dir / f"{normalized_name}{suffix}").resolve()
            if candidate.is_file():
                return candidate

    raise FileNotFoundError(
        f"prompt template not found: locale={requested_locale!r} name={normalized_name!r}"
    )


def list_prompt_templates(
    locale: str | None = None,
    prompts_root: Path | None = None,
) -> dict[str, PromptTemplateInfo]:
    root = get_prompts_root(prompts_root)
    requested_locale = normalize_prompt_locale(locale)
    templates: dict[str, PromptTemplateInfo] = {}

    for locale_candidate in reversed(_iter_locale_candidates(requested_locale)):
        locale_dir = root / locale_candidate
        if not locale_dir.is_dir():
            continue
        for suffix in PROMPT_EXTENSIONS:
            for prompt_path in sorted(locale_dir.glob(f"*{suffix}")):
                if not prompt_path.is_file():
                    continue
                templates[prompt_path.stem] = PromptTemplateInfo(
                    path=prompt_path,
                    metadata=_load_prompt_metadata(prompt_path),
                )
    return templates


@lru_cache(maxsize=None)
def _read_prompt_template(prompt_path: str) -> str:
    return Path(prompt_path).read_text(encoding="utf-8")


def load_prompt(
    name: str,
    locale: str | None = None,
    prompts_root: Path | None = None,
    **kwargs: object,
) -> str:
    prompt_path = resolve_prompt_path(name, locale=locale, prompts_root=prompts_root)
    template = _read_prompt_template(str(prompt_path.resolve()))
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except Exception as exc:
        logger.warning("Prompt 格式化失败 %s: %s", name, exc)
        return template


def clear_prompt_cache() -> None:
    _read_prompt_template.cache_clear()
