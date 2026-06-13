"""Test OriginalProtocol (OpenAI native codexResponses JSON format)."""

import json
import pytest

from src.core.fncall.protocols.original import OriginalProtocol


class TestOriginalProtocol:
    @pytest.fixture
    def protocol(self):
        return OriginalProtocol()

    def test_id(self, protocol):
        assert protocol.id == "original"

    def test_supports_streaming(self, protocol):
        assert protocol.supports_streaming() is True

    def test_trigger_tags(self, protocol):
        tags = protocol.get_trigger_tags()
        assert '"type":"function_call"' in tags
        assert '"type": "function_call"' in tags

    def test_detect_start(self, protocol):
        found, pos = protocol.detect_start('{"type":"function_call"}')
        assert found is True

    def test_detect_start_with_space(self, protocol):
        found, pos = protocol.detect_start('{"type": "function_call"}')
        assert found is True

    def test_detect_start_not_found(self, protocol):
        found, pos = protocol.detect_start("just some text")
        assert found is False

    def test_render_prompt_passes_context(self, protocol):
        prompt = protocol.render_prompt("", "en", user_system_prompt="sys", current_user_message="hi")
        assert "sys" in prompt
        assert "hi" in prompt

    def test_render_prompt_interpolates_tool_descs(self, protocol):
        """Original protocol uses native JSON tool calls, so tool_descs is not injected.
        Verify no literal '{tool_descs}' placeholder appears in the output."""
        tool_descs = 'Tool: Bash - Executes a shell command.'
        prompt = protocol.render_prompt(tool_descs, "en", user_system_prompt="sys", current_user_message="hi")
        assert "{tool_descs}" not in prompt, "rendered prompt must not contain literal placeholder"
        # Original protocol intentionally does not inject tool_descs
        assert "sys" in prompt
        assert "hi" in prompt

    def test_render_prompt_renders_loop_warning(self, protocol):
        """Original protocol should include loop_warning when provided (safety mechanism)."""
        prompt = protocol.render_prompt(
            "", "en",
            loop_warning="avoid repeating the same tool call",
            current_user_message="hi",
        )
        assert "<loop_warning>" in prompt, "loop_warning section should be rendered"
        assert "avoid repeating" in prompt, "loop_warning content should appear"

    def test_render_prompt_omits_empty_loop_warning(self, protocol):
        """When loop_warning is empty, no section should appear."""
        prompt = protocol.render_prompt("", "en", current_user_message="hi")
        assert "<loop_warning>" not in prompt

    def test_format_assistant_tool_calls(self, protocol):
        tool_calls = [{
            "id": "call_123",
            "function": {"name": "Bash", "arguments": '{"command": "echo hello"}'}
        }]
        result = protocol.format_assistant_tool_calls(tool_calls)
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["type"] == "function_call"
        assert parsed[0]["name"] == "Bash"

    def test_format_tool_result_returns_content(self, protocol):
        result = protocol.format_tool_result("output")
        assert result == "output"

    def test_clean_tags(self, protocol):
        content = 'text {"type": "function_call", "name": "X", "arguments": {}} more'
        cleaned = protocol.clean_tags(content)
        assert "function_call" not in cleaned

    def test_parse_single_call(self, protocol):
        text = '{"type": "function_call", "name": "Bash", "arguments": {"command": "ls"}}'
        clean, calls = protocol.parse(text)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"

    def test_parse_multiple_calls_in_array(self, protocol):
        text = json.dumps([
            {"type": "function_call", "name": "Bash", "arguments": {"cmd": "a"}},
            {"type": "function_call", "name": "Glob", "arguments": {"pat": "b"}},
        ])
        clean, calls = protocol.parse(text)
        assert len(calls) == 2
        assert calls[0]["function"]["name"] == "Bash"
        assert calls[1]["function"]["name"] == "Glob"

    def test_parse_nested_in_output(self, protocol):
        text = json.dumps({
            "output": [
                {"type": "function_call", "name": "Test", "arguments": {}},
            ]
        })
        clean, calls = protocol.parse(text)
        assert len(calls) == 1

    def test_parse_empty_returns_empty(self, protocol):
        clean, calls = protocol.parse("no tool calls here")
        assert calls == []
