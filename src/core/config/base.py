from __future__ import annotations

"""配置基类 - 提供自动 from_dict 反序列化"""

from dataclasses import MISSING, fields, is_dataclass
from typing import Any, TypeVar, Type, get_origin, get_args, Literal, Union, get_type_hints

T = TypeVar("T", bound="ConfigBase")

_type_hints_cache: dict[type, dict[str, Any]] = {}


class ConfigBase:
    """配置类的基类，提供 from_dict 自动反序列化。"""

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        if not isinstance(data, dict):
            raise TypeError(f"Expected a dict, got {type(data).__name__}")

        init_args: dict[str, Any] = {}
        type_hints = _get_type_hints(cls)

        for f in fields(cls):
            field_name = f.name
            field_type = type_hints.get(field_name, f.type)

            if field_name.startswith("_"):
                continue

            # 跳过 init=False 的字段（由 __post_init__ 处理）
            if not f.init:
                continue

            if field_name not in data:
                # 有默认值则使用；否则报错
                if f.default is not MISSING:
                    init_args[field_name] = f.default
                    continue
                if f.default_factory is not MISSING:
                    init_args[field_name] = f.default_factory()
                    continue
                raise ValueError(f"Missing required field: '{field_name}'")

            value = data[field_name]
            init_args[field_name] = cls._convert_field(value, field_type)

        return cls(**init_args)

    @classmethod
    def _convert_field(cls, value: Any, field_type: Any) -> Any:
        if isinstance(field_type, type) and is_dataclass(field_type):
            return field_type.from_dict(value)

        origin = get_origin(field_type)
        args = get_args(field_type)

        if origin in {list, set, tuple}:
            if not isinstance(value, list):
                raise TypeError(f"Expected list for {field_type}, got {type(value).__name__}")
            if origin is list:
                item_type = args[0] if args else Any
                return [cls._convert_field(item, item_type) for item in value]
            if origin is set:
                item_type = args[0] if args else Any
                return {cls._convert_field(item, item_type) for item in value}
            if origin is tuple:
                return tuple(cls._convert_field(item, arg) for item, arg in zip(value, args))

        if origin is dict:
            if not isinstance(value, dict):
                raise TypeError(f"Expected dict for {field_type}, got {type(value).__name__}")
            key_type, val_type = args if len(args) == 2 else (Any, Any)
            result = {}
            for k, v in value.items():
                ck = cls._convert_field(k, key_type)
                try:
                    cv = cls._convert_field(v, val_type)
                except (TypeError, ValueError):
                    cv = v
                result[ck] = cv
            return result

        if origin is Union:
            if value is None:
                return None
            real_type = next((a for a in args if a is not type(None)), Any)
            return cls._convert_field(value, real_type)

        if origin is Literal:
            allowed = get_args(field_type)
            if value not in allowed:
                raise TypeError(f"Value '{value}' not in allowed values {allowed}")
            return value

        if isinstance(field_type, type):
            if isinstance(value, field_type):
                return value
            try:
                return field_type(value)
            except (ValueError, TypeError) as e:
                raise TypeError(f"Cannot convert {type(value).__name__} to {field_type.__name__}") from e

        return value

    def __str__(self) -> str:
        field_strs = [f"{f.name}={getattr(self, f.name)!r}" for f in fields(self)]
        return f"{self.__class__.__name__}({', '.join(field_strs)})"


def _get_type_hints(cls: type) -> dict[str, Any]:
    if cls not in _type_hints_cache:
        try:
            _type_hints_cache[cls] = get_type_hints(cls)
        except Exception:
            _type_hints_cache[cls] = {}
    return _type_hints_cache[cls]
