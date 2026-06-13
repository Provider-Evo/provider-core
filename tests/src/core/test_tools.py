"""Tests for src/core/tools.py."""

import json
import sys
import os

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.core.tools import (
    normalize_content,
    format_tool_descs,
    parse_fncall,
    parse_fncall_xml,
    FncallStreamParser,
)
from echotools.fncall.prompt.history import _render_tool_call, _render_tool_result
from echotools.fncall.prompt.inject import _format_conversation_history, _normalize_messages

SAMPLE_TOOL = {
    "type": "function",
    "function": {
        "name": "Bash",
        "description": "Run a shell command",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The command to run"},
                "description": {"type": "string", "description": "Short description"},
            },
            "required": ["command"],
        },
    },
}

SAMPLE_TC = {
    "id": "call_abc123",
    "type": "function",
    "function": {
        "name": "Bash",
        "arguments": json.dumps({"command": "echo hello"}),
    },
}


def test_normalize_str():
    assert normalize_content("hello") == "hello"

def test_normalize_none():
    assert normalize_content(None) == ""

def test_normalize_list():
    assert normalize_content(["a", "b"]) == "a\nb"

def test_normalize_dict_text():
    assert normalize_content({"text": "hi"}) == "hi"


def test_format_tool_descs():
    out = format_tool_descs([SAMPLE_TOOL])
    assert 'name="Bash"' in out
    assert "parameters" in out


def test_render_tool_call():
    out = _render_tool_call(SAMPLE_TC)
    assert "<function_calls>" in out
    assert 'name="Bash"' in out
    assert "</function_calls>" in out


def test_render_tool_result():
    out = _render_tool_result("output", "Bash")
    assert "<function_results>" in out
    assert "<tool_name>Bash</tool_name>" in out
    assert "<stdout>" in out
    assert "output" in out


def test_format_history_empty():
    assert _format_conversation_history([]) == ""


def test_format_history_single_user():
    msgs = [{"role": "user", "content": "hi"}]
    out = _format_conversation_history(msgs)
    assert "<user>" in out
    assert "hi" in out


def test_format_history_user_assistant():
    msgs = [
        {"role": "user", "content": "run ls"},
        {"role": "assistant", "content": "ok", "tool_calls": [SAMPLE_TC]},
    ]
    out = _format_conversation_history(msgs)
    assert "<user>" in out
    assert "run ls" in out
    assert "<assistant>" in out
    assert "ok" in out
    # is_webui removed — tool_calls are always rendered
    assert "<function_calls>" in out


def test_dedup_adjacent_identical_assistant():
    """Two consecutive identical assistant messages should produce only one."""
    assistant_msg = {"role": "assistant", "content": "testing", "tool_calls": [SAMPLE_TC]}
    msgs = [
        {"role": "user", "content": "test"},
        assistant_msg,
        assistant_msg,
    ]
    out = _format_conversation_history(msgs)
    count = out.count("<assistant>")
    assert count == 1, f"Expected 1 assistant block, got {count}"


def test_dedup_non_adjacent_with_tool_between():
    """Same assistant msg appearing twice with a tool result between them should still dedup."""
    assistant_msg = {"role": "assistant", "content": "testing", "tool_calls": [SAMPLE_TC]}
    tool_msg = {
        "role": "tool",
        "tool_call_id": "call_abc123",
        "content": "hello",
    }
    msgs = [
        {"role": "user", "content": "test"},
        assistant_msg,
        tool_msg,
        assistant_msg,
        {"role": "user", "content": "again"},
    ]
    out = _format_conversation_history(msgs)
    count = out.count("<assistant>")
    assert count == 1, f"Expected 1 assistant block, got {count}"


def test_dedup_multiple_different_assistant_preserved():
    """Different assistant messages should all be preserved."""
    tc2 = {
        "id": "call_xyz789",
        "type": "function",
        "function": {"name": "Glob", "arguments": "{}"},
    }
    msgs = [
        {"role": "user", "content": "step1"},
        {"role": "assistant", "content": "first", "tool_calls": [SAMPLE_TC]},
        {"role": "tool", "tool_call_id": "call_abc123", "content": "out1"},
        {"role": "assistant", "content": "second", "tool_calls": [tc2]},
        {"role": "user", "content": "step2"},
    ]
    out = _format_conversation_history(msgs)
    count = out.count("<assistant>")
    assert count == 2, f"Expected 2 assistant blocks, got {count}"
    assert "first" in out
    assert "second" in out


def test_dedup_same_content_different_tool_call_ids():
    """Same assistant text content with different tool_call IDs should still dedup.

    This is the real-world deadlock scenario: LLM generates the same response
    (same text, same tool call) each round, but each round has a different
    tool_call ID. Dedup must be based on (content, function_name+arguments),
    not (content, tool_call_id).
    """
    def make_tc(tool_id):
        return {
            "id": tool_id,
            "type": "function",
            "function": {"name": "Bash", "arguments": json.dumps({"command": "echo hi"})},
        }
    assistant1 = {"role": "assistant", "content": "running", "tool_calls": [make_tc("call_r1")]}
    assistant2 = {"role": "assistant", "content": "running", "tool_calls": [make_tc("call_r2")]}
    assistant3 = {"role": "assistant", "content": "running", "tool_calls": [make_tc("call_r3")]}
    msgs = [
        {"role": "user", "content": "go"},
        assistant1,
        {"role": "tool", "tool_call_id": "call_r1", "content": "out1"},
        assistant2,
        {"role": "tool", "tool_call_id": "call_r2", "content": "out2"},
        assistant3,
        {"role": "tool", "tool_call_id": "call_r3", "content": "out3"},
        {"role": "user", "content": "next"},
    ]
    out = _format_conversation_history(msgs)
    a_count = out.count("<assistant>")
    fr_count = out.count("<function_results>")
    assert a_count == 1, f"Expected 1 assistant block, got {a_count}"
    assert fr_count == 3, f"Expected 3 tool result blocks, got {fr_count}"


def test_dedup_different_tool_calls_not_deduped():
    """Assistant messages calling different tools should NOT be deduped."""
    tc1 = {"id": "call_1", "type": "function", "function": {"name": "Bash", "arguments": "{}"}}
    tc2 = {"id": "call_2", "type": "function", "function": {"name": "Glob", "arguments": "{}"}}
    msgs = [
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": "step1", "tool_calls": [tc1]},
        {"role": "tool", "tool_call_id": "call_1", "content": "bash_out"},
        {"role": "assistant", "content": "step2", "tool_calls": [tc2]},
        {"role": "tool", "tool_call_id": "call_2", "content": "glob_out"},
    ]
    out = _format_conversation_history(msgs)
    a_count = out.count("<assistant>")
    assert a_count == 2, f"Expected 2 assistant blocks (different calls), got {a_count}"


def test_dedup_many_copies_of_same_assistant():
    """9 copies of the same assistant message should produce exactly 1."""
    assistant_msg = {"role": "assistant", "content": "repeat", "tool_calls": [SAMPLE_TC]}
    msgs = [{"role": "user", "content": "go"}] + [assistant_msg] * 9
    out = _format_conversation_history(msgs)
    count = out.count("<assistant>")
    assert count == 1, f"Expected 1 assistant block, got {count}"


def test_dedup_preserves_tool_results():
    """Tool results should NOT be deduplicated even if they have the same content."""
    assistant_msg = {"role": "assistant", "content": "run", "tool_calls": [SAMPLE_TC]}
    msgs = [
        {"role": "user", "content": "test"},
        assistant_msg,
        {"role": "tool", "tool_call_id": "call_abc123", "content": "result1"},
        assistant_msg,
        {"role": "tool", "tool_call_id": "call_abc123", "content": "result2"},
    ]
    out = _format_conversation_history(msgs)
    assistant_count = out.count("<assistant>")
    assert assistant_count == 1, f"Expected 1 assistant block, got {assistant_count}"
    tool_count = out.count("<function_results>")
    assert tool_count == 2, f"Expected 2 tool result blocks, got {tool_count}"


def test_normalize_messages_pseudo_tool_call():
    line = "Tool call (toolu_bdrk123): Bash({\"command\": \"ls\"})"
    msgs = [{"role": "assistant", "content": line}]
    result = _normalize_messages(msgs)
    assert result[0].get("tool_calls") is not None
    assert result[0]["tool_calls"][0]["function"]["name"] == "Bash"


def test_normalize_messages_pseudo_tool_result():
    assistant_msg = {
        "role": "assistant",
        "tool_calls": [{
            "id": "toolu_bdrk123",
            "type": "function",
            "function": {"name": "Bash", "arguments": "{}"},
        }],
    }
    user_msg = {
        "role": "user",
        "content": "Tool result (toolu_bdrk123): output here",
    }
    msgs = [assistant_msg, user_msg]
    result = _normalize_messages(msgs)
    roles = [m.get("role") for m in result]
    assert "tool" in roles
    tool_msg = [m for m in result if m.get("role") == "tool"][0]
    assert tool_msg["tool_call_id"] == "toolu_bdrk123"
    assert "output here" in tool_msg["content"]


LT = chr(60)
GT = chr(62)

def _invoke_xml(name, params):
    parts = [LT + 'invoke name="' + name + '"' + GT]
    for k, v in params.items():
        parts.append(LT + 'parameter name="' + k + '"' + GT + v + LT + '/parameter' + GT)
    parts.append(LT + '/invoke' + GT)
    return "".join(parts)

def _fncall_xml(calls):
    wrapper = f"{LT}function_calls{GT}%s{LT}/function_calls{GT}"
    return wrapper % "".join(_invoke_xml(n, p) for n, p in calls)

def test_parse_fncall_xml_format():
    xml = _fncall_xml([("Bash", {"command": "ls"})])
    results = parse_fncall_xml(xml)
    assert len(results) == 1
    assert results[0]["function"]["name"] == "Bash"
    args = json.loads(results[0]["function"]["arguments"])
    assert args["command"] == "ls"

def test_parse_fncall_xml_multiple():
    xml = _fncall_xml([
        ("Bash", {"command": "echo hi"}),
        ("Glob", {"pattern": "*.py"}),
    ])
    results = parse_fncall_xml(xml)
    assert len(results) == 2
    assert results[0]["function"]["name"] == "Bash"
    assert results[1]["function"]["name"] == "Glob"

def test_parse_fncall_from_text():
    tc_name = "Bash"
    xml_block = _fncall_xml([(tc_name, {"command": "pwd"})])
    text = f"Let me check.\n\n{xml_block}\n\nDone."
    cleaned, calls = parse_fncall(text)
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == tc_name
    assert "Let me check." in cleaned
    assert "Done." in cleaned
    assert xml_block not in cleaned

def test_fncall_stream_parser_no_call():
    parser = FncallStreamParser()
    for chunk in ["Hello", " world", "!"]:
        parser.feed(chunk)
    text, calls = parser.finalize()
    assert not parser.has_calls
    assert calls == []
    assert text == "Hello world!"

def test_fncall_stream_parser_with_call():
    from src.core.fncall.base import get_protocol_by_id
    xml = _fncall_xml([("Bash", {"command": "date"})])
    parser = FncallStreamParser(protocol=get_protocol_by_id("xml"))
    for chunk in ["wait " + xml, " done"]:
        parser.feed(chunk)
    text, calls = parser.finalize()
    assert parser.has_calls
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "Bash"
    # Text before the trigger tag is preserved
    assert "wait" in text

def test_fncall_stream_parser_split_across_chunks():
    from src.core.fncall.base import get_protocol_by_id
    xml = _fncall_xml([("Bash", {"command": "whoami"})])
    mid = len(xml) // 2
    parser = FncallStreamParser(protocol=get_protocol_by_id("xml"))
    parser.feed("start " + xml[:mid])
    parser.feed(xml[mid:] + " end")
    text, calls = parser.finalize()
    assert parser.has_calls
    assert len(calls) == 1
    assert calls[0]["function"]["name"] == "Bash"