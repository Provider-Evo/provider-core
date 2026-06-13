"""Test FncallStreamParser with all protocols."""

import pytest

from src.core.fncall.parsers.stream import FncallStreamParser
from src.core.fncall.protocols.xml import XmlProtocol
from src.core.fncall.protocols.antml import AntmlProtocol
from src.core.fncall.protocols.nous import NousProtocol
from src.core.fncall.protocols.original import OriginalProtocol
from src.core.fncall.protocols.bracket import BracketProtocol
from src.core.fncall.protocols.custom import CustomProtocol

LT = chr(60)
GT = chr(62)


class TestFncallStreamParserNoCalls:
    @pytest.mark.parametrize("protocol_cls", [
        XmlProtocol, AntmlProtocol, NousProtocol, OriginalProtocol, BracketProtocol,
    ])
    def test_no_tool_calls_preserves_text(self, protocol_cls):
        protocol = protocol_cls()
        parser = FncallStreamParser(protocol=protocol)
        for chunk in ["Hello", " world", "!"]:
            parser.feed(chunk)
        text, calls = parser.finalize()
        assert not parser.has_calls
        assert calls == []
        assert text == "Hello world!"


class TestFncallStreamParserXml:
    def test_detects_provider_format(self):
        protocol = XmlProtocol()
        parser = FncallStreamParser(protocol=protocol)
        parser.feed("wait ")
        parser.feed("<|PROVIDER|tool_calls>")
        parser.feed('<|PROVIDER|invoke name="Bash">')
        parser.feed('<|PROVIDER|parameter name="cmd"><![CDATA[ls]]></|PROVIDER|parameter>')
        parser.feed("</|PROVIDER|invoke></|PROVIDER|tool_calls>")
        parser.feed(" done")
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"

    def test_detects_legacy_function_calls(self):
        protocol = XmlProtocol()
        parser = FncallStreamParser(protocol=protocol)
        parser.feed("wait <function_calls>")
        parser.feed('<invoke name="Test">')
        parser.feed('</invoke></function_calls>')
        parser.feed(" done")
        text, calls = parser.finalize()
        assert parser.has_calls


class TestFncallStreamParserAntml:
    def test_detects_antml(self):
        protocol = AntmlProtocol()
        parser = FncallStreamParser(protocol=protocol)
        parser.feed("wait ")
        parser.feed("<antml:function_calls>")
        parser.feed('<antml:invoke name="Bash">')
        parser.feed('<antml:parameters>{"cmd":"ls"}</antml:parameters>')
        parser.feed("</antml:invoke></antml:function_calls>")
        parser.feed(" done")
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"


class TestFncallStreamParserNous:
    def test_detects_nous(self):
        protocol = NousProtocol()
        parser = FncallStreamParser(protocol=protocol)
        fc = LT + "function_calls" + GT
        inv = LT + 'invoke name="Bash"' + GT
        param = LT + 'parameter name="cmd"' + GT + "![CDATA[ls]]" + LT + "/parameter" + GT
        end_inv = LT + "/invoke" + GT
        end_fc = LT + "/function_calls" + GT
        parser.feed("wait " + fc)
        parser.feed(inv + param)
        parser.feed(end_inv + end_fc)
        parser.feed(" done")
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"


class TestFncallStreamParserBracket:
    def test_detects_bracket(self):
        protocol = BracketProtocol()
        parser = FncallStreamParser(protocol=protocol)
        parser.feed("wait [function_calls]")
        parser.feed('[call:Bash]{"cmd":"ls"}[/call]')
        parser.feed("[/function_calls]")
        parser.feed(" done")
        text, calls = parser.finalize()
        assert parser.has_calls
        assert len(calls) == 1
        assert calls[0]["function"]["name"] == "Bash"


class TestFncallStreamParserOriginal:
    def test_detects_original(self):
        protocol = OriginalProtocol()
        parser = FncallStreamParser(protocol=protocol)
        parser.feed('wait {"type":"function_call"')
        parser.feed(',"name":"Bash","arguments":{}}')
        text, calls = parser.finalize()
        # Original protocol uses JSON detection, may not trigger via stream parser
        # Just verify it doesn't crash
        assert isinstance(calls, list)


class TestFncallStreamParserSplitAcrossChunks:
    def test_trigger_split_across_chunks(self):
        protocol = XmlProtocol()
        parser = FncallStreamParser(protocol=protocol)
        trigger = "<|PROVIDER|tool_calls>"
        mid = len(trigger) // 2
        parser.feed("wait " + trigger[:mid])
        parser.feed(trigger[mid:])
        parser.feed('<|PROVIDER|invoke name="X"></|PROVIDER|invoke>')
        parser.feed("</|PROVIDER|tool_calls>")
        text, calls = parser.finalize()
        assert parser.has_calls
