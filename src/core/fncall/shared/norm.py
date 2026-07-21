from __future__ import annotations

"""工具调用参数规范化：修复模型输出的 Python 字面量无法被 JSON 解析的问题。"""

import ast
import json
from typing import Any, Dict, List, Optional

from echotools.fncall.shared.coercion import _build_param_schema_index
from echotools.fncall.shared.normalization import (  # noqa: F401
    format_tool_descs,
    normalize_content,
)

from src.foundation.logger import get_logger

logger = get_logger(__name__)

__all__ = [
    "normalize_content",
    "format_tool_descs",
    "normalize_tool_call",
    "normalize_tool_calls",
]


def _try_parse_relaxed_literal(text: str) -> Any | None:
    """仅对 array/object 形态尝试 JSON 或 Python literal 解析。"""
    stripped = text.strip()
    if not stripped or stripped[0] not in "[{" or stripped[-1] not in "]}":
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return None


def _normalize_value(value: Any, schema: Optional[Dict[str, Any]] = None) -> Any:
    if isinstance(value, str):
        parsed = _try_parse_relaxed_literal(value)
        if parsed is not None:
            value = parsed
    if isinstance(value, list):
        item_schema = (schema or {}).get("items") if schema else None
        if isinstance(item_schema, dict):
            return [_normalize_value(item, item_schema) for item in value]
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        props = (schema or {}).get("properties") or {}
        return {
            key: _normalize_value(
                val,
                props.get(key) if isinstance(props.get(key), dict) else None,
            )
            for key, val in value.items()
        }
    return value


def normalize_tool_call(
    tc: Dict[str, Any],
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """将 tool call arguments 中的 Python 字面量字符串还原为合法 JSON 结构。"""
    func = tc.get("function") or {}
    name = str(func.get("name") or "")
    raw_args = func.get("arguments", "{}")
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("normalize_tool_call: invalid arguments JSON for %s", name)
        return tc

    schema_index = _build_param_schema_index(tools) if tools else {}
    param_schemas = schema_index.get(name, {})

    if isinstance(args, dict):
        args = {
            key: _normalize_value(
                val,
                param_schemas.get(key) if param_schemas else None,
            )
            for key, val in args.items()
        }
    else:
        args = _normalize_value(args)

    normalized = dict(tc)
    normalized["function"] = dict(func)
    normalized["function"]["arguments"] = json.dumps(args, ensure_ascii=False)
    return normalized


def normalize_tool_calls(
    tool_calls: Optional[List[Dict[str, Any]]],
    tools: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """批量规范化 OpenAI 格式 tool_calls。"""
    if not tool_calls:
        return []
    return [normalize_tool_call(tc, tools) for tc in tool_calls]
