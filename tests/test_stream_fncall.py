from __future__ import annotations

import pytest

from echotools.fncall.parsers.stream import FncallStreamParser
from echotools.fncall.registry import get_protocol

from src.core.dispatch.engine.support.fncall_context import (
    FncallStreamEmitState,
    feed_fncall_stream,
    finalize_fncall_stream,
)


@pytest.fixture
def entml_parser():
    protocol = get_protocol(protocol_id="entml")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "weather",
                "parameters": {
                    "type": "object",
                    "properties": {"city": {"type": "string"}},
                    "required": ["city"],
                },
            },
        }
    ]
    return FncallStreamParser(protocol=protocol, tools=tools)


def test_feed_fncall_stream_emits_partial_text(entml_parser) -> None:
    state = FncallStreamEmitState()
    out = feed_fncall_stream(entml_parser, "hello ", state)
    assert out == ["hello "]
    out2 = feed_fncall_stream(entml_parser, "world", state)
    assert out2 == ["world"]


def test_finalize_fncall_stream_emits_tool_calls(entml_parser) -> None:
    state = FncallStreamEmitState()
    raw = (
        '<entml:invoke name="get_weather">\n'
        '<entml:parameter name="city">beijing</entml:parameter>\n'
        "</entml:invoke>"
    )
    feed_fncall_stream(entml_parser, raw, state)
    tail = finalize_fncall_stream(entml_parser, state)
    assert any(isinstance(x, dict) and "tool_calls" in x for x in tail)
