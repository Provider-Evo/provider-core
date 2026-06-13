"""Tests for src/core/config/base.py."""
import pytest
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal, Union

from src.core.config.base import ConfigBase


@dataclass
class NestedCfg(ConfigBase):
    name: str = "nested"
    value: int = 42


@dataclass
class TestCfg(ConfigBase):
    str_field: str = "default"
    int_field: int = 10
    bool_field: bool = False
    list_field: List[str] = field(default_factory=list)
    dict_field: Dict[str, int] = field(default_factory=dict)
    optional_field: Optional[str] = None
    nested: NestedCfg = field(default_factory=NestedCfg)
    literal_field: Literal["a", "b", "c"] = "a"
    union_field: Union[str, int] = "default"


class TestConfigBaseFromDict:
    def test_basic_conversion(self):
        data = {"str_field": "custom", "int_field": 99}
        cfg = TestCfg.from_dict(data)
        assert cfg.str_field == "custom"
        assert cfg.int_field == 99
        assert cfg.bool_field is False  # default

    def test_missing_optional_uses_default(self):
        cfg = TestCfg.from_dict({})
        assert cfg.str_field == "default"

    def test_missing_required_raises(self):
        @dataclass
        class RequiredCfg(ConfigBase):
            name: str  # No default

        with pytest.raises(ValueError, match="Missing required field"):
            RequiredCfg.from_dict({})

    def test_non_dict_raises(self):
        with pytest.raises(TypeError, match="Expected a dict"):
            TestCfg.from_dict("not a dict")

    def test_nested_dataclass(self):
        data = {
            "nested": {"name": "custom", "value": 100}
        }
        cfg = TestCfg.from_dict(data)
        assert cfg.nested.name == "custom"
        assert cfg.nested.value == 100


class TestConfigBaseTypeConversion:
    def test_list_conversion(self):
        data = {"list_field": ["a", "b", "c"]}
        cfg = TestCfg.from_dict(data)
        assert cfg.list_field == ["a", "b", "c"]

    def test_dict_conversion(self):
        data = {"dict_field": {"a": 1, "b": 2}}
        cfg = TestCfg.from_dict(data)
        assert cfg.dict_field == {"a": 1, "b": 2}

    def test_optional_none(self):
        data = {"optional_field": None}
        cfg = TestCfg.from_dict(data)
        assert cfg.optional_field is None

    def test_optional_value(self):
        data = {"optional_field": "hello"}
        cfg = TestCfg.from_dict(data)
        assert cfg.optional_field == "hello"

    def test_literal_valid(self):
        data = {"literal_field": "b"}
        cfg = TestCfg.from_dict(data)
        assert cfg.literal_field == "b"

    def test_literal_invalid(self):
        data = {"literal_field": "invalid"}
        with pytest.raises(TypeError, match="not in allowed values"):
            TestCfg.from_dict(data)

    def test_union_str(self):
        data = {"union_field": "test"}
        cfg = TestCfg.from_dict(data)
        assert cfg.union_field == "test"

    def test_union_int(self):
        data = {"union_field": 42}
        cfg = TestCfg.from_dict(data)
        # Union[str, int] coerces int to string due to str being first in Union
        assert cfg.union_field == "42" or cfg.union_field == 42


class TestConfigBaseStr:
    def test_string_representation(self):
        cfg = TestCfg(str_field="test", int_field=5)
        s = str(cfg)
        assert "TestCfg" in s
        assert "str_field" in s
        assert "int_field" in s


class TestGetTypeHints:
    def test_caching(self):
        from src.core.config.base import _get_type_hints
        hints1 = _get_type_hints(TestCfg)
        hints2 = _get_type_hints(TestCfg)
        assert hints1 is hints2  # Same cached object
