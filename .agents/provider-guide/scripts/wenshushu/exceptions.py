# -*- coding: utf-8 -*-
"""异常体系模块。

定义 Serializable 协议与完整的异常继承层次:

    ModuleError
    ├── ValidationError
    ├── ConfigurationError
    ├── DomainError
    │   ├── BusinessRuleError
    │   ├── EntityNotFoundError
    │   └── StateTransitionError
    ├── InfrastructureError
    │   ├── PersistenceError
    │   └── ExternalServiceError
    └── ApplicationError
        └── UseCaseError
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# 序列化协议
# ---------------------------------------------------------------------------

@runtime_checkable
class Serializable(Protocol):
    """序列化协议,所有领域对象应实现此协议。

    >>> class Foo:
    ...     def to_dict(self) -> dict[str, Any]: return {"x": 1}
    ...     @classmethod
    ...     def from_dict(cls, data: dict[str, Any]) -> 'Foo': return cls()
    ...     def to_json(self, indent: int = 2) -> str: return '{}'
    ...     @classmethod
    ...     def from_json(cls, raw: str) -> 'Foo': return cls()
    >>> isinstance(Foo(), Serializable)
    True
    """

    def to_dict(self) -> dict[str, Any]:
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Any:
        ...

    def to_json(self, indent: int = 2) -> str:
        ...

    @classmethod
    def from_json(cls, raw: str) -> Any:
        ...


# ---------------------------------------------------------------------------
# 哨兵对象（ValidationError 需要）
# ---------------------------------------------------------------------------

_SENTINEL = object()


# ---------------------------------------------------------------------------
# 异常层次
# ---------------------------------------------------------------------------

class ModuleError(Exception):
    """模块基础异常,携带结构化上下文信息。

    Args:
        message: 中文错误消息。
        code: 错误代码标识。
        context: 额外上下文字典。

    >>> e = ModuleError("测试错误", code="E001", context={"key": "val"})
    >>> e.message
    '测试错误'
    >>> e.code
    'E001'
    """

    def __init__(
        self,
        message: str = "未知错误",
        *,
        code: str = "UNKNOWN",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.context: dict[str, Any] = context or {}
        super().__init__(message)

    def __str__(self) -> str:
        parts = [f"[{self.code}] {self.message}"]
        if self.context:
            parts.append(f" 上下文: {self.context}")
        return "".join(parts)


class ValidationError(ModuleError):
    """字段级校验错误。"""

    def __init__(
        self,
        message: str = "校验失败",
        *,
        field: str = "",
        value: Any = _SENTINEL,
        reason: str = "",
        code: str = "VALIDATION",
        context: dict[str, Any] | None = None,
    ) -> None:
        ctx = dict(context or {})
        ctx.update({"field": field, "reason": reason})
        if value is not _SENTINEL:
            ctx["value"] = value
        super().__init__(message, code=code, context=ctx)
        self.field = field
        self.value = value
        self.reason = reason


class ConfigurationError(ModuleError):
    """配置错误。"""

    def __init__(self, message: str = "配置错误", **kwargs: Any) -> None:
        super().__init__(message, code="CONFIG", **kwargs)


class DomainError(ModuleError):
    """领域层基础错误。"""

    def __init__(self, message: str = "领域错误", **kwargs: Any) -> None:
        kwargs.setdefault("code", "DOMAIN")
        super().__init__(message, **kwargs)


class BusinessRuleError(DomainError):
    """业务规则违反。"""

    def __init__(self, message: str = "业务规则违反", **kwargs: Any) -> None:
        kwargs.setdefault("code", "BIZ_RULE")
        super().__init__(message, **kwargs)


class EntityNotFoundError(DomainError):
    """实体未找到。"""

    def __init__(
        self,
        message: str = "实体未找到",
        *,
        entity_type: str = "",
        identifier: str = "",
        **kwargs: Any,
    ) -> None:
        ctx = kwargs.pop("context", None) or {}
        ctx.update({"entity_type": entity_type, "identifier": identifier})
        kwargs["context"] = ctx
        kwargs.setdefault("code", "NOT_FOUND")
        super().__init__(message, **kwargs)


class StateTransitionError(DomainError):
    """状态迁移非法。"""

    def __init__(self, message: str = "状态迁移非法", **kwargs: Any) -> None:
        kwargs.setdefault("code", "STATE_TRANS")
        super().__init__(message, **kwargs)


class InfrastructureError(ModuleError):
    """基础设施层错误。"""

    def __init__(self, message: str = "基础设施错误", **kwargs: Any) -> None:
        kwargs.setdefault("code", "INFRA")
        super().__init__(message, **kwargs)


class PersistenceError(InfrastructureError):
    """持久化错误。"""

    def __init__(self, message: str = "持久化错误", **kwargs: Any) -> None:
        kwargs.setdefault("code", "PERSIST")
        super().__init__(message, **kwargs)


class ExternalServiceError(InfrastructureError):
    """外部服务错误。"""

    def __init__(self, message: str = "外部服务错误", **kwargs: Any) -> None:
        kwargs.setdefault("code", "EXT_SVC")
        super().__init__(message, **kwargs)


class ApplicationError(ModuleError):
    """应用层错误。"""

    def __init__(self, message: str = "应用层错误", **kwargs: Any) -> None:
        kwargs.setdefault("code", "APP")
        super().__init__(message, **kwargs)


class UseCaseError(ApplicationError):
    """用例执行失败。"""

    def __init__(self, message: str = "用例执行失败", **kwargs: Any) -> None:
        kwargs.setdefault("code", "USE_CASE")
        super().__init__(message, **kwargs)
