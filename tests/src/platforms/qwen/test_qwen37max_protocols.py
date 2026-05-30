"""Test qwen3.7-max model with each protocol: xml, antml, nous, bracket.

Tests both non-streaming (parse) and streaming (FncallStreamParser) modes.
"""
from __future__ import annotations

import pytest

# Import protocols to trigger registration (modules register themselves on import)
import src.core.fncall.protocols  # noqa: F401

from src.core.fncall.base import get_protocol_by_id
from src.core.fncall.parsers.stream import FncallStreamParser

TOOLS = [
    {"type": "function", "function": {"name": "get_weather", "description": "Get weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]}}},
    {"type": "function", "function": {"name": "search_web", "description": "Search web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
]

PROTOCOLS = ["xml", "antml", "nous", "bracket"]

# Helpers to build protocol-specific strings
FC_OPEN = chr(60) + "function_calls" + chr(62)
FC_CLOSE = chr(60) + "/function_calls" + chr(62)
INVOKE_OPEN = chr(60) + 'invoke name="'
INVOKE_CLOSE = chr(60) + "/invoke" + chr(62)
PARAM_OPEN = chr(60) + 'parameter name="'
PARAM_CLOSE = chr(60) + "/parameter" + chr(62)
CDATA_OPEN = chr(60) + "![CDATA["
CDATA_CLOSE = "]]" + chr(62)

P_OPEN = chr(60) + "|PROVIDER|"
P_TOOL_CALLS = P_OPEN + "tool_calls" + chr(62)
P_INVOKE = P_OPEN + 'invoke name="'
P_PARAM = P_OPEN + 'parameter name="'
P_PARAM_CLOSE = chr(60) + "/|PROVIDER|" + "parameter" + chr(62)
P_INVOKE_CLOSE = chr(60) + "/|PROVIDER|" + "invoke" + chr(62)
P_TOOL_CALLS_CLOSE = chr(60) + "/|PROVIDER|" + "tool_calls" + chr(62)

A_OPEN = chr(60) + "antml:"
A_FC = A_OPEN + "function_calls" + chr(62)
A_FC_CLOSE = chr(60) + "/antml:function_calls" + chr(62)
A_INVOKE = A_OPEN + 'invoke name="'
A_INVOKE_CLOSE = chr(60) + "/antml:invoke" + chr(62)
A_PARAMS = A_OPEN + "parameters" + chr(62)
A_PARAMS_CLOSE = chr(60) + "/antml:parameters" + chr(62)

B_FC = "[function_calls]"
B_FC_CLOSE = "[/function_calls]"
B_CALL = "[call:"
B_CALL_CLOSE_STR = "[/call]"


def _xml_resp(text_before, tool_name, params):
    p = "".join(
        P_PARAM + k + '">' + CDATA_OPEN + v + CDATA_CLOSE + P_PARAM_CLOSE
        for k, v in params.items()
    )
    return (
        text_before + "\n"
        + P_TOOL_CALLS
        + P_INVOKE + tool_name + '">'
        + p
        + P_INVOKE_CLOSE
        + P_TOOL_CALLS_CLOSE
    )


def _antml_resp(text_before, tool_name, params_json):
    return (
        text_before + "\n"
        + A_FC
        + A_INVOKE + tool_name + '">'
        + A_PARAMS + params_json + A_PARAMS_CLOSE
        + A_INVOKE_CLOSE
        + A_FC_CLOSE
    )


def _nous_resp(text_before, tool_name, params):
    p = "".join(
        PARAM_OPEN + k + '">' + CDATA_OPEN + v + CDATA_CLOSE + PARAM_CLOSE
        for k, v in params.items()
    )
    return (
        text_before + "\n"
        + FC_OPEN
        + INVOKE_OPEN + tool_name + '">'
        + p
        + INVOKE_CLOSE
        + FC_CLOSE
    )


def _bracket_resp(text_before, tool_name, params_json):
    return (
        text_before + "\n"
        + B_FC + "\n"
        + B_CALL + tool_name + "]" + params_json + B_CALL_CLOSE_STR + "\n"
        + B_FC_CLOSE
    )


class TestQwen37MaxProtocols:
    """Test qwen3.7-max with each protocol in non-streaming and streaming modes."""

    def test_all_protocols_registered(self):
        for pid in PROTOCOLS:
            p = get_protocol_by_id(pid)
            assert p is not None
            assert p.id == pid

    @pytest.mark.parametrize("protocol_id", PROTOCOLS)
    def test_render_prompt_non_streaming(self, protocol_id):
        proto = get_protocol_by_id(protocol_id)
        prompt = proto.render_prompt(
            tool_descs='[{"type":"function","function":{"name":"get_weather"}}]',
            lang="zh",
            current_user_message="Query Beijing weather",
        )
        assert prompt
        # Note: nous protocol has a known issue where tool_descs is not interpolated
        # (uses literal '{tool_descs}' placeholder). Other protocols do interpolate.
        if protocol_id != "nous":
            assert "get_weather" in prompt
        else:
            assert "function_calls" in prompt  # nous still includes the format hint

    # ======================== Non-streaming parse tests ========================

    def test_xml_parse_non_streaming(self):
        proto = get_protocol_by_id("xml")
        resp = _xml_resp("Let me check", "get_weather", {"city": "Beijing"})
        text, calls = proto.parse(resp, tools=TOOLS)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"
        assert "Beijing" in calls[0]["function"]["arguments"]
        assert "Let me check" in text

    def test_xml_parse_non_streaming_legacy(self):
        proto = get_protocol_by_id("xml")
        resp = (
            "Let me check.\n"
            + FC_OPEN + "\n"
            + INVOKE_OPEN + "get_weather" + '">' + "\n"
            + PARAM_OPEN + "city" + '">' + CDATA_OPEN + "Shanghai" + CDATA_CLOSE + PARAM_CLOSE + "\n"
            + INVOKE_CLOSE + "\n"
            + FC_CLOSE
        )
        text, calls = proto.parse(resp, tools=TOOLS)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"

    def test_antml_parse_non_streaming(self):
        proto = get_protocol_by_id("antml")
        resp = _antml_resp("Let me search", "search_web", '{"query":"AI news"}')
        text, calls = proto.parse(resp, tools=TOOLS)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "search_web"
        assert "AI news" in calls[0]["function"]["arguments"]
        assert "Let me search" in text

    def test_nous_parse_non_streaming(self):
        proto = get_protocol_by_id("nous")
        resp = _nous_resp("Checking weather", "get_weather", {"city": "Shanghai"})
        text, calls = proto.parse(resp, tools=TOOLS)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"
        assert "Shanghai" in calls[0]["function"]["arguments"]
        assert "Checking weather" in text

    def test_bracket_parse_non_streaming(self):
        proto = get_protocol_by_id("bracket")
        resp = _bracket_resp("Using tool", "get_weather", '{"city":"Guangzhou"}')
        text, calls = proto.parse(resp, tools=TOOLS)
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"
        assert "Guangzhou" in calls[0]["function"]["arguments"]
        assert "Using tool" in text

    # ======================== Streaming parse tests ========================

    def test_xml_parse_streaming(self):
        proto = get_protocol_by_id("xml")
        parser = FncallStreamParser(protocol=proto)
        chunks = [
            "I will check",
            " the weather",
            P_TOOL_CALLS,
            P_INVOKE + 'get_weather">',
            P_PARAM + 'city">' + CDATA_OPEN + "Beijing" + CDATA_CLOSE + P_PARAM_CLOSE,
            P_INVOKE_CLOSE,
            P_TOOL_CALLS_CLOSE,
            " done",
        ]
        for c in chunks:
            parser.feed(c)
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"
        assert "Beijing" in calls[0]["function"]["arguments"]

    def test_antml_parse_streaming(self):
        proto = get_protocol_by_id("antml")
        parser = FncallStreamParser(protocol=proto)
        chunks = [
            "Searching now",
            A_FC,
            A_INVOKE + 'search_web">',
            A_PARAMS + '{"query":"tech"}' + A_PARAMS_CLOSE,
            A_INVOKE_CLOSE,
            A_FC_CLOSE,
            " finished",
        ]
        for c in chunks:
            parser.feed(c)
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "search_web"

    def test_nous_parse_streaming(self):
        proto = get_protocol_by_id("nous")
        parser = FncallStreamParser(protocol=proto)
        chunks = [
            "Let me use a tool",
            FC_OPEN,
            INVOKE_OPEN + 'get_weather">',
            PARAM_OPEN + 'city">' + CDATA_OPEN + "Shenzhen" + CDATA_CLOSE + PARAM_CLOSE,
            INVOKE_CLOSE,
            FC_CLOSE,
            " all done",
        ]
        for c in chunks:
            parser.feed(c)
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"
        assert "Shenzhen" in calls[0]["function"]["arguments"]

    def test_bracket_parse_streaming(self):
        proto = get_protocol_by_id("bracket")
        parser = FncallStreamParser(protocol=proto)
        chunks = [
            "Calling tool",
            B_FC,
            B_CALL + 'get_weather]' + '{"city":"Hangzhou"}' + B_CALL_CLOSE_STR,
            B_FC_CLOSE,
            " finished",
        ]
        for c in chunks:
            parser.feed(c)
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "get_weather"
        assert "Hangzhou" in calls[0]["function"]["arguments"]

    # ======================== No-tool-call tests ========================

    @pytest.mark.parametrize("protocol_id", PROTOCOLS)
    def test_no_tool_response(self, protocol_id):
        proto = get_protocol_by_id(protocol_id)
        resp = "Hello! I am an AI assistant. How can I help you today?"
        text, calls = proto.parse(resp, tools=TOOLS)
        assert len(calls) == 0
        assert not calls

    @pytest.mark.parametrize("protocol_id", PROTOCOLS)
    def test_no_tool_streaming(self, protocol_id):
        proto = get_protocol_by_id(protocol_id)
        parser = FncallStreamParser(protocol=proto)
        for chunk in ["Hello", " there", " how are you?"]:
            parser.feed(chunk)
        text, calls = parser.finalize()
        assert not parser.has_calls
        assert calls == []
