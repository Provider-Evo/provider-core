"""Test NousProtocol (Nous Research XML format)."""

import json
import pytest

from src.core.fncall.protocols.nous import NousProtocol

_LT = chr(60)
_GT = chr(62)


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
        assert "<function_calls>" in tags

    def test_detect_start(self, protocol):
        found, pos = protocol.detect_start("<function_calls>")
        assert found is True
        assert pos == 0

    def test_detect_start_not_found(self, protocol):
        found, pos = protocol.detect_start("just some text")
        assert found is False

    def test_render_prompt_has_example(self, protocol):
        prompt = protocol.render_prompt("tools", "en")
        assert "<function_calls>" in prompt
        assert "<invoke" in prompt
        assert "<parameter" in prompt
        assert "<![CDATA[" in prompt

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
        assert "<function_calls>" in result
        assert '<invoke name="Bash">' in result
        assert "<parameter" in result
        assert "<![CDATA[" in result

    def test_format_tool_result(self, protocol):
        result = protocol.format_tool_result("output", tool_name="Bash", tool_call_id="call_123")
        assert "<function_results>" in result
        assert 'name="Bash"' in result
        assert "output" in result

    def test_clean_tags(self, protocol):
        content = "text<function_calls><invoke name=\"X\"></invoke></function_calls>more"
        cleaned = protocol.clean_tags(content)
        assert "<function_calls>" not in cleaned
        assert "text" in cleaned
        assert "more" in cleaned

    def _make_nous_xml(self, name, params):
        """Helper to build Nous XML."""
        param_parts = []
        for k, v in params.items():
            param_parts.append(
                f'{_LT}parameter name="{k}"{_GT}<![CDATA[{v}]]>{_LT}/parameter{_GT}'
            )
        params_str = "".join(param_parts)
        return (
            f"{_LT}function_calls{_GT}"
            f'{_LT}invoke name="{name}"{_GT}'
            f"{params_str}"
            f"{_LT}/invoke{_GT}"
            f"{_LT}/function_calls{_GT}"
        )

    def test_parse_single_call(self, protocol):
        xml = self._make_nous_xml("Bash", {"command": "echo hello"})
        clean, calls = protocol.parse(xml)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"

    def test_parse_multiple_calls(self, protocol):
        xml = (
            f"{_LT}function_calls{_GT}"
            f'{_LT}invoke name="Bash"{_GT}{_LT}parameter name="cmd"{_GT}<![CDATA[ls]]>{_LT}/parameter{_GT}{_LT}/invoke{_GT}'
            f'{_LT}invoke name="Glob"{_GT}{_LT}parameter name="pat"{_GT}<![CDATA[*.py]]>{_LT}/parameter{_GT}{_LT}/invoke{_GT}'
            f"{_LT}/function_calls{_GT}"
        )
        clean, calls = protocol.parse(xml)
        assert len(calls) == 2
        assert calls[0]["function"]["name"] == "Bash"
        assert calls[1]["function"]["name"] == "Glob"

    def test_parse_empty_returns_empty(self, protocol):
        clean, calls = protocol.parse("no tool calls here")
        assert calls == []
        assert clean == "no tool calls here"

    def test_parse_fragment(self, protocol):
        xml = self._make_nous_xml("Test", {"x": "1"})
        calls = protocol.parse_fragment(xml)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Test"
