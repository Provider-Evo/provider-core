# tests/src/core/fncall/test_xml_protocol.py
"""Test XmlProtocol with <|PROVIDER| namespace."""

import pytest

from src.core.fncall.protocols.xml import XmlProtocol
from src.core.fncall.parsers.xml_parser import parse_fncall_provider


class TestXmlProtocol:
    """Test XmlProtocol basic operations."""

    @pytest.fixture
    def protocol(self):
        return XmlProtocol()

    def test_id(self, protocol):
        assert protocol.id == "xml"

    def test_supports_streaming(self, protocol):
        assert protocol.supports_streaming() is True

    def test_trigger_tags(self, protocol):
        tags = protocol.get_trigger_tags()
        assert "<|PROVIDER|tool_calls>" in tags
        assert "<tool_calls>" in tags
        assert "<function_calls>" in tags

    def test_detect_start_provider(self, protocol):
        found, pos = protocol.detect_start("<|PROVIDER|tool_calls>")
        assert found is True
        assert pos == 0

    def test_detect_start_legacy(self, protocol):
        found, pos = protocol.detect_start("<function_calls>")
        assert found is True
        assert pos == 0

    def test_render_prompt_has_provider_format(self, protocol):
        prompt = protocol.render_prompt("Tool: test", "en")
        assert "<|PROVIDER|tool_calls>" in prompt
        assert "<|PROVIDER|invoke" in prompt
        assert "<|PROVIDER|parameter" in prompt
        assert "<![CDATA[" in prompt

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
        # Each section tag should appear at most once (protocols wrap internally)
        assert prompt.count("<conversation_history>") == 1, "conversation_history should appear exactly once"
        assert prompt.count("<loop_warning>") == 1, "loop_warning should appear exactly once"
        assert prompt.count("<current_user_message>") == 1, "current_user_message should appear exactly once"

    def test_format_assistant_tool_calls(self, protocol):
        tool_calls = [{
            "id": "call_123",
            "function": {"name": "Bash", "arguments": '{"command": "echo hello"}'}
        }]
        result = protocol.format_assistant_tool_calls(tool_calls)
        assert "<|PROVIDER|tool_calls>" in result
        assert '<|PROVIDER|invoke name="Bash">' in result
        assert '<|PROVIDER|parameter name="command">' in result
        assert "<![CDATA[echo hello]]>" in result

    def test_format_tool_result(self, protocol):
        result = protocol.format_tool_result("output", tool_call_id="call_123")
        assert '<|PROVIDER|tool_result tool_call_id="call_123">' in result
        assert "<![CDATA[output]]>" in result

    def test_clean_tags_removes_provider_block(self, protocol):
        content = "text<|PROVIDER|tool_calls><|PROVIDER|invoke name=\"X\"></|PROVIDER|invoke></|PROVIDER|tool_calls>more"
        cleaned = protocol.clean_tags(content)
        assert "<|PROVIDER|tool_calls>" not in cleaned
        assert "text" in cleaned
        assert "more" in cleaned


class TestParseFncallProvider:
    """Test parse_fncall_provider function."""

    def test_parse_single_call(self):
        xml = '<|PROVIDER|tool_calls><|PROVIDER|invoke name="Bash"><|PROVIDER|parameter name="command"><![CDATA[echo hello]]></|PROVIDER|parameter></|PROVIDER|invoke></|PROVIDER|tool_calls>'
        result = parse_fncall_provider(xml)
        assert len(result) == 1
        assert result[0]["function"]["name"] == "Bash"
        assert "command" in result[0]["function"]["arguments"]

    def test_parse_cdata_value(self):
        xml = '<|PROVIDER|tool_calls><|PROVIDER|invoke name="Test"><|PROVIDER|parameter name="x"><![CDATA[hello world]]></|PROVIDER|parameter></|PROVIDER|invoke></|PROVIDER|tool_calls>'
        result = parse_fncall_provider(xml)
        assert result[0]["function"]["arguments"] == '{"x": "hello world"}'

    def test_parse_empty_returns_empty(self):
        result = parse_fncall_provider("no tool calls here")
        assert result == []
