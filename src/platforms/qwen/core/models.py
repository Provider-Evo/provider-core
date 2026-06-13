"""从 Qwen 远端响应中提取模型 ID 列表的工具。

支持多种返回结构：

- OpenAI 兼容: ``{"data": [{"id": "model-a"}, ...]}``
- 简单列表: ``{"models": ["model-a", ...]}``
- Qwen 嵌套: ``{"data": {"models": [{"modelId": "..."}, ...]}}``
- 纯列表: ``[{"id": "model-a"}, ...]``
"""

from __future__ import annotations

from typing import Any, Iterable, List, Set, Tuple

_KEYS: Tuple[str, ...] = ("id", "modelId", "model_id", "name")


def _iter_dict_ids(items: Iterable[Any]) -> Iterable[str]:
    """迭代 dict 列表，从 ``_KEYS`` 中提取第一个匹配的字符串字段。"""
    for item in items:
        if isinstance(item, dict):
            for key in _KEYS:
                value = item.get(key)
                if isinstance(value, str):
                    yield value
                    break
        elif isinstance(item, str):
            yield item


def _push(model_id: str, models: List[str], seen: Set[str]) -> None:
    """将合法模型 ID 加入列表，去重并去空白。"""
    mid = model_id.strip()
    if mid and mid not in seen:
        models.append(mid)
        seen.add(mid)


def extract_model_ids(raw: Any) -> List[str]:
    """从 API 响应中提取模型 ID 列表。

    Args:
        raw: API 原始 JSON 响应（已 ``json.loads`` 后的 Python 对象）。

    Returns:
        去重的模型 ID 列表；解析失败时返回空列表。

    Examples:
        >>> extract_model_ids({"data": [{"id": "qwen-a"}, {"id": "qwen-b"}]})
        ['qwen-a', 'qwen-b']
        >>> extract_model_ids(["m1", {"id": "m2"}, "m1"])
        ['m1', 'm2']
        >>> extract_model_ids({"models": ["x", "y"]})
        ['x', 'y']
        >>> extract_model_ids({"data": {"models": [{"modelId": "z"}]}})
        ['z']
    """
    models: List[str] = []
    seen: Set[str] = set()

    if isinstance(raw, list):
        for mid in _iter_dict_ids(raw):
            _push(mid, models, seen)
        return models

    if not isinstance(raw, dict):
        return models

    data = raw.get("data")
    if isinstance(data, list):
        for mid in _iter_dict_ids(data):
            _push(mid, models, seen)
        return models

    if isinstance(data, dict):
        nested = data.get("models", [])
        if isinstance(nested, list):
            for mid in _iter_dict_ids(nested):
                _push(mid, models, seen)
        return models

    simple = raw.get("models", [])
    if isinstance(simple, list):
        for mid in _iter_dict_ids(simple):
            _push(mid, models, seen)
    return models
