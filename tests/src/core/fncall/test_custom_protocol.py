"""Test CustomProtocol."""

import pytest

from src.core.fncall.protocols.custom import CustomProtocol


class TestCustomProtocol:
    @pytest.fixture
    def protocol(self):
        return CustomProtocol(prompt_en="Use tool: {tool_descs}", prompt_zh="使用工具: {tool_descs}")

    def test_id(self, protocol):
        assert protocol.id == "custom"

    def test_supports_streaming(self, protocol):
        assert protocol.supports_streaming() is False

    def test_trigger_tags_empty(self, protocol):
        tags = protocol.get_trigger_tags()
        assert tags == []

    def test_detect_start_always_false(self, protocol):
        found, pos = protocol.detect_start("<anything>")
        assert found is False

    def test_render_prompt_en(self, protocol):
        prompt = protocol.render_prompt("my tools", "en")
        assert "Use tool: my tools" in prompt

    def test_render_prompt_zh(self, protocol):
        prompt = protocol.render_prompt("我的工具", "zh")
        assert "使用工具: 我的工具" in prompt

    def test_render_prompt_interpolates_tool_descs(self, protocol):
        tool_descs = 'Tool: Bash - Executes a shell command. Parameter: command (string) - The command to run.'
        prompt = protocol.render_prompt(tool_descs, "en")
        assert "Bash" in prompt, "rendered prompt should contain the tool name from tool_descs"
        assert "{tool_descs}" not in prompt, "rendered prompt must not contain the literal '{tool_descs}' placeholder"

    def test_render_prompt_empty(self, protocol):
        proto = CustomProtocol()
        assert proto.render_prompt("", "en") == ""

    def test_parse_returns_text_empty(self, protocol):
        clean, calls = protocol.parse("anything here")
        assert clean == "anything here"
        assert calls == []

    def test_clean_tags_returns_stripped(self, protocol):
        result = protocol.clean_tags("  text  ")
        assert result == "text"

    def test_parse_fragment_returns_empty(self, protocol):
        assert protocol.parse_fragment("any fragment") == []
