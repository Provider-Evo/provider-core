from __future__ import annotations

"""Model extraction helpers."""

from typing import Any, Iterable, List, Set, Tuple

_KEYS: Tuple[str, ...] = ("id", "modelId", "model_id", "name")


def _iter_ids(items: Iterable[Any]) -> Iterable[str]:
    for item in items:
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            for key in _KEYS:
                value = item.get(key)
                if isinstance(value, str):
                    yield value
                    break


def extract_model_ids(raw: Any) -> List[str]:
    """Extract de-duplicated model identifiers from heterogeneous payloads."""
    result: List[str] = []
    seen: Set[str] = set()

    def push(value: str) -> None:
        text = value.strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)

    if isinstance(raw, list):
        for item in _iter_ids(raw):
            push(item)
        return result
    if not isinstance(raw, dict):
        return result

    candidates = []
    data = raw.get("data")
    if isinstance(data, list):
        candidates.append(data)
    elif isinstance(data, dict):
        nested = data.get("models")
        if isinstance(nested, list):
            candidates.append(nested)
    simple = raw.get("models")
    if isinstance(simple, list):
        candidates.append(simple)

    for block in candidates:
        for item in _iter_ids(block):
            push(item)
    return result
