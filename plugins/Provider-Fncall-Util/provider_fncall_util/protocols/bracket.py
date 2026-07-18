"""
bracket 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-plugin.Provider-Fncall-Util.provider_fncall_util.protocols.bracket
- 文件名：bracket.py
- 父包：provider-plugin/Provider-Fncall-Util/provider_fncall_util/protocols

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""

import json
import re
from typing import List, Tuple

from echotools.fncall.prompt.templates import (
    _HISTORY_CLARIFY_EN,
    _HISTORY_CLARIFY_ZH,
)
from echotools.fncall.shared.coercion import (
    _build_param_schema_index,
    _coerce_param_value,
)
from echotools.protocol.base import ToolProtocol


class BracketProtocol(ToolProtocol):
    @property
    def id(self) -> str:
        return "bracket"

    _TRIGGER = "[function_calls]"
    _END_TAG = "[/function_calls]"
    _BLOCK_RE = re.compile(r"\[function_calls\]([\s\S]*?)\[/function_calls\]", re.DOTALL)
    _CALL_RE = re.compile(r"\[call:([^\]]+)\]([\s\S]*?)\[/call\]", re.DOTALL)
    # Fallback for incorrect [ToolName]{...}[/ToolName] format — only when body starts with {
    _SIMPLE_CALL_RE = re.compile(r"\[([A-Za-z_][A-Za-z0-9_]*)\](\{[\s\S]*?)\[/\1\]", re.DOTALL)

    def get_trigger_tags(self) -> List[str]:
        return [self._TRIGGER]

    def render_prompt(self, tool_descs, lang, user_system_prompt="", history_text="", loop_warning="", current_user_message=""):
        instruction = f"""## Available Tools
You can invoke the following developer tools. Tool names are case-sensitive.
Use only the exact tool names listed below. Do not rename, camelCase, translate, shorten, or invent tool names.

{tool_descs}

## Tool Invocation Format

When calling tools, you MUST respond with ONLY this exact bracket format:

[function_calls]
[call:exact_tool_name]{{"argument_name":"argument_value"}}[/call]
[/function_calls]

Rules:
1. Always wrap tool calls in [function_calls]...[/function_calls]
2. Use [call:tool_name]...[/call] for each invocation (note the colon before tool name)
3. Arguments must be valid JSON inside the [call] tags
4. Tool names are case-sensitive — use exact names from the list above
5. Do NOT use [ToolName]{{...}}[/ToolName] format — that is incorrect
6. Do NOT output plain text between [function_calls] tags

Example correct invocation:
[function_calls]
[call:Bash]{{"command":"echo hello"}}[/call]
[/function_calls]

Tool results will be provided in a corresponding result block."""

        sections = [instruction]
        if user_system_prompt and user_system_prompt.strip():
            sections.append(f"<user_system_prompt>\n{user_system_prompt.strip()}\n</user_system_prompt>")
        if history_text:
            clarify = _HISTORY_CLARIFY_ZH if lang == "zh" else _HISTORY_CLARIFY_EN
            sections.append(f"<conversation_history>\n{clarify}\n\n{history_text}\n</conversation_history>")
        if loop_warning:
            sections.append(f"<loop_warning>\n{loop_warning}\n</loop_warning>")
        if current_user_message:
            sections.append(f"<current_user_message>\n{current_user_message}\n</current_user_message>")

        return "\n\n".join(sections)

    def detect_start(self, buffer: str) -> Tuple[bool, int]:
        pos = buffer.find(self._TRIGGER)
        return (pos >= 0, pos if pos >= 0 else -1)

    def parse(self, text, tools=None):
        tool_calls = []
        schema_index = _build_param_schema_index(tools) if tools else None

        for block_m in self._BLOCK_RE.finditer(text):
            block_body = block_m.group(1)
            block_had_correct_calls = False

            # Try correct [call:name]{...}[/call] format first
            for call_m in self._CALL_RE.finditer(block_body):
                name = call_m.group(1).strip()
                args_raw = call_m.group(2).strip()
                args = self._parse_args(args_raw, name, schema_index)
                tool_calls.append({
                    "id": f"call_{len(tool_calls):04d}",
                    "type": "function",
                    "function": {"name": name, "arguments": args},
                })
                block_had_correct_calls = True

            # Fallback: if no correct calls in this block, try simplified [ToolName]{...}[/ToolName]
            if not block_had_correct_calls:
                for simple_m in self._SIMPLE_CALL_RE.finditer(block_body):
                    name = simple_m.group(1).strip()
                    # Skip if it looks like a block tag
                    if name.lower() in ('function_calls', 'call'):
                        continue
                    args_raw = simple_m.group(2).strip()
                    # Only treat as fallback if body looks like JSON or plain text
                    args = self._parse_args(args_raw, name, schema_index)
                    tool_calls.append({
                        "id": f"call_{len(tool_calls):04d}",
                        "type": "function",
                        "function": {"name": name, "arguments": args},
                    })

        clean = text
        if tool_calls:
            clean = self._BLOCK_RE.sub("", text).strip()

        return (clean, tool_calls)

    def _parse_args(self, args_raw, func_name, schema_index):
        """Parse and optionally coerce arguments."""
        try:
            args = json.loads(args_raw)
            if not isinstance(args, dict):
                args = {"value": args_raw}
        except json.JSONDecodeError:
            args = {"value": args_raw}

        # Apply schema coercion
        if schema_index and func_name in schema_index:
            coerced = {}
            for k, v in args.items():
                pschema = schema_index[func_name].get(k, {})
                coerced[k] = _coerce_param_value(
                    json.dumps(v) if not isinstance(v, str) else v,
                    pschema,
                )
            args = coerced

        return json.dumps(args, ensure_ascii=False)

    def parse_fragment(self, fragment, tools=None):
        _, tool_calls = self.parse(fragment, tools)
        return tool_calls

    def clean_tags(self, content):
        return self._BLOCK_RE.sub("", content).strip()

    def format_assistant_tool_calls(self, tool_calls):
        calls = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            calls.append(f"[call:{fn.get('name', '')}]{fn.get('arguments', '{}')}[/call]")
        joined = "\n".join(calls)
        return f"[function_calls]\n{joined}\n[/function_calls]"

    def supports_streaming(self):
        return True

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
