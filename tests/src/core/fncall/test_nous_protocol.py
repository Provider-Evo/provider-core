"""Test NousProtocol (Nous Research format)."""

import json
import pytest

from src.core.fncall.protocols.nous import NousProtocol


class TestNousProtocol:
    @pytest.fixture
    def protocol(self):
        return NousProtocol()

    def test_id(self, protocol):
        assert protocol.id == "nous"

    def test_supports_streaming(self, protocol):
        assert protocol.supports_streaming() is True

    def test_trigger_tags(self, protocol):
        tags = protocol.get_trigger_tags()
        assert "<function=" in tags

    def test_detect_start(self, protocol):
        found, pos = protocol.detect_start("<function=Bash>")
        assert found is True
        assert pos == 0

    def test_detect_start_not_found(self, protocol):
        found, pos = protocol.detect_start("just some text")
        assert found is False

    def test_render_prompt_has_example(self, protocol):
        prompt = protocol.render_prompt("tools", "en")
        assert "<function=" in prompt
        assert "json" in prompt.lower() or '{"' in prompt

    def test_render_prompt_interpolates_tool_descs(self, protocol):
        tool_descs = 'Tool: Bash - Executes a shell command. Parameter: command (string) - The command to run.'
        prompt = protocol.render_prompt(tool_descs, "en")
        assert "Bash" in prompt, "rendered prompt should contain the tool name from tool_descs"
        assert "command" in prompt, "rendered prompt should contain the parameter name from tool_descs"
        assert "{tool_descs}" not in prompt, "rendered prompt must not contain the literal '{tool_descs}' placeholder"

    def test_format_assistant_tool_calls(self, protocol):
        tool_calls = [{
            "id": "call_123",
            "function": {"name": "Bash", "arguments": '{"command": "echo hello"}'}
        }]
        result = protocol.format_assistant_tool_calls(tool_calls)
        assert "<function=" in result
        assert "Bash" in result

    def test_format_tool_result(self, protocol):
        result = protocol.format_tool_result("output", tool_name="Bash", tool_call_id="call_123")
        assert "Bash" in result or "output" in result

    def test_clean_tags(self, protocol):
        content = 'text<function=Bash>{"command":"ls"}</function>more'
        cleaned = protocol.clean_tags(content)
        assert "<function=" not in cleaned
        assert "text" in cleaned
        assert "more" in cleaned

    def test_parse_single_call(self, protocol):
        xml = '<function=Bash>{"command": "echo hello"}</function>'
        clean, calls = protocol.parse(xml)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"

    def test_parse_multiple_calls(self, protocol):
        xml = '<function=Bash>{"cmd": "ls"}</function><function=Glob>{"pat": "*.py"}</function>'
        clean, calls = protocol.parse(xml)
        assert len(calls) == 2
        assert calls[0]["function"]["name"] == "Bash"
        assert calls[1]["function"]["name"] == "Glob"

    def test_parse_empty_returns_empty(self, protocol):
        clean, calls = protocol.parse("no tool calls here")
        assert calls == []
        assert clean == "no tool calls here"

    def test_parse_fragment(self, protocol):
        xml = '<function=Test>{"x": "1"}</function>'
        calls = protocol.parse_fragment(xml)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Test"