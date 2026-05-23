# src/core/tools.py
from __future__ import annotations

"""fncall 模板注入与解析（支持 en / zh 双语）。

设计原则
--------
* 单一职责：每个函数只做一件事，便于独立测试。
* 防御编程：所有外部输入都做类型/空值检查，不依赖调用方保证格式。
* 不可变数据流：消息列表不在原地修改，始终返回新列表/字典。
* 缓存安全：lru_cache 仅用于纯函数且控制上限，避免内存泄漏。
* 流式安全：FncallStreamParser 状态机保证 feed/finalize 幂等。
* 兼容性：支持 Python 3.8 - 3.14，不使用 3.10+ 专属语法。
* Schema 感知：参数值根据工具 JSON Schema 类型定义做精确类型转换。
* Agent 稳定性：内置无限循环检测、重复调用去重、上下文边界防护。
"""

import hashlib
import json
import os
import re
import secrets
import struct
import time
import uuid
from functools import lru_cache
from typing import Any, Dict, List, Optional, Set, Tuple

from src.core.config import get_config
from src.logger import get_logger

__all__ = [
    "inject_fncall",
    "parse_fncall",
    "FncallStreamParser",
    "format_tool_descs",
    "normalize_content",
    "parse_fncall_xml",
    "detect_tool_loop",
    "LoopDetectionResult",
]

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 正则常量（模块级编译，全局复用）
# ---------------------------------------------------------------------------

_FNCALL_BLOCK_RE = re.compile(
    r"<function_calls>(.*?)</function_calls>",
    re.DOTALL,
)
_INVOKE_RE = re.compile(
    r'<invoke\s+name="([^"]+)">(.*?)</invoke>',
    re.DOTALL,
)
_PARAM_NAME_RE = re.compile(
    r'<parameter\s+name="([^"]+)">(.*?)</parameter>',
    re.DOTALL,
)

_FE = "</" + "function>"
_FE_ESC = re.escape(_FE)
_FUNC_RE = re.compile(r"<function=([^>]+)>(.*?)" + _FE_ESC, re.DOTALL)

_PARAM_RE = re.compile(
    r"<([a-zA-Z_\u4e00-\u9fff][\w\u4e00-\u9fff]*)>\s*\n?(.*?)\n?\s*</\1>",
    re.DOTALL,
)
_TOOL_CALL_LINE_RE = re.compile(
    r"^Tool call \(([^)]+)\)\s*:\s*(\w[\w.]*)\((\{.*?\})\)\s*$",
    re.MULTILINE | re.DOTALL,
)
_TOOL_CALL_ID_RE = re.compile(
    r"Tool call \(([^)]+)\)\s*:",
)
_TOOL_RESULT_LINE_RE = re.compile(
    r"^Tool result \(([^)]+)\)\s*:\s*",
)

# ---------------------------------------------------------------------------
# UUID 生成
# ---------------------------------------------------------------------------


def _uuid7() -> str:
    """生成时间有序的 UUIDv7 字符串。

    布局（128 bit）：
        [0:48]   unix_ts_ms  (48 bit)
        [48:52]  version=7   (4 bit)
        [52:64]  rand_a      (12 bit，随机)
        [64:66]  variant=10  (2 bit)
        [66:128] rand_b      (62 bit，随机)
    """
    ts_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF

    rand_bytes = secrets.token_bytes(10)
    rand_a = struct.unpack(">H", rand_bytes[:2])[0] & 0x0FFF
    rand_b = struct.unpack(">Q", rand_bytes[2:])[0] & 0x3FFFFFFFFFFFFFFF

    uuid_int = (
        ts_ms << 80
        | 0x7 << 76
        | rand_a << 64
        | 0b10 << 62
        | rand_b
    )
    return str(uuid.UUID(int=uuid_int))


# ---------------------------------------------------------------------------
# Schema 索引构建与类型转换（核心新增）
# ---------------------------------------------------------------------------

# JSON Schema 原始类型集合（RFC 8259 + JSON Schema spec）
_SCALAR_TYPES = frozenset({"string", "integer", "number", "boolean", "null"})
_CONTAINER_TYPES = frozenset({"array", "object"})


def _build_param_schema_index(
    tools: Optional[List[Dict[str, Any]]],
) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """将工具列表构建为快速查找索引。

    返回结构::

        {
            "func_name": {
                "param_name": <JSON Schema dict>,
                ...
            },
            ...
        }

    只索引顶层 properties，嵌套对象的子字段类型转换在
    _coerce_param_value 中递归处理。

    Args:
        tools: OpenAI 格式工具定义列表，可为 None。

    Returns:
        两层嵌套字典；tools 为空时返回空字典。
    """
    if not tools:
        return {}

    index: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for tool in tools:
        fn: Dict[str, Any] = tool.get("function", tool)  # type: ignore[arg-type]
        name: str = fn.get("name") or ""
        if not name:
            continue
        props: Dict[str, Any] = (
            (fn.get("parameters") or {}).get("properties") or {}
        )
        index[name] = {
            pname: (pschema if isinstance(pschema, dict) else {})
            for pname, pschema in props.items()
        }
    return index


def _resolve_effective_type(schema: Dict[str, Any]) -> Optional[str]:
    """从 JSON Schema 中解析出有效的单一类型字符串。

    处理以下 schema 形态（按优先级）：
    1. ``{"type": "integer"}``                       → "integer"
    2. ``{"type": ["integer", "null"]}``             → "integer"（忽略 null）
    3. ``{"anyOf": [{"type": "boolean"}, ...]}``     → 取第一个非 null 类型
    4. ``{"oneOf": [...]}``                          → 同 anyOf
    5. ``{"enum": [1, 2, 3]}``                       → 从枚举值推断

    Args:
        schema: 单个参数的 JSON Schema 字典。

    Returns:
        类型字符串（如 "string"、"integer"）；无法确定时返回 None。
    """
    if not schema:
        return None

    # 形态 1 & 2：type 字段
    raw_type = schema.get("type")
    if isinstance(raw_type, str) and raw_type:
        return raw_type
    if isinstance(raw_type, list):
        # 过滤 null，取第一个有效类型
        non_null = [t for t in raw_type if t != "null" and isinstance(t, str)]
        if non_null:
            return non_null[0]

    # 形态 3 & 4：anyOf / oneOf
    for combiner_key in ("anyOf", "oneOf"):
        combiner = schema.get(combiner_key)
        if not isinstance(combiner, list):
            continue
        for sub in combiner:
            if not isinstance(sub, dict):
                continue
            sub_type = sub.get("type")
            if isinstance(sub_type, str) and sub_type != "null":
                return sub_type

    # 形态 5：从 enum 值推断
    enum_vals = schema.get("enum")
    if isinstance(enum_vals, list) and enum_vals:
        first = enum_vals[0]
        if isinstance(first, bool):
            return "boolean"
        if isinstance(first, int):
            return "integer"
        if isinstance(first, float):
            return "number"
        if isinstance(first, str):
            return "string"
        if isinstance(first, list):
            return "array"
        if isinstance(first, dict):
            return "object"

    return None


def _coerce_to_string(value: Any) -> str:
    """将任意值安全转换为字符串。

    - None      → ""
    - str       → 原样
    - dict/list → JSON 序列化
    - 其他      → str()
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _coerce_to_integer(raw: str, parsed: Any) -> Any:
    """将原始字符串或已解析值转换为整数。

    转换链：
        已是 int → 直接返回
        bool     → int(bool)（True→1，False→0）
        float    → 检查是否为整值再转（3.0→3，3.5→保留 float）
        str      → int(str.strip())，失败 → float(str) 再取整
        其他     → 原样返回（防御）
    """
    if isinstance(parsed, bool):
        return int(parsed)
    if isinstance(parsed, int):
        return parsed
    if isinstance(parsed, float):
        if parsed.is_integer():
            return int(parsed)
        logger.debug("_coerce_to_integer: 浮点数 %r 不是整值，保留为 float", parsed)
        return parsed

    # 尝试从字符串转换
    stripped = raw.strip()
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        fval = float(stripped)
        if fval.is_integer():
            return int(fval)
        logger.debug("_coerce_to_integer: %r 为非整浮点，保留为 float", stripped)
        return fval
    except ValueError:
        pass

    logger.debug("_coerce_to_integer: 无法转换 %r，原样返回", raw[:100])
    return parsed


def _coerce_to_number(raw: str, parsed: Any) -> Any:
    """将原始字符串或已解析值转换为数值（int 或 float）。"""
    if isinstance(parsed, bool):
        return int(parsed)
    if isinstance(parsed, (int, float)):
        return parsed

    stripped = raw.strip()
    try:
        ival = int(stripped)
        return ival
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass

    logger.debug("_coerce_to_number: 无法转换 %r，原样返回", raw[:100])
    return parsed


def _coerce_to_boolean(raw: str, parsed: Any) -> Any:
    """将原始字符串或已解析值转换为布尔值。

    LLM 常见非标准布尔输出：
        "True" / "False"（Python 风格）
        "yes" / "no"
        "1" / "0"
        "on" / "off"
    """
    if isinstance(parsed, bool):
        return parsed
    if isinstance(parsed, int):
        return bool(parsed)

    normalized = raw.strip().lower()
    if normalized in ("true", "yes", "1", "on"):
        return True
    if normalized in ("false", "no", "0", "off"):
        return False

    logger.debug("_coerce_to_boolean: 无法识别布尔值 %r，原样返回", raw[:100])
    return parsed


def _coerce_to_array(raw: str, parsed: Any, item_schema: Dict[str, Any]) -> Any:
    """将原始字符串或已解析值转换为列表，并对元素递归应用类型转换。

    Args:
        raw: 原始字符串（已 strip）。
        parsed: json.loads 尝试后的值。
        item_schema: 数组元素的 JSON Schema（items 字段）。

    Returns:
        列表或原始值（转换失败时）。
    """
    result_list: Any = None

    if isinstance(parsed, list):
        result_list = parsed
    elif isinstance(parsed, str):
        try:
            candidate = json.loads(parsed)
            if isinstance(candidate, list):
                result_list = candidate
        except json.JSONDecodeError:
            pass
    elif isinstance(raw, str):
        stripped = raw.strip()
        if stripped.startswith("["):
            try:
                candidate = json.loads(stripped)
                if isinstance(candidate, list):
                    result_list = candidate
            except json.JSONDecodeError:
                pass

    if result_list is None:
        logger.debug("_coerce_to_array: 无法解析为列表，原样返回 %r", raw[:100])
        return parsed

    # 元素级递归转换（只在 item_schema 非空时执行）
    if item_schema:
        return [
            _coerce_param_value(
                json.dumps(item, ensure_ascii=False) if not isinstance(item, str) else item,
                item_schema,
            )
            for item in result_list
        ]
    return result_list


def _coerce_to_object(raw: str, parsed: Any, schema: Dict[str, Any]) -> Any:
    """将原始字符串或已解析值转换为字典，并对字段递归应用类型转换。

    Args:
        raw: 原始字符串。
        parsed: json.loads 尝试后的值。
        schema: 当前 object 的 JSON Schema（含 properties）。

    Returns:
        字典或原始值（转换失败时）。
    """
    result_dict: Any = None

    if isinstance(parsed, dict):
        result_dict = parsed
    elif isinstance(parsed, str):
        try:
            candidate = json.loads(parsed)
            if isinstance(candidate, dict):
                result_dict = candidate
        except json.JSONDecodeError:
            pass
    elif isinstance(raw, str):
        stripped = raw.strip()
        if stripped.startswith("{"):
            try:
                candidate = json.loads(stripped)
                if isinstance(candidate, dict):
                    result_dict = candidate
            except json.JSONDecodeError:
                pass

    if result_dict is None:
        logger.debug("_coerce_to_object: 无法解析为字典，原样返回 %r", raw[:100])
        return parsed

    # 字段级递归转换
    sub_props: Dict[str, Any] = schema.get("properties") or {}
    if not sub_props:
        return result_dict

    coerced: Dict[str, Any] = {}
    for k, v in result_dict.items():
        field_schema = sub_props.get(k)
        if isinstance(field_schema, dict) and field_schema:
            v_raw = (
                v if isinstance(v, str)
                else json.dumps(v, ensure_ascii=False)
            )
            coerced[k] = _coerce_param_value(v_raw, field_schema)
        else:
            coerced[k] = v
    return coerced


def _coerce_param_value(raw: str, schema: Dict[str, Any]) -> Any:
    """根据 JSON Schema 对单个参数的原始字符串值做精确类型转换。

    转换策略
    --------
    1. 先用 ``json.loads`` 尝试解析，得到 ``parsed``。
    2. 从 ``schema`` 解析出 ``effective_type``。
    3. 根据 ``effective_type`` 分派到专用转换函数。
    4. schema 为空或类型未知时退化为原有行为（json.loads 优先）。

    支持的类型
    ----------
    - ``string``  : 确保结果为 str，对象/列表回退为 JSON 字符串
    - ``integer`` : int，处理 "5"/"5.0"/"5.5"/True/False
    - ``number``  : int 或 float，按值精度选择
    - ``boolean`` : bool，处理 "True"/"False"/"yes"/"no"/"1"/"0"
    - ``array``   : list，支持 items schema 递归转换
    - ``object``  : dict，支持 properties schema 递归转换
    - ``null``    : None
    - 复合类型（anyOf/oneOf/type 数组）：提取第一个非 null 类型处理

    Args:
        raw: 从 XML parameter 标签中提取的原始字符串（已 strip 换行）。
        schema: 对应参数的 JSON Schema 字典；空字典时退化为启发式解析。

    Returns:
        类型转换后的 Python 值。
    """
    # 先尝试 JSON 解析（所有分支都需要 parsed 结果）
    stripped = raw.strip()
    try:
        parsed: Any = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        parsed = raw  # 保留原始字符串

    # schema 为空 → 退化为原有启发式行为
    if not schema:
        return parsed

    effective_type = _resolve_effective_type(schema)

    # 无法确定类型 → 退化
    if effective_type is None:
        return parsed

    # --- string ---
    if effective_type == "string":
        # 若 LLM 把字符串包在 JSON 引号里，json.loads 已正确解析
        if isinstance(parsed, str):
            return parsed
        # 若解析出非字符串（LLM 意外输出了 42、true 等）→ 转为字符串
        return _coerce_to_string(parsed)

    # --- integer ---
    if effective_type == "integer":
        return _coerce_to_integer(stripped, parsed)

    # --- number ---
    if effective_type == "number":
        return _coerce_to_number(stripped, parsed)

    # --- boolean ---
    if effective_type == "boolean":
        return _coerce_to_boolean(stripped, parsed)

    # --- null ---
    if effective_type == "null":
        return None

    # --- array ---
    if effective_type == "array":
        item_schema: Dict[str, Any] = schema.get("items") or {}
        return _coerce_to_array(stripped, parsed, item_schema)

    # --- object ---
    if effective_type == "object":
        return _coerce_to_object(stripped, parsed, schema)

    # 未知类型 → 退化
    logger.debug("_coerce_param_value: 未知类型 %r，退化为 json.loads 结果", effective_type)
    return parsed


# ---------------------------------------------------------------------------
# Agent 循环检测
# ---------------------------------------------------------------------------


class LoopDetectionResult:
    """循环检测结果。

    Attributes:
        is_looping: 是否检测到循环。
        repeat_count: 当前重复次数。
        fingerprint: 最近一次调用的指纹（tool_name + args_hash）。
        suggestion: 建议注入给 LLM 的提示文本（仅 is_looping=True 时非空）。
    """

    __slots__ = ("is_looping", "repeat_count", "fingerprint", "suggestion")

    def __init__(
        self,
        is_looping: bool,
        repeat_count: int,
        fingerprint: str,
        suggestion: str,
    ) -> None:
        self.is_looping = is_looping
        self.repeat_count = repeat_count
        self.fingerprint = fingerprint
        self.suggestion = suggestion

    def __repr__(self) -> str:
        return (
            f"LoopDetectionResult(is_looping={self.is_looping}, "
            f"repeat_count={self.repeat_count}, "
            f"fingerprint={self.fingerprint!r})"
        )


def _tool_call_fingerprint(tool_calls: List[Dict[str, Any]]) -> str:
    """生成一次 assistant 调用的指纹字符串。"""
    if not tool_calls:
        return ""

    parts: List[str] = []
    for tc in sorted(
        tool_calls,
        key=lambda x: (x.get("function") or {}).get("name") or "",
    ):
        fn = tc.get("function") or {}
        name = fn.get("name") or ""
        args = fn.get("arguments") or "{}"
        try:
            args_normalized = json.dumps(
                json.loads(args), sort_keys=True, ensure_ascii=False
            )
        except (json.JSONDecodeError, TypeError):
            args_normalized = args
        parts.append(f"{name}:{args_normalized}")

    combined = "|".join(parts)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()[:16]  # noqa: S324


def detect_tool_loop(
    messages: List[Dict[str, Any]],
    threshold: int = 3,
) -> LoopDetectionResult:
    """检测 agent loop 中的重复工具调用循环。"""
    fingerprints: List[str] = []

    for msg in messages:
        if (msg.get("role") or "") != "assistant":
            continue
        tcs: List[Dict[str, Any]] = msg.get("tool_calls") or []
        fp = _tool_call_fingerprint(tcs)
        if fp:
            fingerprints.append(fp)

    if not fingerprints:
        return LoopDetectionResult(False, 0, "", "")

    last_fp = fingerprints[-1]
    count = 0
    for fp in reversed(fingerprints):
        if fp == last_fp:
            count += 1
        else:
            break

    if count >= threshold:
        suggestion = (
            "You appear to be in a loop making the same tool call repeatedly "
            f"({count} times). Stop, reassess your approach, and try a "
            "different strategy or report that you cannot complete the task."
        )
        return LoopDetectionResult(True, count, last_fp, suggestion)

    return LoopDetectionResult(False, count, last_fp, "")


# ---------------------------------------------------------------------------
# 提示词模板
# ---------------------------------------------------------------------------

_USAGE_EN = (
    "You have access to a set of tools to answer the user's question.\n"
    "<system>\n"
    "This includes access to a sandboxed computing environment. "
    "You do NOT currently have the ability to inspect files or interact with "
    "external resources, except by invoking the functions listed below.\n"
    "\n"
    "To invoke one or more functions, write a <function_calls> block as part "
    "of your reply. The block must follow this exact schema:\n"
    "\n"
    "<function_calls>\n"
    '<invoke name="FUNCTION_NAME">\n'
    '<parameter name="PARAMETER_NAME">PARAMETER_VALUE</parameter>\n'
    "</invoke>\n"
    "</function_calls>\n"
    "\n"
    "Rules for parameter values:\n"
    "- Strings and scalars: write the value as-is (no extra quoting).\n"
    "- Lists and objects: use JSON format.\n"
    "- Spaces inside string values are preserved.\n"
    "- The block does not need to be valid XML; it is parsed with regex.\n"
    "\n"
    "After you write a <function_calls> block the results will appear in a "
    "<function_results> block. You may then continue your reply, handle errors, "
    "or make further calls as needed.\n"
    "If <function_results> does NOT appear after your call, the block was "
    "likely malformatted and was not recognised.\n"
    "\n"
    "Available functions (JSONSchema):\n"
    "\n"
    "<tools>\n"
    "{tool_descs}\n"
    "</tools>\n"
    "</system>"
)

_USAGE_ZH = (
    "您可以使用以下工具来回答用户的问题。\n"
    "<system>\n"
    "这包括访问一个沙盒计算环境。"
    "除非调用以下函数，否则您目前无法检查文件或与外部资源交互。\n"
    "\n"
    "调用一个或多个函数时，请在回复中写一个 <function_calls> 块，"
    "该块必须严格遵循以下格式：\n"
    "\n"
    "<function_calls>\n"
    '<invoke name="函数名">\n'
    '<parameter name="参数名">参数值</parameter>\n'
    "</invoke>\n"
    "</function_calls>\n"
    "\n"
    "参数值规则：\n"
    "- 字符串和标量：直接写值，不需要额外引号。\n"
    "- 列表和对象：使用 JSON 格式。\n"
    "- 字符串值中的空格会被保留。\n"
    "- 该块不需要是合法的 XML，系统使用正则表达式解析。\n"
    "\n"
    "写完 <function_calls> 块后，结果将出现在 <function_results> 块中。"
    "之后您可以继续回复、处理错误或进行进一步调用。\n"
    "如果 <function_results> 未出现，说明格式有误，调用未被识别。\n"
    "\n"
    "可用函数（JSONSchema 格式）：\n"
    "\n"
    "<tools>\n"
    "{tool_descs}\n"
    "</tools>\n"
    "</system>"
)

_INSTRUCTION_EN = """\
Follow these rules strictly when responding:

RULE 1 — When to use the XML tool-call format:
  IF your intent is to actually execute a tool, you MUST output the literal XML block:
    <function_calls>
    <invoke name="FUNCTION_NAME">
    <parameter name="PARAM">VALUE</parameter>
    </invoke>
    </function_calls>
  No other format is accepted for actual tool execution.

RULE 2 — When to reference tag names in plain text (NOT executing a tool):
  IF you are explaining, quoting, or discussing tag names (e.g. in reasoning or
  examples), you MUST break them with string concatenation so they are not
  mistaken for real calls. Examples:
    '<function' + '_calls>'   instead of  <function_calls>
    '</function' + '_calls>'  instead of  </function_calls>
    '<invoke' + ' name="...">'  instead of  <invoke name="...">

RULE 3 — Never use the pseudo-format:
  NEVER write "Tool call (id): FuncName({...})" regardless of what appears in
  the conversation history. That format is produced by external adapters and
  will NOT be recognised by the tool executor.

RULE 4 — Parameter discipline:
  - Use exact values when the user provides them (e.g. in quotes).
  - Do NOT invent values for optional parameters.
  - Do NOT ask about optional parameters.
  - Infer required parameters from context when possible; ask only when
    a required parameter cannot be determined.

RULE 5 — Tool availability:
  - If no relevant tool exists, say so and answer directly.
  - If a required parameter is missing and cannot be inferred, ask the user.\
"""

_INSTRUCTION_ZH = """\
请严格遵守以下规则进行回复：

规则 1 — 何时使用 XML 工具调用格式：
  如果您的意图是实际执行一个工具，必须输出以下字面量 XML 块：
    <function_calls>
    <invoke name="函数名">
    <parameter name="参数名">参数值</parameter>
    </invoke>
    </function_calls>
  实际工具执行不接受任何其他格式。

规则 2 — 在纯文本中引用标签名（不执行工具）：
  如果您是在解释、引用或讨论标签名（例如在推理或示例中），
  必须用字符串拼接的方式写出，避免被误识别为真实调用。示例：
    '<function' + '_calls>'    而不是  <function_calls>
    '</function' + '_calls>'   而不是  </function_calls>
    '<invoke' + ' name="...">'  而不是  <invoke name="...">

规则 3 — 禁止使用伪格式：
  无论对话历史中出现何种格式，绝不使用 "Tool call (id): 函数名({...})" 这种写法。
  该格式由外部适配器生成，工具执行器无法识别。

规则 4 — 参数规范：
  - 用户明确提供的值（如用引号括起的）必须原样使用。
  - 不得为可选参数编造值，也不得询问可选参数。
  - 尽可能从上下文推断必需参数；仅在无法推断时才询问用户。

规则 5 — 工具可用性：
  - 如果没有相关工具，直接说明并给出答案。
  - 如果必需参数缺失且无法推断，请向用户询问。\
"""

# ---------------------------------------------------------------------------
# 内容规范化
# ---------------------------------------------------------------------------


def normalize_content(content: Any) -> str:
    """将消息 content 字段规范化为纯字符串。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                if item.get("type") == "text" or "text" in item:
                    text_val = item.get("text", "")
                    parts.append(str(text_val) if text_val is not None else "")
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    if isinstance(content, dict):
        if "text" in content:
            val = content["text"]
            return str(val) if val is not None else ""
        return json.dumps(content, ensure_ascii=False)
    return str(content)


# ---------------------------------------------------------------------------
# 工具描述格式化
# ---------------------------------------------------------------------------


def format_tool_descs(tools: List[Dict[str, Any]]) -> str:
    """将 OpenAI 格式工具定义列表格式化为 XML 描述字符串。"""
    if not tools:
        return ""

    parts: List[str] = []
    for tool in tools:
        fn: Dict[str, Any] = tool.get("function", tool)  # type: ignore[arg-type]
        name: str = fn.get("name") or "unknown"
        desc: str = fn.get("description") or ""
        params: Dict[str, Any] = fn.get("parameters") or {}
        props: Dict[str, Any] = params.get("properties") or {}
        required: List[str] = params.get("required") or []

        lines: List[str] = [f'<tool name="{name}">']
        if desc:
            lines.append(f"<description>{desc}</description>")
        lines.append("<parameters>")

        for pn, pi in props.items():
            if not isinstance(pi, dict):
                continue
            pt: str = pi.get("type") or "string"
            req_str = "true" if pn in required else "false"
            lines.append(f'<parameter name="{pn}" type="{pt}" required="{req_str}">')
            pd: str = pi.get("description") or ""
            if pd:
                lines.append(f"<description>{pd}</description>")
            enum_vals = pi.get("enum")
            if isinstance(enum_vals, list) and enum_vals:
                lines.append(f"<enum>{', '.join(map(str, enum_vals))}</enum>")
            if "default" in pi:
                lines.append(f"<default>{pi['default']}</default>")
            lines.append("</parameter>")

        lines.append("</parameters>")

        examples = fn.get("input_examples")
        if isinstance(examples, list) and examples:
            lines.append("<input_examples>")
            for ex in examples:
                lines.append(
                    f"<example>{json.dumps(ex, ensure_ascii=False)}</example>"
                )
            lines.append("</input_examples>")

        lines.append("</tool>")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 渲染工具调用 / 工具结果
# ---------------------------------------------------------------------------


def _render_parameter_value(v: Any) -> str:
    """将参数值渲染为适合嵌入 XML parameter 标签的字符串。"""
    if isinstance(v, str):
        return v
    return json.dumps(v, ensure_ascii=False)


def _render_tool_call(tc: Dict[str, Any]) -> str:
    """将单个 tool_call 对象渲染为 function_calls XML 块。"""
    fn: Dict[str, Any] = tc.get("function") or {}
    name: str = fn.get("name") or ""
    args_str: str = fn.get("arguments") or "{}"

    try:
        args_dict = json.loads(args_str)
        if not isinstance(args_dict, dict):
            args_dict = {"value": args_dict}
    except json.JSONDecodeError:
        logger.debug(
            "_render_tool_call: arguments 非合法 JSON，原样传递: %r",
            args_str[:200],
        )
        args_dict = {"value": args_str}

    lines: List[str] = ["<function_calls>", f'<invoke name="{name}">']
    for k, v in args_dict.items():
        val = _render_parameter_value(v).strip("\n")
        lines.append(f'<parameter name="{k}">{val}</parameter>')
    lines.append("</invoke>")
    lines.append("</function_calls>")
    return "\n".join(lines)


def _render_tool_result(
    content: Any,
    tool_name: str = "",
    is_error: bool = False,
) -> str:
    """将工具执行结果渲染为 function_results XML 块。"""
    text = normalize_content(content)
    lines: List[str] = ["<function_results>", "<result>"]
    if tool_name:
        lines.append(f"<tool_name>{tool_name}</tool_name>")
    if is_error:
        lines.append("<is_error>true</is_error>")
    lines.append("<stdout>")
    lines.append(text)
    lines.append("</stdout>")
    lines.append("</result>")
    lines.append("</function_results>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 伪格式检测与转换
# ---------------------------------------------------------------------------


def _strip_tool_result_prefix(content: str) -> str:
    """剥离 content 开头的 'Tool result (id): ' 前缀。"""
    m = _TOOL_RESULT_LINE_RE.match(content)
    if m:
        return content[m.end():].lstrip("\n")
    return content


def _parse_pseudo_tool_calls(
    content: str,
) -> Tuple[str, List[Dict[str, Any]]]:
    """解析 assistant 消息中的 Tool call 伪格式行。"""
    tool_calls: List[Dict[str, Any]] = []
    kept_lines: List[str] = []

    for line in content.splitlines():
        m = _TOOL_CALL_LINE_RE.match(line.strip())
        if m:
            tool_id = m.group(1).strip()
            func_name = m.group(2).strip()
            args_raw = m.group(3).strip()
            try:
                args_obj = json.loads(args_raw)
                if not isinstance(args_obj, dict):
                    args_obj = {"value": args_obj}
                arguments = json.dumps(args_obj, ensure_ascii=False)
            except json.JSONDecodeError:
                logger.debug(
                    "_parse_pseudo_tool_calls: 参数非合法 JSON: %r",
                    args_raw[:200],
                )
                arguments = "{}"
            tool_calls.append(
                {
                    "id": tool_id,
                    "type": "function",
                    "function": {"name": func_name, "arguments": arguments},
                }
            )
        else:
            kept_lines.append(line)

    cleaned = "\n".join(kept_lines).strip()
    return cleaned, tool_calls


def _collect_tool_call_ids(messages: List[Dict[str, Any]]) -> Dict[str, str]:
    """扫描所有 assistant 消息，收集 tool_id -> tool_name 映射。"""
    id_to_name: Dict[str, str] = {}

    for msg in messages:
        if (msg.get("role") or "user") != "assistant":
            continue

        for tc in msg.get("tool_calls") or []:
            tid: str = tc.get("id") or ""
            fn_name: str = (tc.get("function") or {}).get("name") or ""
            if tid:
                id_to_name.setdefault(tid, fn_name)

        content_str = normalize_content(msg.get("content", ""))
        if not content_str:
            continue

        for line in content_str.splitlines():
            stripped = line.strip()
            m_full = _TOOL_CALL_LINE_RE.match(stripped)
            if m_full:
                tid = m_full.group(1).strip()
                fn_name = m_full.group(2).strip()
                if tid:
                    id_to_name.setdefault(tid, fn_name)
                continue
            m_id = _TOOL_CALL_ID_RE.search(stripped)
            if m_id:
                tid = m_id.group(1).strip()
                if tid:
                    id_to_name.setdefault(tid, "")

    return id_to_name


@lru_cache(maxsize=256)
def _parse_tool_result_info(content: str) -> Optional[Tuple[str, str]]:
    """从消息内容中解析 tool result 前缀，返回 (tool_id, clean_content)。"""
    if not content:
        return None

    first_line = ""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break

    if not first_line:
        return None

    m = _TOOL_RESULT_LINE_RE.match(first_line)
    if not m:
        return None

    tool_id = m.group(1).strip()
    clean = _strip_tool_result_prefix(content)
    return (tool_id, clean)


def _try_convert_user_to_tool(
    message: Dict[str, Any],
    known_tool_ids: Dict[str, str],
) -> Optional[Dict[str, Any]]:
    """尝试将 user 消息转换为标准 tool 角色消息。"""
    content_str = normalize_content(message.get("content", ""))
    parsed = _parse_tool_result_info(content_str)
    if parsed is None:
        return None

    tool_id, clean_content = parsed
    if tool_id not in known_tool_ids:
        return None

    return {
        "role": "tool",
        "tool_call_id": tool_id,
        "content": clean_content,
    }


def _convert_assistant_pseudo_calls(message: Dict[str, Any]) -> Dict[str, Any]:
    """将 assistant 消息中的 Tool call 伪格式转换为标准 tool_calls 结构。"""
    if message.get("tool_calls"):
        return message

    content_str = normalize_content(message.get("content", ""))
    if not content_str:
        return message

    cleaned, tool_calls = _parse_pseudo_tool_calls(content_str)
    if not tool_calls:
        return message

    new_msg = dict(message)
    new_msg["content"] = cleaned or None
    new_msg["tool_calls"] = tool_calls
    return new_msg


def _normalize_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """对消息列表做两步预处理。"""
    if not messages:
        return []

    step1: List[Dict[str, Any]] = []
    for m in messages:
        role = m.get("role") or "user"
        if role == "assistant":
            step1.append(_convert_assistant_pseudo_calls(m))
        else:
            step1.append(m)

    known_tool_ids = _collect_tool_call_ids(step1)
    if not known_tool_ids:
        return step1

    result: List[Dict[str, Any]] = []
    for m in step1:
        role = m.get("role") or "user"
        if role == "user":
            converted = _try_convert_user_to_tool(m, known_tool_ids)
            if converted is not None:
                result.append(converted)
                continue
        result.append(m)

    return result


# ---------------------------------------------------------------------------
# 对话历史格式化
# ---------------------------------------------------------------------------


def _make_assistant_dedup_key(
    content: Optional[str],
    tool_calls: List[Dict[str, Any]],
) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
    """生成 assistant 消息的去重键。"""
    safe_content = content or ""
    tc_key: Tuple[Tuple[str, str], ...] = tuple(
        (
            (tc.get("function") or {}).get("name") or "",
            (tc.get("function") or {}).get("arguments") or "",
        )
        for tc in tool_calls
    )
    return (safe_content, tc_key)


def _format_conversation_history(messages: List[Dict[str, Any]]) -> str:
    """将历史消息列表格式化为对话历史文本块。"""
    if not messages:
        return ""

    call_id_to_name: Dict[str, str] = {}
    seen_assistant_keys: Set[Tuple[str, Tuple[Tuple[str, str], ...]]] = set()
    parts: List[Tuple[str, bool]] = []

    for m in messages:
        role: str = m.get("role") or "user"
        content_str = normalize_content(m.get("content", ""))

        if role == "user":
            parts.append((f"<user>\n{content_str}\n</user>", False))

        elif role == "assistant":
            tcs: List[Dict[str, Any]] = m.get("tool_calls") or []
            blocks: List[str] = []

            if content_str:
                blocks.append(content_str)

            for tc in tcs:
                cid = tc.get("id") or ""
                fn_name = (tc.get("function") or {}).get("name") or ""
                if cid and fn_name:
                    call_id_to_name[cid] = fn_name
                blocks.append(_render_tool_call(tc))

            inner = "\n\n".join(blocks)
            rendered = f"<assistant>\n{inner}\n</assistant>"

            dedup_key = _make_assistant_dedup_key(content_str, tcs)
            if dedup_key in seen_assistant_keys:
                logger.debug("跳过重复 assistant 消息（dedup_key 已见）")
                continue
            seen_assistant_keys.add(dedup_key)
            parts.append((rendered, False))

        elif role == "tool":
            tid = m.get("tool_call_id") or ""
            tool_name = call_id_to_name.get(tid, "")
            is_error: bool = bool(m.get("is_error", False))
            rendered = _render_tool_result(content_str, tool_name, is_error)
            parts.append((rendered, True))

        else:
            parts.append((f"<{role}>\n{content_str}\n</{role}>", False))

    if not parts:
        return ""

    result_parts: List[str] = [parts[0][0]]
    for text, is_tool in parts[1:]:
        sep = "\n" if is_tool else "\n\n"
        result_parts.append(sep + text)

    return "".join(result_parts)


# ---------------------------------------------------------------------------
# 配置辅助函数
# ---------------------------------------------------------------------------


def _load_usage_template(lang: str) -> str:
    """从配置加载使用说明模板，失败时回退到内置模板。"""
    try:
        cfg = get_config()
        t = cfg.fncall.templates
        key = f"usage_{lang}"
        tmpl: str = t.get(key) or t.get(lang) or ""
        if tmpl:
            return tmpl
    except Exception as exc:
        logger.debug("读取 fncall 模板配置失败，使用内置模板: %s", exc)
    return _USAGE_ZH if lang == "zh" else _USAGE_EN


def _maybe_dump_prompt(prompt: str) -> None:
    """若配置开启 print_prompt，将 prompt 写入 logs/prompts/ 目录。"""
    try:
        cfg = get_config()
        if not cfg.fncall.print_prompt:
            return
    except Exception:
        return

    try:
        dump_dir = "logs/prompts"
        os.makedirs(dump_dir, exist_ok=True)
        dump_path = os.path.join(dump_dir, f"{_uuid7()}.txt")
        with open(dump_path, "w", encoding="utf-8") as f:
            f.write(prompt)
        logger.debug("fncall prompt 已写入 %s", dump_path)
    except Exception as exc:
        logger.warning("写入 fncall prompt 失败: %s", exc)


# ---------------------------------------------------------------------------
# 核心注入函数
# ---------------------------------------------------------------------------


def inject_fncall(
    messages: List[Dict[str, Any]],
    tools: List[Dict[str, Any]],
    lang: str = "en",
    user_system_prompt: str = "",
    loop_detection_threshold: int = 3,
) -> List[Dict[str, Any]]:
    """将工具定义注入消息列表，构建为单条 user 消息送给 LLM。"""
    if not tools:
        return list(messages)

    normalized = _normalize_messages(list(messages))

    loop_warning: str = ""
    if loop_detection_threshold > 0:
        loop_result = detect_tool_loop(normalized, loop_detection_threshold)
        if loop_result.is_looping:
            logger.warning(
                "inject_fncall: 检测到工具调用循环（重复 %d 次，指纹=%s）",
                loop_result.repeat_count,
                loop_result.fingerprint,
            )
            loop_warning = loop_result.suggestion

    last_user_idx: Optional[int] = None
    for i in range(len(normalized) - 1, -1, -1):
        if (normalized[i].get("role") or "user") == "user":
            last_user_idx = i
            break

    if last_user_idx is not None:
        history_messages: List[Dict[str, Any]] = (
            normalized[:last_user_idx] + normalized[last_user_idx + 1:]
        )
        current_user_message: str = normalize_content(
            normalized[last_user_idx].get("content", "")
        )
    else:
        history_messages = normalized
        current_user_message = ""

    tool_descs = format_tool_descs(tools)
    usage_template = _load_usage_template(lang)
    system_block = usage_template.replace("{tool_descs}", tool_descs)
    instruction_text = _INSTRUCTION_ZH if lang == "zh" else _INSTRUCTION_EN

    sections: List[str] = [system_block]

    if user_system_prompt and user_system_prompt.strip():
        sections.append(
            f"<user_system_prompt>\n{user_system_prompt.strip()}\n</user_system_prompt>"
        )

    history_text = _format_conversation_history(history_messages).strip()
    if history_text:
        sections.append(
            f"<conversation_history>\n{history_text}\n</conversation_history>"
        )

    if loop_warning:
        sections.append(f"<loop_warning>\n{loop_warning}\n</loop_warning>")

    if current_user_message:
        sections.append(
            f"<current_user_message>\n{current_user_message}\n</current_user_message>"
        )
    else:
        sections.append("<current_user_message>\n</current_user_message>")

    sections.append(f"<instruction>\n{instruction_text}\n</instruction>")

    prompt = "\n\n".join(sections)
    _maybe_dump_prompt(prompt)

    return [{"role": "user", "content": prompt}]


# ---------------------------------------------------------------------------
# 解析函数调用（schema 感知版本）
# ---------------------------------------------------------------------------


def _parse_invoke_body(
    body: str,
    func_name: str = "",
    schema_index: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> str:
    """将 <invoke> 标签体中的 <parameter> 列表解析为 JSON arguments 字符串。

    新增 schema_index 参数：若提供，对每个参数值调用 _coerce_param_value
    进行 schema 感知类型转换。

    Args:
        body: <invoke> 内部的原始字符串。
        func_name: 函数名，用于在 schema_index 中查找参数 schema。
        schema_index: _build_param_schema_index() 返回的索引，可为 None。

    Returns:
        JSON 格式的 arguments 字符串，无参数时返回 "{}"。
    """
    matches = list(_PARAM_NAME_RE.finditer(body))
    if not matches:
        return "{}"

    # 获取当前函数的参数 schema 映射
    param_schemas: Dict[str, Dict[str, Any]] = {}
    if schema_index and func_name:
        param_schemas = schema_index.get(func_name) or {}

    result: Dict[str, Any] = {}
    for m in matches:
        pname = m.group(1)
        pval = m.group(2).strip("\n")
        pschema = param_schemas.get(pname) or {}
        if pschema:
            result[pname] = _coerce_param_value(pval, pschema)
        else:
            # 无 schema → 原有启发式行为
            try:
                result[pname] = json.loads(pval)
            except json.JSONDecodeError:
                result[pname] = pval

    return json.dumps(result, ensure_ascii=False)


def _get_known_params(
    func_name: str,
    tools: Optional[List[Dict[str, Any]]],
) -> List[str]:
    """返回指定函数的已知参数名列表。"""
    if not tools:
        return []
    for t in tools:
        fn = t.get("function", t)
        if fn.get("name") == func_name:
            return list((fn.get("parameters") or {}).get("properties", {}).keys())
    return []


def _parse_func_body(
    body: str,
    func_name: str,
    tools: Optional[List[Dict[str, Any]]] = None,
    schema_index: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None,
) -> str:
    """将旧格式 <function=name> 标签体解析为 JSON arguments 字符串。"""
    known = _get_known_params(func_name, tools)
    param_schemas: Dict[str, Dict[str, Any]] = {}
    if schema_index and func_name:
        param_schemas = schema_index.get(func_name) or {}

    matches = list(_PARAM_RE.finditer(body))

    if matches:
        result: Dict[str, Any] = {}
        for m_obj in matches:
            pname = m_obj.group(1).strip()
            pval = m_obj.group(2).strip()
            if known and pname not in known:
                continue
            pschema = param_schemas.get(pname) or {}
            if pschema:
                result[pname] = _coerce_param_value(pval, pschema)
            else:
                try:
                    result[pname] = json.loads(pval)
                except json.JSONDecodeError:
                    result[pname] = pval
        if result:
            return json.dumps(result, ensure_ascii=False)

    stripped = body.strip()
    if stripped:
        try:
            json.loads(stripped)
            return stripped
        except json.JSONDecodeError:
            logger.debug(
                "_parse_func_body: 参数体非 JSON，回退为空对象: func=%s", func_name
            )

    return "{}"


def parse_fncall(
    text: str,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    """从文本中提取函数调用，返回 (清理后文本, tool_calls 列表)。

    解析优先级（互斥）：
    1. 新格式：<function_calls><invoke name="...">...</invoke></function_calls>
    2. 旧格式：<function=name>...</function>

    类型转换：
    若提供 tools，对每个参数值根据对应的 JSON Schema 做精确类型转换。
    """
    calls: List[Dict[str, Any]] = []

    # 预构建 schema 索引（O(n) 一次构建，避免每个参数重复线性搜索）
    schema_index = _build_param_schema_index(tools) if tools else None

    for block_m in _FNCALL_BLOCK_RE.finditer(text):
        block_body = block_m.group(1)
        for inv_m in _INVOKE_RE.finditer(block_body):
            func_name = inv_m.group(1).strip()
            body = inv_m.group(2)
            arguments = _parse_invoke_body(body, func_name, schema_index)
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {"name": func_name, "arguments": arguments},
                }
            )

    if not calls:
        for m_obj in _FUNC_RE.finditer(text):
            func_name = m_obj.group(1).strip()
            body = m_obj.group(2)
            arguments = _parse_func_body(body, func_name, tools, schema_index)
            calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {"name": func_name, "arguments": arguments},
                }
            )

    clean = text
    if calls:
        clean = _FNCALL_BLOCK_RE.sub("", clean)
        clean = _FUNC_RE.sub("", clean)
        clean = clean.strip()

    return clean, calls


# ---------------------------------------------------------------------------
# 流式解析状态机
# ---------------------------------------------------------------------------


class FncallStreamParser:
    """流式 fncall 检测与解析状态机。"""

    WAITING_FOR_TAG = "WAITING_FOR_TAG"
    IN_FUNCTION_CALLS = "IN_FUNCTION_CALLS"
    DONE = "DONE"

    _TRIGGER = "<function_calls>"
    _TRIGGER_LEGACY = "<function="
    _END_TAG = "</function_calls>"
    _END_TAG_LEGACY = _FE

    _ALL_TRIGGERS: List[str] = [_TRIGGER, _TRIGGER_LEGACY]

    def __init__(self, tools: Optional[List[Dict[str, Any]]] = None) -> None:
        self._tools = tools
        self._raw_buf: str = ""
        self._text_parts: List[str] = []
        self._waiting_tail: str = ""
        self._fncall_buf: str = ""
        self._detected: bool = False
        self._use_legacy_end: bool = False
        self._state: str = self.WAITING_FOR_TAG
        self._finalized_result: Optional[Tuple[str, List[Dict[str, Any]]]] = None

    @staticmethod
    def _split_safe_text(
        buffer: str,
        tags: List[str],
    ) -> Tuple[str, str]:
        """将 buffer 分为「可安全输出的前缀」和「需保留的尾部（真前缀）」。"""
        if not buffer:
            return "", ""

        max_keep = max(len(t) - 1 for t in tags)
        check_len = min(len(buffer), max_keep)

        for length in range(check_len, 0, -1):
            suffix = buffer[-length:]
            if any(tag.startswith(suffix) and suffix != tag for tag in tags):
                return buffer[:-length], buffer[-length:]

        return buffer, ""

    def _find_trigger(self, text: str) -> Tuple[int, str]:
        """在 text 中查找最早出现的触发标签，相同位置优先新格式。"""
        idx_new = text.find(self._TRIGGER)
        idx_legacy = text.find(self._TRIGGER_LEGACY)

        if idx_new == -1 and idx_legacy == -1:
            return -1, ""
        if idx_new == -1:
            return idx_legacy, self._TRIGGER_LEGACY
        if idx_legacy == -1:
            return idx_new, self._TRIGGER
        if idx_new <= idx_legacy:
            return idx_new, self._TRIGGER
        return idx_legacy, self._TRIGGER_LEGACY

    def _is_call_closed(self) -> bool:
        """检测 fncall 缓冲区中是否包含结束标签。"""
        if self._use_legacy_end:
            return self._END_TAG_LEGACY in self._fncall_buf
        return (
            self._END_TAG in self._fncall_buf
            or self._END_TAG_LEGACY in self._fncall_buf
        )

    def _feed_waiting(self, chunk: str) -> None:
        """在 WAITING_FOR_TAG 状态下处理新块。"""
        combined = self._waiting_tail + chunk
        idx, tag = self._find_trigger(combined)

        if idx == -1:
            safe, remain = self._split_safe_text(combined, self._ALL_TRIGGERS)
            if safe:
                self._text_parts.append(safe)
            self._waiting_tail = remain
            return

        if idx > 0:
            self._text_parts.append(combined[:idx])

        self._fncall_buf = combined[idx:]
        self._waiting_tail = ""
        self._detected = True
        self._use_legacy_end = (tag == self._TRIGGER_LEGACY)
        self._state = self.IN_FUNCTION_CALLS

        if self._is_call_closed():
            self._state = self.DONE

    def feed(self, chunk: str) -> None:
        """喂入新的流式文本块。DONE 或 finalize 后调用静默忽略。"""
        if not chunk or self._state == self.DONE:
            return
        if self._finalized_result is not None:
            return

        self._raw_buf += chunk

        if self._state == self.WAITING_FOR_TAG:
            self._feed_waiting(chunk)
        else:
            self._fncall_buf += chunk
            if self._is_call_closed():
                self._state = self.DONE

    def finalize(self) -> Tuple[str, List[Dict[str, Any]]]:
        """结束流式解析，返回 (清理后文本, tool_calls 列表)。幂等。"""
        if self._finalized_result is not None:
            return self._finalized_result

        self._state = self.DONE

        if not self._detected:
            full_text = "".join(self._text_parts) + self._waiting_tail
            result = parse_fncall(full_text, self._tools)
        else:
            clean_text = "".join(self._text_parts).strip()
            _, tool_calls = parse_fncall(self._fncall_buf, self._tools)
            result = (clean_text, tool_calls)

        self._finalized_result = result
        return result

    @property
    def state(self) -> str:
        """当前状态：WAITING_FOR_TAG / IN_FUNCTION_CALLS / DONE。"""
        return self._state

    @property
    def has_calls(self) -> bool:
        """是否已检测到 fncall 触发标签。"""
        return self._detected

    @property
    def partial_text(self) -> str:
        """已确认的非 fncall 文本片段（可用于流式 UI 实时展示）。"""
        return "".join(self._text_parts)


# ---------------------------------------------------------------------------
# XML 片段直接解析（外部调用接口）
# ---------------------------------------------------------------------------


def parse_fncall_xml(
    xml: str,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """将 function_calls XML 片段直接解析为 OpenAI tool_calls 格式列表。

    新增 tools 参数：若提供，对参数值做 schema 感知类型转换。

    Args:
        xml: 包含 <invoke> 块的 XML 字符串。
        tools: 工具定义列表，用于类型转换（可为 None）。

    Returns:
        tool_calls 列表；解析失败时返回 []。
    """
    tool_calls: List[Dict[str, Any]] = []
    schema_index = _build_param_schema_index(tools) if tools else None

    try:
        for match in _INVOKE_RE.finditer(xml):
            func_name = match.group(1).strip()
            params_xml = match.group(2)
            param_schemas: Dict[str, Dict[str, Any]] = {}
            if schema_index:
                param_schemas = schema_index.get(func_name) or {}

            arguments: Dict[str, Any] = {}
            for pm in _PARAM_NAME_RE.finditer(params_xml):
                key = pm.group(1).strip()
                val = pm.group(2).strip()
                pschema = param_schemas.get(key) or {}
                if pschema:
                    arguments[key] = _coerce_param_value(val, pschema)
                else:
                    try:
                        arguments[key] = json.loads(val)
                    except (json.JSONDecodeError, ValueError):
                        arguments[key] = val

            tool_calls.append(
                {
                    "id": f"call_{uuid.uuid4().hex[:24]}",
                    "type": "function",
                    "function": {
                        "name": func_name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
    except Exception as exc:
        logger.warning("parse_fncall_xml 解析失败: %s", exc)

    return tool_calls
