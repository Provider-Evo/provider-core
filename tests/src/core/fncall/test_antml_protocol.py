"""Test AntmlProtocol."""

import pytest

from src.core.fncall.protocols.antml import AntmlProtocol


class TestAntmlProtocol:
    @pytest.fixture
    def protocol(self):
        return AntmlProtocol()

    def test_id(self, protocol):
        assert protocol.id == "antml"

    def test_supports_streaming(self, protocol):
        assert protocol.supports_streaming() is True

    def test_trigger_tags(self, protocol):
        tags = protocol.get_trigger_tags()
        assert "<antml:function_calls>" in tags

    def test_detect_start(self, protocol):
        found, pos = protocol.detect_start('<antml:function_calls>')
        assert found is True
        assert pos == 0

    def test_detect_start_not_found(self, protocol):
        found, pos = protocol.detect_start("just some text")
        assert found is False

    def test_render_prompt_has_functions_block(self, protocol):
        prompt = protocol.render_prompt('{"name": "test"}', "en")
        assert "<functions>" in prompt
        assert "</functions>" in prompt

    def test_render_prompt_has_invocation_syntax(self, protocol):
        prompt = protocol.render_prompt("", "en")
        assert "<antml:function_calls>" in prompt
        assert "<antml:invoke" in prompt
        assert "<antml:parameters>" in prompt

    def test_render_prompt_interpolates_tool_descs(self, protocol):
        tool_descs = 'Tool: Bash - Executes a shell command. Parameter: command (string) - The command to run.'
        prompt = protocol.render_prompt(tool_descs, "en")
        assert "Bash" in prompt, "rendered prompt should contain the tool name from tool_descs"
        assert "command" in prompt, "rendered prompt should contain the parameter name from tool_descs"
        assert "{tool_descs}" not in prompt, "rendered prompt must not contain the literal '{tool_descs}' placeholder"

    def test_render_prompt_no_double_wrapping(self, protocol):
        """Verify render_prompt does not double-wrap sections when given raw values."""
        prompt = protocol.render_prompt(
            "tools", "en",
            history_text="prev conversation",
            loop_warning="avoid repeating",
            current_user_message="user question",
        )
        assert prompt.count("<conversation_history>") == 1, "conversation_history should appear exactly once"
        assert prompt.count("<loop_warning>") == 1, "loop_warning should appear exactly once"
        assert prompt.count("<current_user_message>") == 1, "current_user_message should appear exactly once"

    def test_format_assistant_tool_calls(self, protocol):
        tool_calls = [{
            "id": "call_123",
            "function": {"name": "Bash", "arguments": '{"command": "echo hello"}'}
        }]
        result = protocol.format_assistant_tool_calls(tool_calls)
        assert "<antml:function_calls>" in result
        assert '<antml:invoke name="Bash">' in result
        assert "<antml:parameters>" in result

    def test_clean_tags(self, protocol):
        content = "text<antml:function_calls><antml:invoke name=\"X\"></antml:invoke></antml:function_calls>more"
        cleaned = protocol.clean_tags(content)
        assert "<antml:function_calls>" not in cleaned
        assert "text" in cleaned
        assert "more" in cleaned

    def test_parse_single_call(self, protocol):
        xml = '<antml:function_calls><antml:invoke name="Bash"><antml:parameters>{"command": "echo hello"}</antml:parameters></antml:invoke></antml:function_calls>'
        clean, calls = protocol.parse(xml)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"
        assert "command" in calls[0]["function"]["arguments"]

    def test_parse_multiple_calls(self, protocol):
        xml = (
            '<antml:function_calls>'
            '<antml:invoke name="Bash"><antml:parameters>{"command": "ls"}</antml:parameters></antml:invoke>'
            '<antml:invoke name="Glob"><antml:parameters>{"pattern": "*.py"}</antml:parameters></antml:invoke>'
            '</antml:function_calls>'
        )
        clean, calls = protocol.parse(xml)
        assert len(calls) == 2
        assert calls[0]["function"]["name"] == "Bash"
        assert calls[1]["function"]["name"] == "Glob"

    def test_parse_empty_returns_empty(self, protocol):
        clean, calls = protocol.parse("no tool calls here")
        assert calls == []
        assert clean == "no tool calls here"

    def test_parse_with_parameter_tag(self, protocol):
        xml = '<antml:function_calls><antml:invoke name="Test"><antml:parameter name="x">hello</antml:parameter></antml:invoke></antml:function_calls>'
        clean, calls = protocol.parse(xml)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Test"
