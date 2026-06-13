# tests/src/core/fncall/test_bracket_protocol.py
"""Test BracketProtocol with correct and fallback format parsing."""

import json

import pytest

from src.core.fncall.protocols.bracket import BracketProtocol


class TestBracketProtocol:
    """Test BracketProtocol basic operations."""

    @pytest.fixture
    def protocol(self):
        return BracketProtocol()

    def test_id(self, protocol):
        assert protocol.id == "bracket"

    def test_supports_streaming(self, protocol):
        assert protocol.supports_streaming() is True

    def test_trigger_tags(self, protocol):
        tags = protocol.get_trigger_tags()
        assert "[function_calls]" in tags

    def test_detect_start(self, protocol):
        found, pos = protocol.detect_start("some text [function_calls]")
        assert found is True
        assert pos == 10

    def test_render_prompt_has_format_rules(self, protocol):
        prompt = protocol.render_prompt("Tool: test", "en")
        assert "[function_calls]" in prompt
        assert "[call:exact_tool_name]" in prompt
        assert "Do NOT use [ToolName]" in prompt

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
        assert "[function_calls]" in result
        assert "[call:Bash]" in result
        assert "[/call]" in result

    def test_clean_tags(self, protocol):
        content = "text [function_calls][call:Bash]{\"cmd\":\"echo hi\"}[/call][/function_calls] more"
        cleaned = protocol.clean_tags(content)
        assert "[function_calls]" not in cleaned
        assert "text" in cleaned
        assert "more" in cleaned


class TestBracketParseCorrectFormat:
    """Test parsing correct [call:name]{args}[/call] format."""

    @pytest.fixture
    def protocol(self):
        return BracketProtocol()

    def test_parse_single_call(self, protocol):
        text = '[function_calls]\n[call:Bash]{"command": "echo hello"}[/call]\n[/function_calls]'
        tools = [{
            "type": "function",
            "function": {
                "name": "Bash",
                "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}
            }
        }]
        clean, tool_calls = protocol.parse(text, tools)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "Bash"
        assert "command" in tool_calls[0]["function"]["arguments"]
        assert clean.strip() == ""

    def test_parse_multiple_calls(self, protocol):
        text = """[function_calls]
[call:Bash]{"command": "echo hello"}[/call]
[call:ReadFile]{"path": "/tmp/test.txt"}[/call]
[/function_calls]"""
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 2
        assert tool_calls[0]["function"]["name"] == "Bash"
        assert tool_calls[1]["function"]["name"] == "ReadFile"


class TestBracketParseFallbackFormat:
    """Test parsing simplified [ToolName]{args}[/ToolName] fallback format."""

    @pytest.fixture
    def protocol(self):
        return BracketProtocol()

    def test_parse_simple_call(self, protocol):
        text = '[function_calls]\n[Bash]{"command": "echo hello"}[/Bash]\n[/function_calls]'
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "Bash"
        assert "command" in tool_calls[0]["function"]["arguments"]

    def test_parse_simple_call_non_json_args(self, protocol):
        """Fallback requires JSON-like content (starts with {)."""
        text = '[function_calls]\n[Bash]{"value": "echo hello"}[/Bash]\n[/function_calls]'
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "Bash"
        args = json.loads(tool_calls[0]["function"]["arguments"])
        assert "value" in args
        assert args["value"] == "echo hello"

    def test_parse_skips_function_calls_tag(self, protocol):
        """Ensure [function_calls] tag itself is not parsed as a tool call."""
        text = '[function_calls]\n[call:Bash]{"cmd":"echo"}[/call]\n[/function_calls]'
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "Bash"
        # Should NOT have a call named "function_calls"

    def test_parse_prefers_correct_format(self, protocol):
        """If both formats appear, prefer correct [call:name] format."""
        text = """[function_calls]
[call:Bash]{"command": "correct"}[/call]
[/function_calls]"""
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "Bash"
        assert "command" in tool_calls[0]["function"]["arguments"]

    def test_parse_multiple_blocks_mixed_formats(self, protocol):
        """Per-block fallback: block 1 uses correct format, block 2 uses simplified."""
        text = """[function_calls]
[call:Bash]{"command": "correct"}[/call]
[/function_calls]
[function_calls]
[ReadFile]{"path": "/tmp/test.txt"}[/ReadFile]
[/function_calls]"""
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 2
        assert tool_calls[0]["function"]["name"] == "Bash"
        assert tool_calls[1]["function"]["name"] == "ReadFile"

    def test_parse_empty_block(self, protocol):
        """Empty [function_calls] block should produce no calls."""
        text = '[function_calls][/function_calls]'
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 0

    def test_parse_malformed_no_closing_tag(self, protocol):
        """Malformed block without closing tag should produce no calls."""
        text = '[function_calls][call:Bash]{}'
        clean, tool_calls = protocol.parse(text)
        assert len(tool_calls) == 0

    def test_parse_fallback_requires_json_brace(self, protocol):
        """Fallback regex only matches when body starts with {."""
        text = '[function_calls]\n[Bash]echo hello[/Bash]\n[/function_calls]'
        clean, tool_calls = protocol.parse(text)
        # Should NOT match because "echo hello" doesn't start with {
        assert len(tool_calls) == 0

    def test_parse_skips_call_tag_in_fallback(self, protocol):
        """Fallback should not parse [call]{...}[/call] as a tool call."""
        text = '[function_calls]\n[call]{"something":"x"}[/call]\n[/function_calls]'
        clean, tool_calls = protocol.parse(text)
        # Should NOT match because 'call' is in the skip list
        assert len(tool_calls) == 0
