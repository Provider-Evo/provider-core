# tests/src/core/fncall/test_dsml_protocol.py
"""Test DsmlProtocol with DSML namespace."""

import json

import pytest

from src.core.fncall.protocols.dsml import DsmlProtocol


# DSML uses fullwidth vertical line U+FF5C (｜) as delimiter.
_DSML_START = "<\uff5c\uff5cDSML\uff5c\uff5ctool_calls>"
_DSML_END = "</\uff5c\uff5cDSML\uff5c\uff5ctool_calls>"
_DSML_CALL_START = "<\uff5c\uff5cDSML\uff5c\uff5ctool_call>"
_DSML_CALL_END = "</\uff5c\uff5cDSML\uff5c\uff5ctool_call>"
_DSML_NAME = lambda n: f"<\uff5c\uff5cDSML\uff5c\uff5ctool_name>{n}</\uff5c\uff5cDSML\uff5c\uff5ctool_name>"
_DSML_PARAM = lambda k, v: f'<\uff5c\uff5cDSML\uff5c\uff5cparameter name="{k}">{v}</\uff5c\uff5cDSML\uff5c\uff5cparameter>'
_DSML_PARAMS_START = "<\uff5c\uff5cDSML\uff5c\uff5ctool_parameters>"
_DSML_PARAMS_END = "</\uff5c\uff5cDSML\uff5c\uff5ctool_parameters>"
_DSML_RESULT = lambda cid, c: f'<\uff5c\uff5cDSML\uff5c\uff5ctool_result tool_call_id="{cid}">{c}</\uff5c\uff5cDSML\uff5c\uff5ctool_result>'


def _make_dsml_block(*calls):
    """Build a complete DSML block from call bodies."""
    return _DSML_START + "\n" + "\n".join(calls) + "\n" + _DSML_END


def _make_dsml_call(name, params):
    """Build a single DSML tool_call element.

    *params* is a dict mapping parameter name to string value.
    """
    param_tags = "\n".join(_DSML_PARAM(k, v) for k, v in params.items())
    return (
        f"{_DSML_CALL_START}\n"
        f"{_DSML_NAME(name)}\n"
        f"{_DSML_PARAMS_START}\n{param_tags}\n{_DSML_PARAMS_END}\n"
        f"{_DSML_CALL_END}"
    )


class TestDsmlProtocol:
    """Test DsmlProtocol basic operations."""

    @pytest.fixture
    def protocol(self):
        return DsmlProtocol()

    def test_id(self, protocol):
        assert protocol.id == "dsml"

    def test_supports_streaming(self, protocol):
        assert protocol.supports_streaming() is True

    def test_trigger_tags(self, protocol):
        tags = protocol.get_trigger_tags()
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_calls>" in tags

    def test_detect_start(self, protocol):
        found, pos = protocol.detect_start("<\uff5c\uff5cDSML\uff5c\uff5ctool_calls>")
        assert found is True
        assert pos == 0

    def test_detect_start_negative(self, protocol):
        found, pos = protocol.detect_start("just some unrelated text")
        assert found is False
        assert pos == -1

    def test_render_prompt_has_dsml_format(self, protocol):
        prompt = protocol.render_prompt("Tool: test", "en")
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_calls>" in prompt
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_call>" in prompt
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_name>" in prompt
        assert "<\uff5c\uff5cDSML\uff5c\uff5cparameter" in prompt

    def test_render_prompt_interpolates_tool_descs(self, protocol):
        tool_descs = "Tool: Bash - Executes a shell command. Parameter: command (string) - The command to run."
        prompt = protocol.render_prompt(tool_descs, "en")
        assert "Bash" in prompt, "rendered prompt should contain the tool name from tool_descs"
        assert "command" in prompt, "rendered prompt should contain the parameter name from tool_descs"
        assert "{tool_descs}" not in prompt, "rendered prompt must not contain the literal '{tool_descs}' placeholder"

    def test_render_prompt_no_double_wrapping(self, protocol):
        """Verify render_prompt does not double-wrap sections when given raw values."""
        prompt = protocol.render_prompt(
            "tools",
            "en",
            history_text="prev conversation",
            loop_warning="avoid repeating",
            current_user_message="user question",
        )
        assert prompt.count("<conversation_history>") == 1, "conversation_history should appear exactly once"
        assert prompt.count("<loop_warning>") == 1, "loop_warning should appear exactly once"
        assert prompt.count("<current_user_message>") == 1, "current_user_message should appear exactly once"

    def test_parse_single_call(self, protocol):
        text = _make_dsml_block(
            _make_dsml_call("Bash", {"command": "echo hello"})
        )
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "Bash"
        args = json.loads(tool_calls[0]["function"]["arguments"])
        assert args["command"] == "echo hello"

    def test_parse_multiple_calls(self, protocol):
        text = _make_dsml_block(
            _make_dsml_call("Bash", {"command": "echo hello"}),
            _make_dsml_call("Read", {"file_path": "/tmp/test.txt"}),
        )
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 2
        assert tool_calls[0]["function"]["name"] == "Bash"
        assert tool_calls[1]["function"]["name"] == "Read"

    def test_parse_no_calls(self, protocol):
        clean, tool_calls = protocol.parse("no tool calls here")
        assert tool_calls == []

    def test_parse_fragment(self, protocol):
        fragment = _make_dsml_block(
            _make_dsml_call("Bash", {"command": "echo hello"})
        )
        tool_calls = protocol.parse_fragment(fragment)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "Bash"
        args = json.loads(tool_calls[0]["function"]["arguments"])
        assert args["command"] == "echo hello"

    def test_format_assistant_tool_calls(self, protocol):
        tool_calls = [
            {
                "id": "call_123",
                "function": {"name": "Bash", "arguments": '{"command": "echo hello"}'},
            }
        ]
        result = protocol.format_assistant_tool_calls(tool_calls)
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_calls>" in result
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_call>" in result
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_name>Bash</\uff5c\uff5cDSML\uff5c\uff5ctool_name>" in result
        assert '<\uff5c\uff5cDSML\uff5c\uff5cparameter name="command">' in result

    def test_format_tool_result(self, protocol):
        result = protocol.format_tool_result("output", tool_call_id="call_123")
        assert '<\uff5c\uff5cDSML\uff5c\uff5ctool_result tool_call_id="call_123">' in result
        assert "output" in result
        assert "</\uff5c\uff5cDSML\uff5c\uff5ctool_result>" in result

    def test_clean_tags(self, protocol):
        block = _make_dsml_block(
            _make_dsml_call("X", {"a": "b"})
        )
        content = f"text{block}more"
        cleaned = protocol.clean_tags(content)
        assert "<\uff5c\uff5cDSML\uff5c\uff5ctool_calls>" not in cleaned
        assert "text" in cleaned
        assert "more" in cleaned
