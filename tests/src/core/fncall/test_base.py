"""Tests for src/core/fncall/base.py."""
import pytest

from src.core.fncall.base import (
    ToolProtocol,
    register_protocol,
    get_protocol_by_id,
    list_protocols,
    VALID_PROTOCOL_IDS,
)
from echotools.protocol.base import _PROTOCOL_REGISTRY


class TestValidProtocolIds:
    def test_contains_all_expected(self):
        assert "xml" in VALID_PROTOCOL_IDS
        assert "original" in VALID_PROTOCOL_IDS
        assert "antml" in VALID_PROTOCOL_IDS
        assert "bracket" in VALID_PROTOCOL_IDS
        assert "custom" in VALID_PROTOCOL_IDS
        assert "nous" in VALID_PROTOCOL_IDS

    def test_is_tuple(self):
        assert isinstance(VALID_PROTOCOL_IDS, tuple)


class TestToolProtocolAbstract:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            ToolProtocol()

    def test_missing_render_prompt_raises(self):
        class IncompleteProtocol(ToolProtocol):
            @property
            def id(self):
                return "test"
            # Missing render_prompt, parse, parse_fragment

        with pytest.raises(TypeError):
            IncompleteProtocol()


class TestConcreteProtocol:
    def test_implement_all_methods(self):
        class TestProtocol(ToolProtocol):
            @property
            def id(self):
                return "test"

            def render_prompt(self, tool_descs, lang, **kwargs):
                return f"Prompt: {tool_descs}"

            def parse(self, text, tools=None):
                return text, []

            def parse_fragment(self, fragment, tools=None):
                return []

        proto = TestProtocol()
        assert proto.id == "test"
        assert proto.render_prompt("tools", "en") == "Prompt: tools"
        assert proto.parse("text") == ("text", [])
        assert proto.parse_fragment("<tool/>") == []
        assert proto.supports_streaming() is True

    def test_detect_start_default(self):
        class TestProtocol(ToolProtocol):
            @property
            def id(self):
                return "test"

            def render_prompt(self, tool_descs, lang, **kwargs):
                return ""

            def parse(self, text, tools=None):
                return text, []

            def parse_fragment(self, fragment, tools=None):
                return []

        proto = TestProtocol()
        found, pos = proto.detect_start("some text")
        assert found is False
        assert pos == -1

    def test_clean_tags_default(self):
        class TestProtocol(ToolProtocol):
            @property
            def id(self):
                return "test"

            def render_prompt(self, tool_descs, lang, **kwargs):
                return ""

            def parse(self, text, tools=None):
                return text, []

            def parse_fragment(self, fragment, tools=None):
                return []

        proto = TestProtocol()
        assert proto.clean_tags("  text  ") == "text"

    def test_format_assistant_tool_calls_default(self):
        class TestProtocol(ToolProtocol):
            @property
            def id(self):
                return "test"

            def render_prompt(self, tool_descs, lang, **kwargs):
                return ""

            def parse(self, text, tools=None):
                return text, []

            def parse_fragment(self, fragment, tools=None):
                return []

        proto = TestProtocol()
        assert proto.format_assistant_tool_calls([]) == ""

    def test_format_tool_result_default(self):
        class TestProtocol(ToolProtocol):
            @property
            def id(self):
                return "test"

            def render_prompt(self, tool_descs, lang, **kwargs):
                return ""

            def parse(self, text, tools=None):
                return text, []

            def parse_fragment(self, fragment, tools=None):
                return []

        proto = TestProtocol()
        assert proto.format_tool_result("result", "tool") == ""


class TestProtocolRegistry:
    _saved_registry: dict = None
    _saved_registered: bool = None

    def setup_method(self):
        # Save and clear registry before each test
        import src.core.fncall.registry as fncall_registry
        self._saved_registry = dict(_PROTOCOL_REGISTRY)
        self._saved_registered = fncall_registry._registered
        _PROTOCOL_REGISTRY.clear()
        fncall_registry._registered = False

    def teardown_method(self):
        # Restore registry after each test
        import src.core.fncall.registry as fncall_registry
        _PROTOCOL_REGISTRY.clear()
        _PROTOCOL_REGISTRY.update(self._saved_registry)
        fncall_registry._registered = self._saved_registered

    def test_register_and_get(self):
        class TestProto(ToolProtocol):
            @property
            def id(self):
                return "testproto"

            def render_prompt(self, tool_descs, lang, **kwargs):
                return ""

            def parse(self, text, tools=None):
                return text, []

            def parse_fragment(self, fragment, tools=None):
                return []

        proto = TestProto()
        register_protocol(proto)
        assert get_protocol_by_id("testproto") is proto

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError, match="未知的 fncall 协议"):
            get_protocol_by_id("nonexistent")

    def test_list_protocols(self):
        class P1(ToolProtocol):
            @property
            def id(self): return "p1"
            def render_prompt(self, **k): return ""
            def parse(self, text, tools=None): return text, []
            def parse_fragment(self, fragment, tools=None): return []

        class P2(ToolProtocol):
            @property
            def id(self): return "p2"
            def render_prompt(self, **k): return ""
            def parse(self, text, tools=None): return text, []
            def parse_fragment(self, fragment, tools=None): return []

        register_protocol(P1())
        register_protocol(P2())

        protocols = list_protocols()
        assert "p1" in protocols
        assert "p2" in protocols
        assert protocols == sorted(protocols)

    def test_duplicate_registration_overwrites(self):
        class TestProto(ToolProtocol):
            @property
            def id(self):
                return "dup"

            def render_prompt(self, tool_descs, lang, **kwargs):
                return ""

            def parse(self, text, tools=None):
                return text, []

            def parse_fragment(self, fragment, tools=None):
                return []

        proto1 = TestProto()
        proto2 = TestProto()

        register_protocol(proto1)
        register_protocol(proto2)

        # Second registration should overwrite
        assert get_protocol_by_id("dup") is proto2
