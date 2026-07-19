"""Anthropic ML (antml) 协议实现。

使用 <function_calls> 作为触发标记，
<invoke name="..."> 作为调用格式。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from echotools.fncall.prompt.templates import (
    _HISTORY_CLARIFY_EN,
    _HISTORY_CLARIFY_ZH,
)
from echotools.fncall.shared.coercion import (
    _build_param_schema_index,
    _coerce_param_value,
)
from echotools.logger.manager import get_logger
from echotools.protocol.base import ToolProtocol

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 硬编码 Prompt 指令
# ---------------------------------------------------------------------------

_ANTML_INSTRUCTION = """\
## Function Definitions

All functions are defined inside a `<functions>` wrapper block. Each function is a JSON object inside a `<function>` tag containing `description`, `name`, and `parameters` (JSON Schema).

**Function Invocation Syntax:**

When calling tools, respond with ONLY the following XML block format:

<function_calls>
<invoke name="tool_name">
<parameters>{"param_name": "value"}</parameters>
</invoke>
</function_calls>

Multiple invocations can be stacked inside one `<function_calls>` block for parallel execution.

## Function Call Instructions

When making function calls using tools that accept array or object parameters, ensure those are structured using JSON.

Answer the user's request using the relevant tool(s), if they are available. Check that all required parameters are provided or can reasonably be inferred from context. If there are no relevant tools or missing required parameter values, ask the user. If the user provides a specific value for a parameter (e.g., in quotes), use that value EXACTLY. Do NOT make up values for or ask about optional parameters.

If you intend to call multiple tools and there are no dependencies between the calls, make all independent calls in the same function_calls block. Otherwise, wait for previous calls to finish to determine dependent values (do NOT use placeholders or guess missing parameters).
"""

# ---------------------------------------------------------------------------
# 正则常量
# ---------------------------------------------------------------------------

_BLOCK_RE = re.compile(
    r"<function_calls\b[^>]*>([\s\S]*?)</function_calls>",
    re.DOTALL,
)
_INVOKE_RE = re.compile(
    r'<invoke\s+name="([^"]+)">\s*([\s\S]*?)\s*</invoke>',
    re.DOTALL,
)
_PARAM_RE = re.compile(
    r'<parameter\s+name="([^"]+)">\s*([\s\S]*?)\s*</parameter>',
    re.DOTALL,
)
_PARAMETERS_RE = re.compile(
    r'<parameters>([\s\S]*?)</parameters>',
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Antml 协议
# ---------------------------------------------------------------------------


class AntmlProtocol(ToolProtocol):
    """Anthropic ML 格式工具调用协议适配器。

    使用 <function_calls><invoke name="...">...</invoke>
    作为触发标记和调用格式。
    """

    @property
    def id(self) -> str:
        return "antml"

    _TRIGGER = "<function_calls>"
    _END_TAG = "</function_calls>"

    def get_trigger_tags(self) -> List[str]:
        return [self._TRIGGER]

    def render_prompt(
        self,
        tool_descs: str,
        lang: str,
        user_system_prompt: str = "",
        history_text: str = "",
        loop_warning: str = "",
        current_user_message: str = "",
    ) -> str:
        """构建完整的 prompt 字符串，注入工具定义。"""
        sections: List[str] = [_ANTML_INSTRUCTION]

        # Add tool definitions in a functions block
        sections.append("<functions>\n" + tool_descs + "\n</functions>")

        if user_system_prompt and user_system_prompt.strip():
            sections.append(
                "<user_system_prompt>\n{}\n</user_system_prompt>".format(user_system_prompt.strip())
            )

        if history_text:
            clarify = _HISTORY_CLARIFY_ZH if lang == "zh" else _HISTORY_CLARIFY_EN
            sections.append(
                "<conversation_history>\n{}\n\n{}\n</conversation_history>".format(clarify, history_text)
            )

        if loop_warning:
            sections.append("<loop_warning>\n{}\n</loop_warning>".format(loop_warning))

        if current_user_message:
            sections.append(
                "<current_user_message>\n{}\n</current_user_message>".format(current_user_message)
            )
        else:
            sections.append("<current_user_message>\n</current_user_message>")

        prompt = "\n\n".join(sections)

        return prompt

    _TRIGGER_PREFIX = "<function_calls"

    def detect_start(self, buffer: str) -> Tuple[bool, int]:
        """检测 buffer 中是否包含 ``<function_calls...>`` 触发标记。

        容忍变体（如 ``<function_calls >`` 或带属性），只要前缀
        ``<function_calls`` 后跟任意字符并以 ``>`` 闭合即视为触发。
        """
        pos = buffer.find(self._TRIGGER_PREFIX)
        if pos < 0:
            return (False, -1)
        close = buffer.find(">", pos + len(self._TRIGGER_PREFIX))
        if close < 0:
            # 标签未闭合：视为待流入的增量
            return (False, -1)
        return (True, pos)

    def _extract_args_from_parameters_json(self, body: str) -> Optional[Dict[str, Any]]:
        """尝试从 <parameters>{json}</parameters> 格式中提取参数。"""
        params_m = _PARAMETERS_RE.search(body)
        if not params_m:
            return None
        params_json = params_m.group(1).strip()
        try:
            return json.loads(params_json)
        except json.JSONDecodeError:
            return {"value": params_json}

    def _extract_args_from_parameter_tags(
        self,
        body: str,
        name: str,
        schema_index: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """从 <parameter name="...">value</parameter> 格式中提取参数。"""
        args: Dict[str, Any] = {}
        for param_m in _PARAM_RE.finditer(body):
            pname = param_m.group(1).strip()
            pval = param_m.group(2).strip()
            pschema = (
                schema_index.get(name, {}).get(pname, {})
                if schema_index
                else {}
            )
            if pschema:
                args[pname] = _coerce_param_value(pval, pschema)
            else:
                try:
                    args[pname] = json.loads(pval)
                except json.JSONDecodeError:
                    args[pname] = pval
        return args

    def _extract_invoke_args(
        self,
        body: str,
        name: str,
        schema_index: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """从单个 invoke 体中提取参数，兼容两种参数格式。"""
        args = self._extract_args_from_parameters_json(body)
        if args is not None:
            return args
        return self._extract_args_from_parameter_tags(body, name, schema_index)

    def _parse_block(
        self,
        block_body: str,
        schema_index: Optional[Dict[str, Any]],
        tool_calls: List[Dict[str, Any]],
    ) -> None:
        """解析单个 <function_calls> 块内的所有 invoke，追加到 tool_calls。"""
        for invoke_m in _INVOKE_RE.finditer(block_body):
            name = invoke_m.group(1).strip()
            body = invoke_m.group(2)
            args = self._extract_invoke_args(body, name, schema_index)
            arguments = json.dumps(args, ensure_ascii=False)
            tool_calls.append(
                {
                    "id": "call_{:04d}".format(len(tool_calls)),
                    "type": "function",
                    "function": {"name": name, "arguments": arguments},
                }
            )

    def parse(
        self,
        text: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """从文本中提取工具调用，返回 (清理后文本, tool_calls 列表)。"""
        tool_calls: List[Dict[str, Any]] = []
        schema_index: Optional[Dict[str, Any]] = None

        for block_m in _BLOCK_RE.finditer(text):
            block_body = block_m.group(1)

            # Build schema index lazily on first invocation
            if schema_index is None and tools is not None:
                schema_index = _build_param_schema_index(tools)

            self._parse_block(block_body, schema_index, tool_calls)

        clean = text
        if tool_calls:
            clean = _BLOCK_RE.sub("", text).strip()

        return (clean, tool_calls)

    def parse_fragment(
        self,
        fragment: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """将已知的完整 antml 片段直接解析为 tool_calls 列表。"""
        _, tool_calls = self.parse(fragment, tools)
        return tool_calls

    def clean_tags(self, content: str) -> str:
        """从响应文本中移除 <function_calls> 标签残留。"""
        return _BLOCK_RE.sub("", content).strip()

    def format_assistant_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
    ) -> str:
        """将 tool_call 对象列表渲染为 antml 格式。"""
        if not tool_calls:
            return ""

        parts: List[str] = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name", "")
            args = fn.get("arguments", "{}")
            parts.append(
                '<invoke name="{}">'
                "<parameters>{}</parameters>"
                "</invoke>".format(name, args)
            )
        return "<function_calls>{}</function_calls>".format(''.join(parts))

    def supports_streaming(self) -> bool:
        """antml 协议支持流式检测。"""
        return True
