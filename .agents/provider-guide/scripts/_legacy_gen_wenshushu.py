# filename: use_wenshushu.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
文叔叔(wenshushu.cn)文件传输工具

功能: 匿名登录、文件上传(含秒传/分块)、文件下载、加密签名。

用法:
    python use_wenshushu.py upload "file.exe"
    python use_wenshushu.py download "https://www.wenshushu.cn/f/xxx"
    python use_wenshushu.py --test
    python use_wenshushu.py --demo
    python use_wenshushu.py --version
"""

# ═══════════════════════════════════════════════════════════════
# 区域 02: __future__ 与标准库导入
# ═══════════════════════════════════════════════════════════════
from __future__ import annotations

import abc
import argparse
import base64
import concurrent.futures
import contextlib
import copy
import dataclasses
import enum
import functools
import hashlib
import inspect
import io
import json
import logging
import os
import re
import sys
import textwrap
import threading
import time
import traceback
import uuid
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    ClassVar,
    Generic,
    Iterator,
    Protocol,
    TypeVar,
    runtime_checkable,
)

# ═══════════════════════════════════════════════════════════════
# 区域 03: 第三方可选导入与降级代理
# ═══════════════════════════════════════════════════════════════

def _optional_import(module: str, pip_name: str = "") -> Any:
    """尝试导入模块,缺失时返回代理对象,访问任何属性抛出含 pip install 指引的 ImportError。

    Args:
        module: 模块导入路径。
        pip_name: pip 包名,为空时使用 module 的顶层名称。

    Returns:
        导入的模块或代理对象。

    >>> proxy = _optional_import("nonexistent_module_xyz", "nonexistent-pkg")
    >>> try:
    ...     proxy.something
    ... except ImportError as e:
    ...     "pip install" in str(e)
    True
    """
    try:
        import importlib
        return importlib.import_module(module)
    except ImportError:
        _pip = pip_name or module.split(".")[0]

        class _Proxy:
            def __getattr__(self, name: str) -> Any:
                raise ImportError(
                    f"模块 '{module}' 未安装。请执行: pip install {_pip}"
                )
        return _Proxy()


_requests_mod = _optional_import("requests", "requests")
_base58_mod = _optional_import("base58", "base58")
_des_mod = _optional_import("Cryptodome.Cipher.DES", "pycryptodomex")
_padding_mod = _optional_import("Cryptodome.Util.Padding", "pycryptodomex")

try:
    import requests as _requests  # type: ignore[import-untyped]
    import base58 as _base58  # type: ignore[import-untyped]
    from Cryptodome.Cipher import DES as _DES  # type: ignore[import-untyped]
    from Cryptodome.Util import Padding as _Padding  # type: ignore[import-untyped]
    _HAS_CRYPTO_DEPS = True
except ImportError:
    _requests = _requests_mod  # type: ignore[assignment]
    _base58 = _base58_mod  # type: ignore[assignment]
    _DES = _des_mod  # type: ignore[assignment]
    _Padding = _padding_mod  # type: ignore[assignment]
    _HAS_CRYPTO_DEPS = False

# ═══════════════════════════════════════════════════════════════
# 区域 04: 模块元信息
# ═══════════════════════════════════════════════════════════════

__all__: list[str] = [
    # 异常
    "ModuleError", "ValidationError", "ConfigurationError",
    "DomainError", "BusinessRuleError", "EntityNotFoundError",
    "StateTransitionError", "InfrastructureError", "PersistenceError",
    "ExternalServiceError", "ApplicationError", "UseCaseError",
    # 基础设施
    "Result", "Ok", "Err", "Option", "Some", "Nothing",
    "Pipeline", "Builder", "Query", "EventBus", "Registry", "StateMachine",
    "Container",
    # 装饰器
    "validate_args", "retry", "timed", "cached", "singleton",
    "deprecated", "immutable", "contract", "trace_calls",
    "guard_none", "safe_execute", "coerce_types",
    # 配置/日志
    "Config", "setup_logging",
    # 领域
    "Serializable", "Specification",
    # 文叔叔核心
    "WenShuShuClient",
    # 入口
    "main",
]

__version__ = "1.0.0"
__author__ = "LLM Generated"

# ═══════════════════════════════════════════════════════════════
# 区域 05: 类型系统
# ═══════════════════════════════════════════════════════════════

T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
TEntity = TypeVar("TEntity")
Self = TypeVar("Self")

HandlerFunc = Callable[..., Any]
PredicateFunc = Callable[[Any], bool]
KeyFunc = Callable[[Any], Any]


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


# ═══════════════════════════════════════════════════════════════
# 区域 06: 常量 / 配置 / 哨兵 / 正则
# ═══════════════════════════════════════════════════════════════

_SENTINEL = object()

# 文叔叔相关常量
WSS_BASE_URL = "https://www.wenshushu.cn"
WSS_CHUNK_SIZE = 2097152  # 2 MiB
WSS_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) "
    "Gecko/20100101 Firefox/82.0"
)
WSS_DEFAULT_ACCEPT_LANG = "en-US, en;q=0.9"

# 默认重试参数
DEFAULT_MAX_RETRY = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0

# 缓存默认参数
DEFAULT_CACHE_MAXSIZE = 128
DEFAULT_CACHE_TTL = 300

# 上传线程池大小
UPLOAD_MAX_WORKERS = 4

# 日志格式
DEFAULT_LOG_FMT = "%(asctime)s|%(levelname)-8s|%(name)s:%(lineno)d| %(message)s"

# 退出码
EXIT_SUCCESS = 0
EXIT_TEST_FAIL = 1
EXIT_CONFIG_ERROR = 2
EXIT_BUSINESS_ERROR = 3
EXIT_UNKNOWN_ERROR = 4


# ═══════════════════════════════════════════════════════════════
# 区域 07: 异常体系
# ═══════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════
# 区域 08: 日志与调试工具
# ═══════════════════════════════════════════════════════════════

_logger = logging.getLogger("use_wenshushu")


def setup_logging(
    level: int = logging.INFO,
    *,
    log_file: str | None = None,
    fmt: str = DEFAULT_LOG_FMT,
) -> None:
    """初始化日志系统。

    Args:
        level: 日志级别。
        log_file: 日志文件路径,为 None 时仅输出到控制台。
        fmt: 日志格式字符串。

    >>> setup_logging(logging.DEBUG)
    >>> _logger.level <= logging.DEBUG or _logger.parent.level <= logging.DEBUG
    True
    """
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(fmt)
    # 移除已有处理器避免重复
    for h in root.handlers[:]:
        root.removeHandler(h)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)


# ═══════════════════════════════════════════════════════════════
# 区域 09: 通用工具函数
# ═══════════════════════════════════════════════════════════════

def sha1_of_string(s: str) -> str:
    """计算字符串的 SHA1 十六进制摘要。

    Args:
        s: 输入字符串。

    Returns:
        SHA1 十六进制字符串。

    >>> sha1_of_string("hello")
    'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d'
    """
    return hashlib.sha1(s.encode()).hexdigest()


def md5_of_bytes(data: bytes) -> str:
    """计算字节数据的 MD5 十六进制摘要。

    Args:
        data: 输入字节。

    Returns:
        MD5 十六进制字符串。

    >>> md5_of_bytes(b"hello")
    '5d41402abc4b2a76b9719d911017c592'
    """
    return hashlib.md5(data).hexdigest()


def sha1_of_bytes(data: bytes) -> str:
    """计算字节数据的 SHA1 十六进制摘要。

    Args:
        data: 输入字节。

    Returns:
        SHA1 十六进制字符串。

    >>> sha1_of_bytes(b"hello")
    'aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d'
    """
    return hashlib.sha1(data).hexdigest()


def format_file_size(size_bytes: int) -> str:
    """将字节数格式化为人类可读的文件大小。

    Args:
        size_bytes: 文件字节大小。

    Returns:
        格式化后的字符串。

    >>> format_file_size(1048576)
    '1.0 MiB'
    >>> format_file_size(500)
    '500 B'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KiB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / 1024 ** 2:.1f} MiB"
    else:
        return f"{size_bytes / 1024 ** 3:.2f} GiB"


def format_duration(seconds: float) -> str:
    """将秒数格式化为 天时分秒 表示。

    Args:
        seconds: 总秒数。

    Returns:
        格式化后的字符串。

    >>> format_duration(90061)
    '1天1时1分1秒'
    """
    total = int(seconds)
    days, remainder = divmod(total, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{days}天{hours}时{minutes}分{secs}秒"


def generate_id() -> str:
    """生成 UUID4 标识符。

    Returns:
        UUID 字符串。

    >>> len(generate_id()) == 36
    True
    """
    return str(uuid.uuid4())


@contextlib.contextmanager
def managed_resource(factory: Callable[[], T], cleanup: Callable[[T], None] | None = None) -> Iterator[T]:
    """通用资源上下文管理器。

    Args:
        factory: 创建资源的工厂函数。
        cleanup: 可选的清理函数,为 None 时尝试调用 close()。

    Yields:
        创建的资源对象。

    >>> with managed_resource(lambda: [1,2,3]) as r:
    ...     len(r)
    3
    """
    resource = factory()
    try:
        yield resource
    finally:
        if cleanup:
            cleanup(resource)
        elif hasattr(resource, "close"):
            resource.close()


# ═══════════════════════════════════════════════════════════════
# 区域 10: 通用装饰器
# ═══════════════════════════════════════════════════════════════

def validate_args(**validators: Callable[[Any], bool]) -> Callable:
    """声明式参数校验装饰器。

    Args:
        **validators: 参数名到校验函数的映射。校验函数返回 False 时抛出 ValidationError。

    Returns:
        装饰器函数。

    >>> @validate_args(x=lambda v: v > 0)
    ... def add(x: int) -> int:
    ...     return x + 1
    >>> add(5)
    6
    >>> try:
    ...     add(-1)
    ... except ValidationError:
    ...     True
    True
    """
    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            for param_name, validator_fn in validators.items():
                if param_name in bound.arguments:
                    val = bound.arguments[param_name]
                    if not validator_fn(val):
                        raise ValidationError(
                            f"参数 '{param_name}' 校验失败",
                            field=param_name,
                            value=val,
                            reason="自定义校验未通过",
                        )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def retry(
    max_attempts: int = DEFAULT_MAX_RETRY,
    delay: float = DEFAULT_RETRY_DELAY,
    backoff: float = DEFAULT_RETRY_BACKOFF,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """指数退避重试装饰器。

    Args:
        max_attempts: 最大尝试次数。
        delay: 初始延迟秒数。
        backoff: 退避乘数。
        exceptions: 需要重试的异常元组。

    Returns:
        装饰器函数。

    >>> call_count = 0
    >>> @retry(max_attempts=3, delay=0.01, backoff=1.0)
    ... def flaky() -> str:
    ...     global call_count
    ...     call_count += 1
    ...     if call_count < 3:
    ...         raise ValueError("暂时失败")
    ...     return "成功"
    >>> call_count = 0
    >>> flaky()
    '成功'
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_exc: BaseException | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    _logger.debug(
                        "函数 %s 第 %d 次尝试失败: %s, %.2f秒后重试",
                        fn.__name__, attempt, exc, current_delay,
                    )
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        current_delay *= backoff
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def timed(fn: Callable) -> Callable:
    """执行耗时日志装饰器。

    Args:
        fn: 被装饰的函数。

    Returns:
        包装后的函数。

    >>> @timed
    ... def fast() -> int:
    ...     return 42
    >>> fast()
    42
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = fn(*args, **kwargs)
        elapsed = time.perf_counter() - start
        _logger.info("函数 %s 执行耗时: %.4f 秒", fn.__name__, elapsed)
        return result
    return wrapper


def cached(maxsize: int = DEFAULT_CACHE_MAXSIZE, ttl_seconds: float = DEFAULT_CACHE_TTL) -> Callable:
    """带 TTL 的缓存装饰器。

    Args:
        maxsize: 最大缓存条目数。
        ttl_seconds: 缓存存活时间(秒)。

    Returns:
        装饰器函数。

    >>> @cached(maxsize=10, ttl_seconds=60)
    ... def compute(x: int) -> int:
    ...     return x * x
    >>> compute(5)
    25
    >>> compute(5)  # 命中缓存
    25
    """
    def decorator(fn: Callable) -> Callable:
        cache: dict[str, tuple[Any, float]] = {}
        lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = str((args, sorted(kwargs.items())))
            now = time.monotonic()
            with lock:
                if key in cache:
                    value, ts = cache[key]
                    if now - ts < ttl_seconds:
                        return value
                    else:
                        del cache[key]
            result = fn(*args, **kwargs)
            with lock:
                if len(cache) >= maxsize:
                    # 驱逐最旧的条目
                    oldest_key = min(cache, key=lambda k: cache[k][1])
                    del cache[oldest_key]
                cache[key] = (result, now)
            return result

        wrapper.cache_clear = lambda: cache.clear()  # type: ignore[attr-defined]
        return wrapper
    return decorator


def singleton(cls: type[T]) -> type[T]:
    """线程安全单例装饰器。

    Args:
        cls: 被装饰的类。

    Returns:
        单例化后的类。

    >>> @singleton
    ... class MyService:
    ...     pass
    >>> MyService() is MyService()
    True
    """
    instances: dict[type, Any] = {}
    lock = threading.Lock()
    orig_init = cls.__init__

    @functools.wraps(cls)  # type: ignore[misc]
    def get_instance(*args: Any, **kwargs: Any) -> Any:
        with lock:
            if cls not in instances:
                instance = object.__new__(cls)
                orig_init(instance, *args, **kwargs)
                instances[cls] = instance
            return instances[cls]

    get_instance._cls = cls  # type: ignore[attr-defined]
    get_instance.__name__ = cls.__name__  # type: ignore[attr-defined]
    get_instance.__qualname__ = cls.__qualname__  # type: ignore[attr-defined]
    return get_instance  # type: ignore[return-value]


def deprecated(reason: str = "", removal_version: str = "") -> Callable:
    """弃用警告装饰器。

    Args:
        reason: 弃用原因。
        removal_version: 计划移除的版本号。

    Returns:
        装饰器函数。

    >>> @deprecated("请使用新接口", "2.0.0")
    ... def old_func() -> str:
    ...     return "旧"
    >>> import warnings
    >>> with warnings.catch_warnings(record=True) as w:
    ...     warnings.simplefilter("always")
    ...     old_func()
    ...     len(w) > 0
    '旧'
    True
    """
    def decorator(fn: Callable) -> Callable:
        msg_parts = [f"函数 {fn.__name__} 已弃用"]
        if reason:
            msg_parts.append(f": {reason}")
        if removal_version:
            msg_parts.append(f" (将在 {removal_version} 版本移除)")
        msg = "".join(msg_parts)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def immutable(cls: type) -> type:
    """冻结实例属性装饰器,使实例在初始化后不可变。

    Args:
        cls: 被装饰的类。

    Returns:
        不可变化后的类。

    >>> @immutable
    ... class Point:
    ...     def __init__(self, x: int, y: int) -> None:
    ...         self.x = x
    ...         self.y = y
    >>> p = Point(1, 2)
    >>> p.x
    1
    >>> try:
    ...     p.x = 10
    ... except AttributeError:
    ...     True
    True
    """
    orig_init = cls.__init__

    def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
        object.__setattr__(self, "_immutable_frozen", False)
        orig_init(self, *args, **kwargs)
        object.__setattr__(self, "_immutable_frozen", True)

    def frozen_setattr(self: Any, name: str, value: Any) -> None:
        if getattr(self, "_immutable_frozen", False):
            raise AttributeError(f"不可变对象 {cls.__name__} 的属性 '{name}' 不允许修改")
        object.__setattr__(self, name, value)

    def frozen_delattr(self: Any, name: str) -> None:
        if getattr(self, "_immutable_frozen", False):
            raise AttributeError(f"不可变对象 {cls.__name__} 的属性 '{name}' 不允许删除")
        object.__delattr__(self, name)

    cls.__init__ = new_init  # type: ignore[misc]
    cls.__setattr__ = frozen_setattr  # type: ignore[assignment]
    cls.__delattr__ = frozen_delattr  # type: ignore[assignment]
    return cls


def contract(
    pre: Callable[..., bool] | None = None,
    post: Callable[[Any], bool] | None = None,
) -> Callable:
    """前置/后置条件契约装饰器。

    Args:
        pre: 前置条件函数,接收与被装饰函数相同的参数,返回 False 则抛出异常。
        post: 后置条件函数,接收返回值,返回 False 则抛出异常。

    Returns:
        装饰器函数。

    >>> @contract(pre=lambda x: x >= 0, post=lambda r: r >= 0)
    ... def sqrt_ish(x: float) -> float:
    ...     return x ** 0.5
    >>> sqrt_ish(4.0)
    2.0
    >>> try:
    ...     sqrt_ish(-1.0)
    ... except BusinessRuleError:
    ...     True
    True
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if pre is not None:
                if not pre(*args, **kwargs):
                    raise BusinessRuleError(
                        f"函数 {fn.__name__} 前置条件不满足",
                        context={"args": str(args), "kwargs": str(kwargs)},
                    )
            result = fn(*args, **kwargs)
            if post is not None:
                if not post(result):
                    raise BusinessRuleError(
                        f"函数 {fn.__name__} 后置条件不满足",
                        context={"result": str(result)},
                    )
            return result
        return wrapper
    return decorator


def trace_calls(fn: Callable) -> Callable:
    """调用链路跟踪日志装饰器。

    Args:
        fn: 被装饰的函数。

    Returns:
        包装后的函数。

    >>> @trace_calls
    ... def greet(name: str) -> str:
    ...     return f"你好, {name}"
    >>> greet("世界")
    '你好, 世界'
    """
    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        _logger.debug("调用 %s(args=%s, kwargs=%s)", fn.__name__, args, kwargs)
        result = fn(*args, **kwargs)
        _logger.debug("返回 %s -> %s", fn.__name__, result)
        return result
    return wrapper


def guard_none(*param_names: str) -> Callable:
    """None 值拦截装饰器。

    Args:
        *param_names: 不允许为 None 的参数名列表。

    Returns:
        装饰器函数。

    >>> @guard_none("name")
    ... def greet(name: str) -> str:
    ...     return f"你好, {name}"
    >>> try:
    ...     greet(None)
    ... except ValidationError:
    ...     True
    True
    """
    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            for pn in param_names:
                if pn in bound.arguments and bound.arguments[pn] is None:
                    raise ValidationError(
                        f"参数 '{pn}' 不允许为 None",
                        field=pn,
                        value=None,
                        reason="值为 None",
                    )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def safe_execute(
    default: Any = None,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable:
    """异常安全执行装饰器,捕获指定异常并返回默认值。

    Args:
        default: 异常时返回的默认值。
        exceptions: 需要捕获的异常元组。

    Returns:
        装饰器函数。

    >>> @safe_execute(default=-1)
    ... def risky(x: int) -> int:
    ...     return 10 // x
    >>> risky(0)
    -1
    >>> risky(2)
    5
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except exceptions as exc:
                _logger.warning("函数 %s 执行异常已捕获: %s, 返回默认值", fn.__name__, exc)
                return default
        return wrapper
    return decorator


def coerce_types(**type_map: type) -> Callable:
    """参数类型强制转换装饰器。

    Args:
        **type_map: 参数名到目标类型的映射。

    Returns:
        装饰器函数。

    >>> @coerce_types(x=int, y=float)
    ... def add(x: int, y: float) -> float:
    ...     return x + y
    >>> add("3", "4.5")
    7.5
    """
    def decorator(fn: Callable) -> Callable:
        sig = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            for pn, target_type in type_map.items():
                if pn in bound.arguments:
                    try:
                        bound.arguments[pn] = target_type(bound.arguments[pn])
                    except (ValueError, TypeError) as exc:
                        raise ValidationError(
                            f"参数 '{pn}' 无法转换为 {target_type.__name__}",
                            field=pn,
                            value=bound.arguments[pn],
                            reason=str(exc),
                        ) from exc
            return fn(*bound.args, **bound.kwargs)
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════════
# 区域 11: 核心基础设施组件
# ═══════════════════════════════════════════════════════════════

# --- Result 单子 ---

class Result(Generic[T]):
    """Result 基类,用于表达可能失败的计算。不直接实例化,使用 Ok 或 Err。"""

    def is_ok(self) -> bool:
        """是否为成功值。"""
        return isinstance(self, Ok)

    def is_err(self) -> bool:
        """是否为错误值。"""
        return isinstance(self, Err)

    def map(self, fn: Callable[[T], U]) -> Result[U]:
        """对成功值应用变换函数。

        Args:
            fn: 变换函数。

        Returns:
            新的 Result。
        """
        if isinstance(self, Ok):
            return Ok(fn(self._value))
        return self  # type: ignore[return-value]

    def flat_map(self, fn: Callable[[T], Result[U]]) -> Result[U]:
        """对成功值应用返回 Result 的变换函数(扁平化)。

        Args:
            fn: 返回 Result 的变换函数。

        Returns:
            新的 Result。
        """
        if isinstance(self, Ok):
            return fn(self._value)
        return self  # type: ignore[return-value]

    def tap(self, fn: Callable[[T], None]) -> Result[T]:
        """对成功值执行副作用函数,不影响值本身。

        Args:
            fn: 副作用函数。

        Returns:
            原 Result。
        """
        if isinstance(self, Ok):
            fn(self._value)
        return self

    def unwrap(self) -> T:
        """解包成功值,若为 Err 则抛出异常。

        Returns:
            内部值。

        Raises:
            ModuleError: 当 Result 为 Err 时。
        """
        if isinstance(self, Ok):
            return self._value
        raise ModuleError(f"对 Err 调用 unwrap: {self._error}", code="UNWRAP")  # type: ignore[attr-defined]

    def unwrap_or(self, default: T) -> T:
        """解包成功值,若为 Err 则返回默认值。

        Args:
            default: 默认值。

        Returns:
            成功值或默认值。
        """
        if isinstance(self, Ok):
            return self._value
        return default

    def __repr__(self) -> str:
        if isinstance(self, Ok):
            return f"Ok({self._value!r})"
        return f"Err({self._error!r})"  # type: ignore[attr-defined]


class Ok(Result[T]):
    """成功值包装。

    Args:
        value: 成功值。

    >>> Ok(42).map(lambda x: x * 2).unwrap()
    84
    """

    def __init__(self, value: T) -> None:
        self._value = value


class Err(Result[T]):
    """错误值包装。

    Args:
        error: 错误信息。

    >>> Err("失败").unwrap_or(0)
    0
    """

    def __init__(self, error: Any) -> None:
        self._error = error


# --- Option 单子 ---

class Option(Generic[T]):
    """Option 基类,用于表达可选值。不直接实例化,使用 Some 或 NOTHING。"""

    def is_some(self) -> bool:
        """是否有值。"""
        return isinstance(self, Some)

    def is_nothing(self) -> bool:
        """是否为空。"""
        return isinstance(self, _Nothing)

    def map(self, fn: Callable[[T], U]) -> Option[U]:
        """对值应用变换函数。

        Args:
            fn: 变换函数。

        Returns:
            新的 Option。
        """
        if isinstance(self, Some):
            return Some(fn(self._value))
        return self  # type: ignore[return-value]

    def flat_map(self, fn: Callable[[T], Option[U]]) -> Option[U]:
        """对值应用返回 Option 的变换函数。

        Args:
            fn: 返回 Option 的变换函数。

        Returns:
            新的 Option。
        """
        if isinstance(self, Some):
            return fn(self._value)
        return self  # type: ignore[return-value]

    def filter(self, pred: Callable[[T], bool]) -> Option[T]:
        """根据谓词过滤值。

        Args:
            pred: 谓词函数。

        Returns:
            满足谓词则返回自身,否则返回 Nothing。
        """
        if isinstance(self, Some) and pred(self._value):
            return self
        return Nothing

    def unwrap(self) -> T:
        """解包值,若为 Nothing 则抛出异常。

        Returns:
            内部值。

        Raises:
            ModuleError: 当 Option 为 Nothing 时。
        """
        if isinstance(self, Some):
            return self._value
        raise ModuleError("对 Nothing 调用 unwrap", code="UNWRAP")

    def unwrap_or(self, default: T) -> T:
        """解包值,若为 Nothing 则返回默认值。

        Args:
            default: 默认值。

        Returns:
            值或默认值。
        """
        if isinstance(self, Some):
            return self._value
        return default

    def __repr__(self) -> str:
        if isinstance(self, Some):
            return f"Some({self._value!r})"
        return "Nothing"


class Some(Option[T]):
    """有值包装。

    Args:
        value: 包装的值。

    >>> Some(10).map(lambda x: x + 5).unwrap()
    15
    """

    def __init__(self, value: T) -> None:
        self._value = value


class _Nothing(Option[Any]):
    """无值单例。

    >>> Nothing.unwrap_or(99)
    99
    """

    _instance: _Nothing | None = None
    _lock = threading.Lock()

    def __new__(cls) -> _Nothing:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance


Nothing: Option[Any] = _Nothing()


# --- Pipeline ---

class Pipeline(Generic[T]):
    """数据处理管道,支持链式操作。

    Args:
        data: 初始数据。

    >>> Pipeline(10).pipe(lambda x: x * 2, "乘二").pipe(lambda x: x + 1, "加一").unwrap()
    21
    """

    def __init__(self, data: T) -> None:
        self._data: Any = data
        self._error: Any = None
        self._trace: list[str] = []
        self._has_error = False

    def pipe(self, fn: Callable[[Any], Any], label: str = "") -> Pipeline:
        """应用变换函数。

        Args:
            fn: 变换函数。
            label: 步骤标签。

        Returns:
            自身,支持链式调用。
        """
        if self._has_error:
            return self
        try:
            self._data = fn(self._data)
            self._trace.append(label or fn.__name__)
        except Exception as exc:
            self._error = exc
            self._has_error = True
            self._trace.append(f"错误@{label or fn.__name__}: {exc}")
        return self

    def pipe_if(self, condition: bool, fn: Callable[[Any], Any], label: str = "") -> Pipeline:
        """条件性应用变换函数。

        Args:
            condition: 条件。
            fn: 变换函数。
            label: 步骤标签。

        Returns:
            自身。
        """
        if condition:
            return self.pipe(fn, label)
        self._trace.append(f"跳过@{label or fn.__name__}")
        return self

    def tap(self, fn: Callable[[Any], None]) -> Pipeline:
        """执行副作用函数,不改变数据。

        Args:
            fn: 副作用函数。

        Returns:
            自身。
        """
        if not self._has_error:
            fn(self._data)
        return self

    def catch(self, handler: Callable[[Exception], None]) -> Pipeline:
        """错误处理,若有错误则调用 handler。

        Args:
            handler: 错误处理函数。

        Returns:
            自身。
        """
        if self._has_error and self._error is not None:
            handler(self._error)
        return self

    def recover(self, fallback_fn: Callable[[Exception], Any]) -> Pipeline:
        """从错误中恢复。

        Args:
            fallback_fn: 恢复函数,接收异常,返回恢复值。

        Returns:
            自身。
        """
        if self._has_error and self._error is not None:
            self._data = fallback_fn(self._error)
            self._has_error = False
            self._error = None
            self._trace.append("已恢复")
        return self

    def unwrap(self) -> Any:
        """解包最终数据。

        Returns:
            管道中的数据。

        Raises:
            ModuleError: 若管道中存在未处理的错误。
        """
        if self._has_error:
            raise ModuleError(f"管道错误: {self._error}", code="PIPELINE")
        return self._data

    @property
    def trace(self) -> list[str]:
        """获取执行路径列表。"""
        return list(self._trace)


# --- Builder ---

class Builder(Generic[T]):
    """通用对象构建器。

    Args:
        target_cls: 目标类。

    >>> class User:
    ...     def __init__(self, name: str = "", age: int = 0) -> None:
    ...         self.name = name
    ...         self.age = age
    >>> u = Builder(User).set("name", "张三").set("age", 25).build()
    >>> u.name
    '张三'
    """

    def __init__(self, target_cls: type[T]) -> None:
        self._cls = target_cls
        self._attrs: dict[str, Any] = {}
        self._validators: list[Callable[[dict[str, Any]], bool]] = []

    def set(self, key: str, value: Any) -> Builder[T]:
        """设置属性值。

        Args:
            key: 属性名。
            value: 属性值。

        Returns:
            自身。
        """
        self._attrs[key] = value
        return self

    def set_if(self, condition: bool, key: str, value: Any) -> Builder[T]:
        """条件性设置属性值。

        Args:
            condition: 条件。
            key: 属性名。
            value: 属性值。

        Returns:
            自身。
        """
        if condition:
            self._attrs[key] = value
        return self

    def merge(self, data: dict[str, Any] | Builder) -> Builder[T]:
        """合并属性。

        Args:
            data: 字典或另一个 Builder。

        Returns:
            自身。
        """
        if isinstance(data, Builder):
            self._attrs.update(data._attrs)
        else:
            self._attrs.update(data)
        return self

    def configure(self, fn: Callable[[Builder[T]], None]) -> Builder[T]:
        """使用配置函数进行设置。

        Args:
            fn: 配置函数,接收 Builder 实例。

        Returns:
            自身。
        """
        fn(self)
        return self

    def validate(self, validator_fn: Callable[[dict[str, Any]], bool]) -> Builder[T]:
        """添加校验函数。

        Args:
            validator_fn: 校验函数。

        Returns:
            自身。
        """
        self._validators.append(validator_fn)
        return self

    def build(self) -> T:
        """构建目标对象。

        Returns:
            构建的对象。

        Raises:
            ValidationError: 校验不通过时。
        """
        for vf in self._validators:
            if not vf(self._attrs):
                raise ValidationError(
                    f"Builder 校验失败: {self._cls.__name__}",
                    field="builder",
                    reason="校验函数返回 False",
                )
        return self._cls(**self._attrs)


# --- Query ---

class Query(Generic[T]):
    """内存集合查询引擎。

    Args:
        collection: 可迭代集合。

    >>> Query([3,1,4,1,5]).where(lambda x: x > 2).order_by(lambda x: x).to_list()
    [3, 4, 5]
    """

    def __init__(self, collection: list[T] | tuple[T, ...] | Iterator[T]) -> None:
        self._items: list[T] = list(collection)

    def where(self, predicate: Callable[[T], bool]) -> Query[T]:
        """过滤满足条件的元素。

        Args:
            predicate: 谓词函数。

        Returns:
            新的 Query。
        """
        return Query([item for item in self._items if predicate(item)])

    def order_by(self, key: Callable[[T], Any], reverse: bool = False) -> Query[T]:
        """排序。

        Args:
            key: 排序键函数。
            reverse: 是否降序。

        Returns:
            新的 Query。
        """
        return Query(sorted(self._items, key=key, reverse=reverse))

    def group_by(self, key_fn: Callable[[T], Any]) -> dict[Any, list[T]]:
        """分组。

        Args:
            key_fn: 分组键函数。

        Returns:
            分组字典。
        """
        groups: dict[Any, list[T]] = {}
        for item in self._items:
            k = key_fn(item)
            groups.setdefault(k, []).append(item)
        return groups

    def select(self, projector: Callable[[T], Any]) -> Query[Any]:
        """投影。

        Args:
            projector: 投影函数。

        Returns:
            新的 Query。
        """
        return Query([projector(item) for item in self._items])

    def distinct(self, key_fn: Callable[[T], Any] | None = None) -> Query[T]:
        """去重。

        Args:
            key_fn: 去重键函数,为 None 时使用元素本身。

        Returns:
            新的 Query。
        """
        seen: set[Any] = set()
        result: list[T] = []
        for item in self._items:
            k = key_fn(item) if key_fn else item
            if k not in seen:
                seen.add(k)
                result.append(item)
        return Query(result)

    def limit(self, n: int) -> Query[T]:
        """限制返回数量。

        Args:
            n: 最大数量。

        Returns:
            新的 Query。
        """
        return Query(self._items[:n])

    def offset(self, n: int) -> Query[T]:
        """跳过前 n 个元素。

        Args:
            n: 跳过数量。

        Returns:
            新的 Query。
        """
        return Query(self._items[n:])

    def first(self) -> T | None:
        """获取第一个元素,无元素时返回 None。

        Returns:
            第一个元素或 None。
        """
        return self._items[0] if self._items else None

    def to_list(self) -> list[T]:
        """转换为列表。

        Returns:
            元素列表。
        """
        return list(self._items)

    def count(self) -> int:
        """返回元素数量。

        Returns:
            数量。
        """
        return len(self._items)

    def exists(self) -> bool:
        """是否存在元素。

        Returns:
            布尔值。
        """
        return len(self._items) > 0

    def aggregate(self, fn: Callable[[Any, T], Any], initial: Any = 0) -> Any:
        """聚合操作。

        Args:
            fn: 聚合函数。
            initial: 初始值。

        Returns:
            聚合结果。
        """
        result = initial
        for item in self._items:
            result = fn(result, item)
        return result

    def sum(self, key: Callable[[T], float | int] | None = None) -> float | int:
        """求和。

        Args:
            key: 提取数值的键函数,为 None 时直接求和。

        Returns:
            总和。
        """
        if key:
            return sum(key(item) for item in self._items)
        return sum(self._items)  # type: ignore[arg-type]

    def avg(self, key: Callable[[T], float | int] | None = None) -> float:
        """求平均值。

        Args:
            key: 提取数值的键函数。

        Returns:
            平均值。

        Raises:
            ModuleError: 集合为空时。
        """
        if not self._items:
            raise ModuleError("空集合无法求平均值", code="QUERY_AVG")
        total = self.sum(key)
        return float(total) / len(self._items)


# --- EventBus ---

class EventBus:
    """事件总线,支持订阅/发布模式。

    >>> bus = EventBus()
    >>> results = []
    >>> bus.on("greet", lambda payload: results.append(payload))
    <...EventBus...>
    >>> bus.emit("greet", "你好")
    <...EventBus...>
    >>> results
    ['你好']
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = {}
        self._once_handlers: dict[str, list[Callable]] = {}

    def on(self, event: str, handler: Callable) -> EventBus:
        """注册事件处理器。

        Args:
            event: 事件名。
            handler: 处理函数。

        Returns:
            自身。
        """
        self._handlers.setdefault(event, []).append(handler)
        return self

    def once(self, event: str, handler: Callable) -> EventBus:
        """注册一次性事件处理器。

        Args:
            event: 事件名。
            handler: 处理函数。

        Returns:
            自身。
        """
        self._once_handlers.setdefault(event, []).append(handler)
        return self

    def emit(self, event: str, payload: Any = None) -> EventBus:
        """发布事件。

        Args:
            event: 事件名。
            payload: 事件数据。

        Returns:
            自身。
        """
        for h in self._handlers.get(event, []):
            h(payload)
        once_list = self._once_handlers.pop(event, [])
        for h in once_list:
            h(payload)
        return self

    def off(self, event: str | None = None) -> EventBus:
        """取消订阅。

        Args:
            event: 事件名,为 None 时取消所有订阅。

        Returns:
            自身。
        """
        if event is None:
            self._handlers.clear()
            self._once_handlers.clear()
        else:
            self._handlers.pop(event, None)
            self._once_handlers.pop(event, None)
        return self


# --- Registry ---

class Registry(Generic[T]):
    """策略/插件注册表。

    >>> reg = Registry()
    >>> @reg.register("upper")
    ... class UpperFormatter:
    ...     def format(self, s: str) -> str: return s.upper()
    >>> reg.has("upper")
    True
    >>> reg.list_names()
    ['upper']
    """

    def __init__(self) -> None:
        self._registry: dict[str, Any] = {}

    def register(self, name: str) -> Callable:
        """注册装饰器。

        Args:
            name: 注册名称。

        Returns:
            类装饰器。
        """
        def decorator(cls: type) -> type:
            self._registry[name] = cls
            return cls
        return decorator

    def register_instance(self, name: str, instance: Any) -> None:
        """直接注册实例。

        Args:
            name: 注册名称。
            instance: 实例对象。
        """
        self._registry[name] = instance

    def get(self, name: str) -> Any:
        """获取注册项。

        Args:
            name: 注册名称。

        Returns:
            注册的类或实例。

        Raises:
            EntityNotFoundError: 未找到时。
        """
        if name not in self._registry:
            raise EntityNotFoundError(
                f"注册项 '{name}' 未找到",
                entity_type="Registry",
                identifier=name,
            )
        return self._registry[name]

    def list_names(self) -> list[str]:
        """列出所有注册名称。

        Returns:
            名称列表。
        """
        return list(self._registry.keys())

    def has(self, name: str) -> bool:
        """检查是否已注册。

        Args:
            name: 名称。

        Returns:
            布尔值。
        """
        return name in self._registry


# --- StateMachine ---

class StateMachine:
    """有限状态机。

    >>> sm = StateMachine("idle")
    >>> sm.add_transition("idle", "start", "running")
    <...StateMachine...>
    >>> sm.trigger("start")
    <...StateMachine...>
    >>> sm.current
    'running'
    """

    def __init__(self, initial_state: str) -> None:
        self._current = initial_state
        self._transitions: dict[tuple[str, str], tuple[str, Callable[[], bool] | None]] = {}
        self._on_enter: dict[str, list[Callable]] = {}
        self._on_exit: dict[str, list[Callable]] = {}
        self._on_transition: list[Callable[[str, str, str], None]] = []
        self._history: list[str] = [initial_state]

    @property
    def current(self) -> str:
        """当前状态。"""
        return self._current

    @property
    def history(self) -> list[str]:
        """状态历史。"""
        return list(self._history)

    def add_transition(
        self,
        from_state: str,
        trigger: str,
        to_state: str,
        guard: Callable[[], bool] | None = None,
    ) -> StateMachine:
        """添加状态迁移规则。

        Args:
            from_state: 源状态。
            trigger: 触发动作。
            to_state: 目标状态。
            guard: 可选守卫条件。

        Returns:
            自身。
        """
        self._transitions[(from_state, trigger)] = (to_state, guard)
        return self

    def on_enter(self, state: str, callback: Callable) -> StateMachine:
        """注册进入状态回调。

        Args:
            state: 状态名。
            callback: 回调函数。

        Returns:
            自身。
        """
        self._on_enter.setdefault(state, []).append(callback)
        return self

    def on_exit(self, state: str, callback: Callable) -> StateMachine:
        """注册退出状态回调。

        Args:
            state: 状态名。
            callback: 回调函数。

        Returns:
            自身。
        """
        self._on_exit.setdefault(state, []).append(callback)
        return self

    def on_transition(self, callback: Callable[[str, str, str], None]) -> StateMachine:
        """注册迁移回调。

        Args:
            callback: 回调函数,接收 (from_state, trigger, to_state)。

        Returns:
            自身。
        """
        self._on_transition.append(callback)
        return self

    def can_trigger(self, action: str) -> bool:
        """检查是否可以触发指定动作。

        Args:
            action: 动作名。

        Returns:
            布尔值。
        """
        key = (self._current, action)
        if key not in self._transitions:
            return False
        _, guard = self._transitions[key]
        if guard and not guard():
            return False
        return True

    def trigger(self, action: str) -> StateMachine:
        """触发状态迁移。

        Args:
            action: 动作名。

        Returns:
            自身。

        Raises:
            StateTransitionError: 迁移非法时。
        """
        key = (self._current, action)
        if key not in self._transitions:
            raise StateTransitionError(
                f"状态 '{self._current}' 无法处理动作 '{action}'",
                context={"current": self._current, "action": action},
            )
        to_state, guard = self._transitions[key]
        if guard and not guard():
            raise StateTransitionError(
                f"状态迁移守卫条件不满足: {self._current} --{action}--> {to_state}",
                context={"current": self._current, "action": action, "to": to_state},
            )
        from_state = self._current
        # 退出回调
        for cb in self._on_exit.get(from_state, []):
            cb()
        # 迁移回调
        for cb in self._on_transition:
            cb(from_state, action, to_state)
        self._current = to_state
        self._history.append(to_state)
        # 进入回调
        for cb in self._on_enter.get(to_state, []):
            cb()
        return self


# --- Container (依赖注入) ---

class Container:
    """依赖注入容器。

    >>> c = Container()
    >>> c.instance(str, "hello").resolve(str)
    'hello'
    """

    def __init__(self) -> None:
        self._singletons: dict[type | str, Callable] = {}
        self._factories: dict[type | str, Callable] = {}
        self._instances: dict[type | str, Any] = {}
        self._singleton_cache: dict[type | str, Any] = {}
        self._lock = threading.Lock()

    def singleton(self, interface: type | str, factory: Callable[..., Any]) -> Container:
        """注册单例工厂。

        Args:
            interface: 接口类型或名称。
            factory: 工厂函数。

        Returns:
            自身。
        """
        self._singletons[interface] = factory
        return self

    def factory(self, interface: type | str, factory: Callable[..., Any]) -> Container:
        """注册工厂(每次创建新实例)。

        Args:
            interface: 接口类型或名称。
            factory: 工厂函数。

        Returns:
            自身。
        """
        self._factories[interface] = factory
        return self

    def instance(self, interface: type | str, existing_obj: Any) -> Container:
        """注册已有实例。

        Args:
            interface: 接口类型或名称。
            existing_obj: 已有对象。

        Returns:
            自身。
        """
        self._instances[interface] = existing_obj
        return self

    def resolve(self, interface: type | str) -> Any:
        """解析依赖。

        Args:
            interface: 接口类型或名称。

        Returns:
            解析到的对象。

        Raises:
            ConfigurationError: 未注册时。
        """
        # 实例优先
        if interface in self._instances:
            return self._instances[interface]
        # 单例
        if interface in self._singletons:
            with self._lock:
                if interface not in self._singleton_cache:
                    self._singleton_cache[interface] = self._singletons[interface](self)
                return self._singleton_cache[interface]
        # 工厂
        if interface in self._factories:
            return self._factories[interface](self)
        raise ConfigurationError(
            f"依赖 '{interface}' 未注册",
            context={"interface": str(interface)},
        )

    def build(self) -> Container:
        """构建容器(当前为空操作,预留扩展)。

        Returns:
            自身。
        """
        return self


# ═══════════════════════════════════════════════════════════════
# 区域 12: 序列化协议与配置管理
# ═══════════════════════════════════════════════════════════════

@dataclass
class Config:
    """统一配置,支持: 默认值 < 环境变量 < CLI 参数 覆盖链。

    Attributes:
        log_level: 日志级别名称。
        log_file: 日志文件路径。
        chunk_size: 上传分块大小(字节)。
        max_workers: 上传线程池大小。
        base_url: 文叔叔基础 URL。
        user_agent: HTTP User-Agent。

    >>> c = Config()
    >>> c.chunk_size == WSS_CHUNK_SIZE
    True
    """

    log_level: str = "INFO"
    log_file: str | None = None
    chunk_size: int = WSS_CHUNK_SIZE
    max_workers: int = UPLOAD_MAX_WORKERS
    base_url: str = WSS_BASE_URL
    user_agent: str = WSS_DEFAULT_USER_AGENT

    @classmethod
    def from_env(cls, prefix: str = "WSS_") -> Config:
        """从环境变量加载配置。

        Args:
            prefix: 环境变量前缀。

        Returns:
            Config 实例。
        """
        kwargs: dict[str, Any] = {}
        env_map: dict[str, tuple[str, type]] = {
            "LOG_LEVEL": ("log_level", str),
            "LOG_FILE": ("log_file", str),
            "CHUNK_SIZE": ("chunk_size", int),
            "MAX_WORKERS": ("max_workers", int),
            "BASE_URL": ("base_url", str),
            "USER_AGENT": ("user_agent", str),
        }
        for env_suffix, (attr_name, attr_type) in env_map.items():
            val = os.environ.get(f"{prefix}{env_suffix}")
            if val is not None:
                try:
                    kwargs[attr_name] = attr_type(val)
                except (ValueError, TypeError):
                    pass
        return cls(**kwargs)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        """从字典创建配置。

        Args:
            data: 配置字典。

        Returns:
            Config 实例。
        """
        valid_fields = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)

    def override(self, **kwargs: Any) -> Config:
        """链式覆盖配置项,返回新实例。

        Args:
            **kwargs: 要覆盖的配置项。

        Returns:
            新的 Config 实例。
        """
        current = dataclasses.asdict(self)
        current.update(kwargs)
        return Config.from_dict(current)

    def validate(self) -> None:
        """校验配置有效性。

        Raises:
            ConfigurationError: 配置无效时。
        """
        if self.chunk_size <= 0:
            raise ConfigurationError("chunk_size 必须为正整数", context={"chunk_size": self.chunk_size})
        if self.max_workers <= 0:
            raise ConfigurationError("max_workers 必须为正整数", context={"max_workers": self.max_workers})
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_levels:
            raise ConfigurationError(
                f"无效的日志级别: {self.log_level}",
                context={"log_level": self.log_level, "valid": list(valid_levels)},
            )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。

        Returns:
            配置字典。
        """
        return dataclasses.asdict(self)


# ═══════════════════════════════════════════════════════════════
# 区域 13: 资源管理与上下文工具
# ═══════════════════════════════════════════════════════════════

# managed_resource 已在区域 09 定义


# ═══════════════════════════════════════════════════════════════
# 区域 14: 领域模型
# ═══════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FileHash:
    """文件哈希值对象。

    Attributes:
        md5: MD5 十六进制摘要。
        sha1: SHA1 十六进制摘要。

    >>> fh = FileHash(md5="abc", sha1="def")
    >>> fh.md5
    'abc'
    """

    md5: str
    sha1: str

    def __post_init__(self) -> None:
        if not self.md5:
            raise ValidationError("MD5 哈希不能为空", field="md5", reason="空值")
        if not self.sha1:
            raise ValidationError("SHA1 哈希不能为空", field="sha1", reason="空值")

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {"md5": self.md5, "sha1": self.sha1}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileHash:
        """从字典反序列化。"""
        return cls(md5=data["md5"], sha1=data["sha1"])

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> FileHash:
        """从 JSON 字符串反序列化。"""
        return cls.from_dict(json.loads(raw))


@dataclass(frozen=True)
class TransferInfo:
    """传输信息值对象。

    Attributes:
        tid: 任务 ID。
        bid: Box ID。
        ufileid: 文件 ID。
        token: 共享令牌。

    >>> ti = TransferInfo(tid="t1", bid="b1", ufileid="u1")
    >>> ti.tid
    't1'
    """

    tid: str
    bid: str = ""
    ufileid: str = ""
    token: str = ""

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {"tid": self.tid, "bid": self.bid, "ufileid": self.ufileid, "token": self.token}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferInfo:
        """从字典反序列化。"""
        return cls(
            tid=data.get("tid", ""),
            bid=data.get("bid", ""),
            ufileid=data.get("ufileid", ""),
            token=data.get("token", ""),
        )

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> TransferInfo:
        """从 JSON 反序列化。"""
        return cls.from_dict(json.loads(raw))


@dataclass
class FileRecord:
    """文件记录实体。

    Attributes:
        id: 唯一标识。
        name: 文件名。
        size: 文件大小(字节)。
        hash_info: 文件哈希信息。
        status: 文件状态。
        created_at: 创建时间戳。

    >>> fr = FileRecord(name="test.txt", size=100, hash_info=FileHash(md5="a", sha1="b"))
    >>> fr.name
    'test.txt'
    """

    name: str
    size: int
    hash_info: FileHash | None = None
    status: str = "pending"
    id: str = field(default_factory=generate_id)
    created_at: float = field(default_factory=time.time)

    def mark_uploaded(self) -> None:
        """标记为已上传。"""
        self.status = "uploaded"

    def mark_failed(self, reason: str = "") -> None:
        """标记为失败。

        Args:
            reason: 失败原因。
        """
        self.status = f"failed: {reason}" if reason else "failed"

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "size": self.size,
            "hash_info": self.hash_info.to_dict() if self.hash_info else None,
            "status": self.status,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileRecord:
        """从字典反序列化。"""
        hi = FileHash.from_dict(data["hash_info"]) if data.get("hash_info") else None
        return cls(
            name=data["name"],
            size=data["size"],
            hash_info=hi,
            status=data.get("status", "pending"),
            id=data.get("id", generate_id()),
            created_at=data.get("created_at", time.time()),
        )

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON。"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, raw: str) -> FileRecord:
        """从 JSON 反序列化。"""
        return cls.from_dict(json.loads(raw))


@dataclass
class TransferTask:
    """传输任务聚合根。

    Attributes:
        id: 唯一标识。
        direction: 传输方向('upload'或'download')。
        files: 文件列表。
        transfer_info: 传输信息。
        events: 领域事件列表。

    >>> tt = TransferTask(direction="upload")
    >>> tt.add_file(FileRecord(name="a.txt", size=10))
    >>> len(tt.files)
    1
    """

    direction: str
    files: list[FileRecord] = field(default_factory=list)
    transfer_info: TransferInfo | None = None
    id: str = field(default_factory=generate_id)
    events: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.direction not in ("upload", "download"):
            raise ValidationError(
                "传输方向必须为 'upload' 或 'download'",
                field="direction",
                value=self.direction,
            )

    def add_file(self, file_record: FileRecord) -> None:
        """添加文件到任务。

        Args:
            file_record: 文件记录。
        """
        self.files.append(file_record)
        self.events.append({
            "type": "file_added",
            "file_id": file_record.id,
            "file_name": file_record.name,
            "timestamp": time.time(),
        })

    def complete(self) -> None:
        """标记任务完成。"""
        for f in self.files:
            if "failed" not in f.status:
                f.mark_uploaded()
        self.events.append({
            "type": "task_completed",
            "task_id": self.id,
            "timestamp": time.time(),
        })

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "id": self.id,
            "direction": self.direction,
            "files": [f.to_dict() for f in self.files],
            "transfer_info": self.transfer_info.to_dict() if self.transfer_info else None,
            "events": self.events,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TransferTask:
        """从字典反序列化。"""
        tt = cls(
            direction=data["direction"],
            id=data.get("id", generate_id()),
        )
        tt.files = [FileRecord.from_dict(fd) for fd in data.get("files", [])]
        if data.get("transfer_info"):
            tt.transfer_info = TransferInfo.from_dict(data["transfer_info"])
        tt.events = data.get("events", [])
        return tt


# ═══════════════════════════════════════════════════════════════
# 区域 15: 领域行为对象(规约 / 策略)
# ═══════════════════════════════════════════════════════════════

class Specification(Generic[T]):
    """规约模式基类,支持 & | ~ 组合。

    >>> class IsPositiveSpec(Specification[int]):
    ...     def is_satisfied_by(self, candidate: int) -> bool:
    ...         return candidate > 0
    >>> class IsEvenSpec(Specification[int]):
    ...     def is_satisfied_by(self, candidate: int) -> bool:
    ...         return candidate % 2 == 0
    >>> spec = IsPositiveSpec() & IsEvenSpec()
    >>> spec.is_satisfied_by(4)
    True
    >>> spec.is_satisfied_by(-2)
    False
    """

    def is_satisfied_by(self, candidate: T) -> bool:
        """检查候选对象是否满足规约。

        Args:
            candidate: 候选对象。

        Returns:
            是否满足。
        """
        raise NotImplementedError("子类必须实现此方法")

    def __and__(self, other: Specification[T]) -> Specification[T]:
        return _AndSpec(self, other)

    def __or__(self, other: Specification[T]) -> Specification[T]:
        return _OrSpec(self, other)

    def __invert__(self) -> Specification[T]:
        return _NotSpec(self)


class _AndSpec(Specification[T]):
    """与规约。"""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) and self._right.is_satisfied_by(candidate)


class _OrSpec(Specification[T]):
    """或规约。"""

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self._left = left
        self._right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return self._left.is_satisfied_by(candidate) or self._right.is_satisfied_by(candidate)


class _NotSpec(Specification[T]):
    """非规约。"""

    def __init__(self, spec: Specification[T]) -> None:
        self._spec = spec

    def is_satisfied_by(self, candidate: T) -> bool:
        return not self._spec.is_satisfied_by(candidate)


class FileSizeSpec(Specification[FileRecord]):
    """文件大小规约: 检查文件大小是否不超过指定限制。

    Args:
        max_bytes: 最大字节数。

    >>> spec = FileSizeSpec(1024)
    >>> spec.is_satisfied_by(FileRecord(name="a.txt", size=500))
    True
    >>> spec.is_satisfied_by(FileRecord(name="b.bin", size=2000))
    False
    """

    def __init__(self, max_bytes: int) -> None:
        self._max = max_bytes

    def is_satisfied_by(self, candidate: FileRecord) -> bool:
        return candidate.size <= self._max


class FileNamePatternSpec(Specification[FileRecord]):
    """文件名正则规约。

    Args:
        pattern: 正则表达式模式。

    >>> spec = FileNamePatternSpec(r".*\\.txt$")
    >>> spec.is_satisfied_by(FileRecord(name="doc.txt", size=10))
    True
    """

    def __init__(self, pattern: str) -> None:
        self._re = re.compile(pattern)

    def is_satisfied_by(self, candidate: FileRecord) -> bool:
        return bool(self._re.match(candidate.name))


# ═══════════════════════════════════════════════════════════════
# 区域 16: 仓储
# ═══════════════════════════════════════════════════════════════

class AbstractRepository(abc.ABC, Generic[TEntity]):
    """抽象仓储接口。"""

    @abc.abstractmethod
    def save(self, entity: TEntity) -> None:
        """保存实体。"""

    @abc.abstractmethod
    def find_by_id(self, entity_id: str) -> TEntity | None:
        """根据 ID 查找实体。"""

    @abc.abstractmethod
    def find_all(self) -> list[TEntity]:
        """查找所有实体。"""

    @abc.abstractmethod
    def delete(self, entity_id: str) -> bool:
        """删除实体,返回是否成功。"""

    @abc.abstractmethod
    def exists(self, entity_id: str) -> bool:
        """检查实体是否存在。"""


class InMemoryFileRecordRepository(AbstractRepository[FileRecord]):
    """文件记录内存仓储实现。

    >>> repo = InMemoryFileRecordRepository()
    >>> fr = FileRecord(name="test.txt", size=100)
    >>> repo.save(fr)
    >>> repo.exists(fr.id)
    True
    >>> repo.find_by_id(fr.id).name
    'test.txt'
    >>> repo.delete(fr.id)
    True
    """

    def __init__(self) -> None:
        self._store: dict[str, FileRecord] = {}

    def save(self, entity: FileRecord) -> None:
        """保存文件记录。"""
        self._store[entity.id] = entity

    def find_by_id(self, entity_id: str) -> FileRecord | None:
        """根据 ID 查找。"""
        return self._store.get(entity_id)

    def find_all(self) -> list[FileRecord]:
        """获取所有记录。"""
        return list(self._store.values())

    def delete(self, entity_id: str) -> bool:
        """删除记录。"""
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False

    def exists(self, entity_id: str) -> bool:
        """检查是否存在。"""
        return entity_id in self._store


class InMemoryTransferTaskRepository(AbstractRepository[TransferTask]):
    """传输任务内存仓储实现。

    >>> repo = InMemoryTransferTaskRepository()
    >>> tt = TransferTask(direction="upload")
    >>> repo.save(tt)
    >>> repo.exists(tt.id)
    True
    """

    def __init__(self) -> None:
        self._store: dict[str, TransferTask] = {}

    def save(self, entity: TransferTask) -> None:
        """保存任务。"""
        self._store[entity.id] = entity

    def find_by_id(self, entity_id: str) -> TransferTask | None:
        """根据 ID 查找。"""
        return self._store.get(entity_id)

    def find_all(self) -> list[TransferTask]:
        """获取所有任务。"""
        return list(self._store.values())

    def delete(self, entity_id: str) -> bool:
        """删除任务。"""
        if entity_id in self._store:
            del self._store[entity_id]
            return True
        return False

    def exists(self, entity_id: str) -> bool:
        """检查是否存在。"""
        return entity_id in self._store


# ═══════════════════════════════════════════════════════════════
# 区域 17: 应用服务 / 用例 / DTO
# ═══════════════════════════════════════════════════════════════

@dataclass
class UploadRequest:
    """上传请求 DTO。

    Attributes:
        file_path: 文件路径。
        password: 密码(可选)。
        expire_days: 过期天数。
    """

    file_path: str
    password: str = ""
    expire_days: str = "1"


@dataclass
class DownloadRequest:
    """下载请求 DTO。

    Attributes:
        url: 下载链接或令牌。
        password: 密码(可选)。
    """

    url: str
    password: str = ""


@dataclass
class TransferResponse:
    """传输响应 DTO。

    Attributes:
        success: 是否成功。
        message: 消息。
        data: 额外数据。
    """

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)


class UploadUseCase:
    """上传用例。

    Args:
        client: 文叔叔客户端实例。
        file_repo: 文件记录仓储。
    """

    def __init__(self, client: WenShuShuClient, file_repo: InMemoryFileRecordRepository) -> None:
        self._client = client
        self._file_repo = file_repo

    def execute(self, request: UploadRequest) -> TransferResponse:
        """执行上传用例。

        Args:
            request: 上传请求。

        Returns:
            传输响应。
        """
        file_path = request.file_path
        if not os.path.isfile(file_path):
            raise UseCaseError(f"文件不存在: {file_path}", context={"file_path": file_path})
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        record = FileRecord(name=file_name, size=file_size)
        self._file_repo.save(record)
        try:
            result = self._client.upload(file_path)
            record.mark_uploaded()
            return TransferResponse(success=True, message="上传成功", data=result)
        except Exception as exc:
            record.mark_failed(str(exc))
            raise UseCaseError(f"上传失败: {exc}", context={"file": file_name}) from exc


class DownloadUseCase:
    """下载用例。

    Args:
        client: 文叔叔客户端实例。
    """

    def __init__(self, client: WenShuShuClient) -> None:
        self._client = client

    def execute(self, request: DownloadRequest) -> TransferResponse:
        """执行下载用例。

        Args:
            request: 下载请求。

        Returns:
            传输响应。
        """
        try:
            result = self._client.download(request.url, request.password)
            return TransferResponse(success=True, message="下载成功", data=result)
        except Exception as exc:
            raise UseCaseError(f"下载失败: {exc}", context={"url": request.url}) from exc


# ═══════════════════════════════════════════════════════════════
# 区域 18: 接口适配层 - 文叔叔客户端核心
# ═══════════════════════════════════════════════════════════════

class WenShuShuClient:
    """文叔叔文件传输客户端。

    封装了匿名登录、文件上传(含秒传/分块)、文件下载的全部逻辑。

    Args:
        config: 配置对象。

    >>> client = WenShuShuClient.__new__(WenShuShuClient)
    >>> client._config = Config()
    >>> client._config.base_url
    'https://www.wenshushu.cn'
    """

    def __init__(self, config: Config | None = None) -> None:
        self._config = config or Config()
        self._session: Any = None
        self._token: str = ""

    def _ensure_session(self) -> Any:
        """确保 HTTP 会话已初始化并登录。

        Returns:
            requests.Session 实例。
        """
        if self._session is None:
            self._session = _requests.Session()
            self._session.headers["User-Agent"] = self._config.user_agent
            self._session.headers["Accept-Language"] = WSS_DEFAULT_ACCEPT_LANG
            self._token = self._login_anonymous()
            self._session.headers["X-TOKEN"] = self._token
        return self._session

    def _login_anonymous(self) -> str:
        """匿名登录获取令牌。

        Returns:
            认证令牌字符串。

        Raises:
            ExternalServiceError: 登录失败时。
        """
        s = self._session
        try:
            r = s.post(
                url=f"{self._config.base_url}/ap/login/anonymous",
                json={"dev_info": "{}"},
            )
            rsp = r.json()
            token = rsp["data"]["token"]
            _logger.info("匿名登录成功")
            return token
        except Exception as exc:
            raise ExternalServiceError(f"匿名登录失败: {exc}") from exc

    def _get_epochtime(self) -> str:
        """获取服务器纪元时间戳。

        Returns:
            时间戳字符串。
        """
        s = self._ensure_session()
        r = s.get(
            url=f"{self._config.base_url}/ag/time",
            headers={
                "Prod": "com.wenshushu.web.pc",
                "Referer": f"{self._config.base_url}/",
            },
        )
        return r.json()["data"]["time"]

    def _get_cipher_header(self, epochtime: str, token: str, data: dict[str, Any]) -> bytes:
        """生成加密签名头。

        使用 DES/CBC/PKCS7Padding 加密方式。

        Args:
            epochtime: 服务器时间戳。
            token: 认证令牌。
            data: 请求数据。

        Returns:
            Base64 编码的密文。
        """
        json_dumps = json.dumps(data, ensure_ascii=False)
        md5_hash_code = hashlib.md5((json_dumps + token).encode()).hexdigest()
        base58_hash_code = _base58.b58encode(md5_hash_code)
        # 时间戳逆序取5位并作为时间戳字串索引再次取值,最后拼接"000"
        key_iv = (
            "".join([epochtime[int(i)] for i in epochtime[::-1][:5]]) + "000"
        ).encode()
        cipher = _DES.new(key_iv, _DES.MODE_CBC, key_iv)
        ciphertext = cipher.encrypt(
            _Padding.pad(base58_hash_code, _DES.block_size, style="pkcs7")
        )
        return base64.b64encode(ciphertext)

    def _calc_file_hash(
        self,
        file_path: str,
        hash_type: str,
        block: bytes | None = None,
        chunk_size: int = WSS_CHUNK_SIZE,
    ) -> str:
        """计算文件或数据块的哈希值。

        Args:
            file_path: 文件路径。
            hash_type: 'MD5' 或 'SHA1'。
            block: 可选的数据块,为 None 时从文件读取。
            chunk_size: 读取大小。

        Returns:
            十六进制哈希字符串。
        """
        file_size = os.path.getsize(file_path)
        is_part = file_size > chunk_size
        read_size = chunk_size if is_part else None
        if block is None:
            with open(file_path, "rb") as f:
                block = f.read(read_size) if read_size else f.read()
        if hash_type == "MD5":
            return hashlib.md5(block).hexdigest()
        elif hash_type == "SHA1":
            return hashlib.sha1(block).hexdigest()
        raise ValidationError(f"不支持的哈希类型: {hash_type}", field="hash_type", value=hash_type)

    def _read_file_chunks(self, file_path: str, block_size: int = WSS_CHUNK_SIZE) -> Iterator[tuple[bytes, int]]:
        """按块读取文件。

        Args:
            file_path: 文件路径。
            block_size: 块大小。

        Yields:
            (数据块, 块编号) 元组。
        """
        part_num = 0
        with open(file_path, "rb") as f:
            while True:
                block = f.read(block_size)
                part_num += 1
                if block:
                    yield block, part_num
                else:
                    return

    def upload(self, file_path: str) -> dict[str, Any]:
        """上传文件到文叔叔。

        支持秒传检测和分块并发上传。

        Args:
            file_path: 要上传的文件路径。

        Returns:
            包含管理链接和公共链接的字典。

        Raises:
            ExternalServiceError: 上传过程中的网络或服务错误。
        """
        s = self._ensure_session()
        cfg = self._config
        chunk_size = cfg.chunk_size
        file_size = os.path.getsize(file_path)
        is_part = file_size > chunk_size
        file_name = os.path.basename(file_path)

        # 获取用户信息和存储空间
        self._show_storage(s)

        # 创建发送任务
        bid, ufileid, tid, up_id = self._addsend(s, file_size, chunk_size)

        # 尝试秒传
        fast_result = self._try_fast_upload(s, file_path, bid, ufileid, up_id, file_size, chunk_size, is_part)
        if fast_result is not None:
            # 秒传成功
            self._wait_process(s, up_id)
            return self._copysend(s, bid, tid, ufileid)

        # 正常上传
        if is_part:
            print("文件正在被分块上传!")
            self._upload_multipart(s, file_path, file_name, up_id, file_size, chunk_size)
        else:
            print("文件被整块上传!")
            self._upload_single(s, file_path, file_name, up_id, file_size)

        # 完成上传
        self._complete_upload(s, file_name, up_id, bid, ufileid, is_part)
        result = self._copysend(s, bid, tid, ufileid)
        self._wait_process(s, up_id)
        return result

    def _show_storage(self, s: Any) -> None:
        """显示存储空间信息。

        Args:
            s: HTTP 会话。
        """
        s.post(url=f"{self._config.base_url}/ap/user/userinfo", json={"plat": "pcweb"})
        r = s.post(url=f"{self._config.base_url}/ap/user/storage", json={})
        rsp = r.json()
        rest_space = int(rsp["data"]["rest_space"])
        send_space = int(rsp["data"]["send_space"])
        total = rest_space + send_space
        print(
            f"当前已用空间:{round(send_space / 1024 ** 3, 2)}GB,"
            f"剩余空间:{round(rest_space / 1024 ** 3, 2)}GB,"
            f"总空间:{round(total / 1024 ** 3, 2)}GB"
        )

    def _addsend(
        self, s: Any, file_size: int, chunk_size: int
    ) -> tuple[str, str, str, str]:
        """创建发送任务并获取上传 ID。

        Args:
            s: HTTP 会话。
            file_size: 文件大小。
            chunk_size: 分块大小。

        Returns:
            (bid, ufileid, tid, up_id) 元组。
        """
        epochtime = self._get_epochtime()
        req_data: dict[str, Any] = {
            "sender": "",
            "remark": "",
            "isextension": False,
            "notSaveTo": False,
            "notDownload": False,
            "notPreview": False,
            "downPreCountLimit": 0,
            "trafficStatus": 0,
            "pwd": "",
            "expire": "1",
            "recvs": ["social", "public"],
            "file_size": file_size,
            "file_count": 1,
        }
        r = s.post(
            url=f"{self._config.base_url}/ap/task/addsend",
            json=req_data,
            headers={
                "A-code": self._get_cipher_header(epochtime, self._token, req_data),
                "Prod": "com.wenshushu.web.pc",
                "Referer": f"{self._config.base_url}/",
                "Origin": self._config.base_url,
                "Req-Time": epochtime,
            },
        )
        rsp = r.json()
        if rsp.get("code") == 1021:
            raise ExternalServiceError(
                f"操作太快! 请{rsp.get('message', '稍')}秒后重试",
                context={"code": 1021},
            )
        data = rsp.get("data")
        if not data:
            raise ExternalServiceError("需要滑动验证码,请稍后重试")
        bid = data["bid"]
        ufileid = data["ufileid"]
        tid = data["tid"]

        # 获取 upId
        r2 = s.post(
            url=f"{self._config.base_url}/ap/uploadv2/getupid",
            json={
                "preid": ufileid,
                "boxid": bid,
                "linkid": tid,
                "utype": "sendcopy",
                "originUpid": "",
                "length": file_size,
                "count": 1,
            },
        )
        up_id = r2.json()["data"]["upId"]
        return bid, ufileid, tid, up_id

    def _try_fast_upload(
        self,
        s: Any,
        file_path: str,
        bid: str,
        ufileid: str,
        up_id: str,
        file_size: int,
        chunk_size: int,
        is_part: bool,
    ) -> dict[str, Any] | None:
        """尝试秒传。

        Args:
            s: HTTP 会话。
            file_path: 文件路径。
            bid: Box ID。
            ufileid: 文件 ID。
            up_id: 上传 ID。
            file_size: 文件大小。
            chunk_size: 分块大小。
            is_part: 是否分块。

        Returns:
            秒传成功时返回信息字典,否则返回 None。
        """
        cm1 = self._calc_file_hash(file_path, "MD5", chunk_size=chunk_size)
        cs1 = self._calc_file_hash(file_path, "SHA1", chunk_size=chunk_size)
        cm = sha1_of_string(cm1)
        name = os.path.basename(file_path)

        payload: dict[str, Any] = {
            "hash": {"cm1": cm1, "cs1": cs1},
            "uf": {"name": name, "boxid": bid, "preid": ufileid},
            "upId": up_id,
        }
        if not is_part:
            payload["hash"]["cm"] = cm

        for _ in range(2):
            r = s.post(url=f"{self._config.base_url}/ap/uploadv2/fast", json=payload)
            rsp = r.json()
            can_fast = rsp["data"]["status"]
            ufile = rsp["data"]["ufile"]
            if can_fast and not ufile:
                # 需要计算完整分块哈希
                hash_codes = ""
                for block, _ in self._read_file_chunks(file_path, chunk_size):
                    hash_codes += md5_of_bytes(block)
                payload["hash"]["cm"] = sha1_of_string(hash_codes)
            elif can_fast and ufile:
                print(f"文件{name}可以被秒传!")
                return {"fast": True, "name": name}
        return None

    def _get_psurl(
        self, s: Any, fname: str, up_id: str, fsize: int, is_part: bool, part_num: int | None = None
    ) -> str:
        """获取预签名上传 URL。

        Args:
            s: HTTP 会话。
            fname: 文件名。
            up_id: 上传 ID。
            fsize: 文件/分块大小。
            is_part: 是否分块。
            part_num: 分块编号。

        Returns:
            预签名 URL。
        """
        payload: dict[str, Any] = {
            "ispart": is_part,
            "fname": fname,
            "fsize": fsize,
            "upId": up_id,
        }
        if is_part and part_num is not None:
            payload["partnu"] = part_num
        r = s.post(url=f"{self._config.base_url}/ap/uploadv2/psurl", json=payload)
        return r.json()["data"]["url"]

    def _upload_single(self, s: Any, file_path: str, fname: str, up_id: str, file_size: int) -> None:
        """整块上传文件。

        Args:
            s: HTTP 会话。
            file_path: 文件路径。
            fname: 文件名。
            up_id: 上传 ID。
            file_size: 文件大小。
        """
        url = self._get_psurl(s, fname, up_id, file_size, False)
        with open(file_path, "rb") as f:
            _requests.put(url=url, data=f.read())
        print("上传完成:100%")

    def _upload_multipart(
        self, s: Any, file_path: str, fname: str, up_id: str, file_size: int, chunk_size: int
    ) -> None:
        """分块并发上传文件。

        Args:
            s: HTTP 会话。
            file_path: 文件路径。
            fname: 文件名。
            up_id: 上传 ID。
            file_size: 文件大小。
            chunk_size: 分块大小。
        """

        def _put_chunk(part_index: int) -> None:
            offset = chunk_size * part_index
            ul_size = min(chunk_size, file_size - offset)
            url = self._get_psurl(s, fname, up_id, ul_size, True, part_index + 1)
            with open(file_path, "rb") as fio:
                fio.seek(offset)
                _requests.put(url=url, data=fio.read(ul_size))

        total_parts = (file_size + chunk_size - 1) // chunk_size
        with ThreadPoolExecutor(max_workers=self._config.max_workers) as executor:
            futures = [executor.submit(_put_chunk, i) for i in range(total_parts)]
            completed = 0
            for _ in concurrent.futures.as_completed(futures):
                completed += 1
                pct = int(completed / total_parts * 100)
                print(f"分块进度:{pct}%", end="\r")
                if pct == 100:
                    print("上传完成:100%")

    def _complete_upload(
        self, s: Any, fname: str, up_id: str, bid: str, ufileid: str, is_part: bool
    ) -> None:
        """通知服务端上传完成。

        Args:
            s: HTTP 会话。
            fname: 文件名。
            up_id: 上传 ID。
            bid: Box ID。
            ufileid: 文件 ID。
            is_part: 是否分块。
        """
        s.post(
            url=f"{self._config.base_url}/ap/uploadv2/complete",
            json={
                "ispart": is_part,
                "fname": fname,
                "upId": up_id,
                "location": {"boxid": bid, "preid": ufileid},
            },
        )

    def _copysend(self, s: Any, bid: str, tid: str, ufileid: str) -> dict[str, Any]:
        """完成发送任务,获取分享链接。

        Args:
            s: HTTP 会话。
            bid: Box ID。
            tid: 任务 ID。
            ufileid: 文件 ID。

        Returns:
            包含管理链接和公共链接的字典。
        """
        r = s.post(
            url=f"{self._config.base_url}/ap/task/copysend",
            json={"bid": bid, "tid": tid, "ufileid": ufileid},
        )
        rsp = r.json()
        mgr_url = rsp["data"]["mgr_url"]
        public_url = rsp["data"]["public_url"]
        print(f"个人管理链接: {mgr_url}")
        print(f"公共链接: {public_url}")
        return {"mgr_url": mgr_url, "public_url": public_url}

    def _wait_process(self, s: Any, up_id: str) -> None:
        """等待服务端处理完成。

        Args:
            s: HTTP 会话。
            up_id: 上传 ID。
        """
        while True:
            r = s.post(
                url=f"{self._config.base_url}/ap/ufile/getprocess",
                json={"processId": up_id},
            )
            if r.json()["data"]["rst"] == "success":
                return
            time.sleep(1)

    def download(self, url: str, password: str = "") -> dict[str, Any]:
        """从文叔叔下载文件。

        Args:
            url: 文叔叔分享链接或令牌。
            password: 分享密码(可选)。

        Returns:
            包含文件名和状态的字典。

        Raises:
            ExternalServiceError: 下载过程中的网络或服务错误。
        """
        s = self._ensure_session()
        token_or_tid = url.split("/")[-1]

        if len(token_or_tid) == 16:
            # 通过 token 获取 tid
            r = s.post(
                url=f"{self._config.base_url}/ap/task/token",
                json={"token": token_or_tid},
            )
            tid = r.json()["data"]["tid"]
        elif len(token_or_tid) == 11:
            tid = token_or_tid
        else:
            raise ValidationError(
                f"无法识别的链接格式: {url}",
                field="url",
                value=url,
                reason="令牌长度应为 11 或 16",
            )

        # 获取任务信息
        r = s.post(
            url=f"{self._config.base_url}/ap/task/mgrtask",
            json={"tid": tid, "password": password},
        )
        rsp = r.json()
        expire = rsp["data"]["expire"]
        print(f"文件过期时间:{format_duration(float(expire))}")

        file_size = int(rsp["data"]["file_size"])
        print(f"文件大小:{format_file_size(file_size)}")

        bid = rsp["data"]["boxid"]
        pid = rsp["data"]["ufileid"]

        # 获取文件列表
        r = s.post(
            url=f"{self._config.base_url}/ap/ufile/list",
            json={
                "start": 0,
                "sort": {"name": "asc"},
                "bid": bid,
                "pid": pid,
                "type": 1,
                "options": {"uploader": "true"},
                "size": 50,
            },
        )
        rsp = r.json()
        file_info = rsp["data"]["fileList"][0]
        filename = file_info["fname"]
        fid = file_info["fid"]
        print(f"文件名:{filename}")

        # 获取下载签名
        r = s.post(
            url=f"{self._config.base_url}/ap/dl/sign",
            json={"consumeCode": 0, "type": 1, "ufileid": fid},
        )
        sign_data = r.json()["data"]
        if sign_data["url"] == "" and sign_data.get("ttNeed", 0) != 0:
            raise ExternalServiceError("对方的分享流量不足")

        dl_url = sign_data["url"]

        # 下载文件
        print("开始下载!", end="\r")
        r = s.get(dl_url, stream=True)
        dl_size = int(r.headers.get("Content-Length", 0))
        dl_count = 0
        block_size = self._config.chunk_size
        with open(filename, "wb") as f:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=block_size):
                f.write(chunk)
                dl_count += len(chunk)
                if dl_size > 0:
                    print(f"下载进度:{int(dl_count / dl_size * 100)}%", end="\r")
            print("下载完成:100%")

        return {"filename": filename, "size": dl_size, "status": "completed"}


# ═══════════════════════════════════════════════════════════════
# 区域 19: 容器组装 / 工厂 / 依赖注入
# ═══════════════════════════════════════════════════════════════

def create_container(config: Config | None = None) -> Container:
    """创建并配置依赖注入容器。

    Args:
        config: 配置对象。

    Returns:
        已配置的容器。

    >>> c = create_container()
    >>> isinstance(c.resolve(Config), Config)
    True
    """
    cfg = config or Config.from_env()
    container = Container()
    container.instance(Config, cfg)
    container.singleton(
        InMemoryFileRecordRepository,
        lambda c: InMemoryFileRecordRepository(),
    )
    container.singleton(
        InMemoryTransferTaskRepository,
        lambda c: InMemoryTransferTaskRepository(),
    )
    container.singleton(
        WenShuShuClient,
        lambda c: WenShuShuClient(c.resolve(Config)),
    )
    container.singleton(
        UploadUseCase,
        lambda c: UploadUseCase(
            c.resolve(WenShuShuClient),
            c.resolve(InMemoryFileRecordRepository),
        ),
    )
    container.singleton(
        DownloadUseCase,
        lambda c: DownloadUseCase(c.resolve(WenShuShuClient)),
    )
    container.singleton(EventBus, lambda c: EventBus())
    return container.build()


# ═══════════════════════════════════════════════════════════════
# 区域 20: 内嵌测试
# ═══════════════════════════════════════════════════════════════

class _TestRunner:
    """自包含测试运行器。

    自动发现 Test* 类中 test_* 方法并执行。
    支持 setUp / tearDown。
    """

    def __init__(self) -> None:
        self._passed = 0
        self._failed = 0
        self._errors = 0
        self._results: list[tuple[str, str, str]] = []

    def run_all(self, test_classes: list[type]) -> bool:
        """运行所有测试类。

        Args:
            test_classes: 测试类列表。

        Returns:
            是否全部通过。
        """
        for cls in test_classes:
            instance = cls()
            methods = [m for m in dir(instance) if m.startswith("test_")]
            for method_name in sorted(methods):
                full_name = f"{cls.__name__}.{method_name}"
                try:
                    if hasattr(instance, "setUp"):
                        instance.setUp()
                    getattr(instance, method_name)()
                    if hasattr(instance, "tearDown"):
                        instance.tearDown()
                    self._passed += 1
                    self._results.append((full_name, "PASS", ""))
                    print(f"  [PASS] {full_name}")
                except AssertionError as exc:
                    self._failed += 1
                    tb = traceback.format_exc()
                    self._results.append((full_name, "FAIL", tb))
                    print(f"  [FAIL] {full_name}: {exc}")
                except Exception as exc:
                    self._errors += 1
                    tb = traceback.format_exc()
                    self._results.append((full_name, "ERROR", tb))
                    print(f"  [ERROR] {full_name}: {exc}\n{tb}")

        total = self._passed + self._failed + self._errors
        print(f"\n测试汇总: {total} 个测试, {self._passed} 通过, {self._failed} 失败, {self._errors} 错误")
        return self._failed == 0 and self._errors == 0


# 将 AssertionError 映射为 AssertionError (Python 原生即 AssertionError)
# 注: Python 拼写为 AssertionError -> AssertionError, 实际为 AssertionError
# 这里直接使用 AssertionError 作为占位, 原生就是 AssertionError
AssertionError = AssertionError  # type: ignore[misc] # noqa: F841 - 占位确认


class TestResult:
    """测试 Result 单子。"""

    def test_ok_map(self) -> None:
        r = Ok(10).map(lambda x: x * 3)
        assert r.unwrap() == 30, "Ok.map 应正确变换值"

    def test_ok_flat_map(self) -> None:
        r = Ok(5).flat_map(lambda x: Ok(x + 1))
        assert r.unwrap() == 6, "Ok.flat_map 应正确扁平化"

    def test_ok_tap(self) -> None:
        side: list[int] = []
        Ok(7).tap(lambda x: side.append(x))
        assert side == [7], "Ok.tap 应执行副作用"

    def test_err_propagation(self) -> None:
        r = Err("错误").map(lambda x: x * 2)
        assert r.is_err(), "Err.map 应传播错误"
        assert r.unwrap_or(99) == 99, "Err.unwrap_or 应返回默认值"

    def test_unwrap_err_raises(self) -> None:
        try:
            Err("boom").unwrap()
            assert False, "应抛出异常"
        except ModuleError:
            pass


class TestOption:
    """测试 Option 单子。"""

    def test_some_map(self) -> None:
        o = Some(10).map(lambda x: x + 5)
        assert o.unwrap() == 15

    def test_nothing_map(self) -> None:
        o = Nothing.map(lambda x: x * 2)
        assert o.is_nothing()

    def test_some_filter(self) -> None:
        assert Some(10).filter(lambda x: x > 5).is_some()
        assert Some(3).filter(lambda x: x > 5).is_nothing()

    def test_unwrap_or(self) -> None:
        assert Nothing.unwrap_or(42) == 42
        assert Some(7).unwrap_or(42) == 7


class TestPipeline:
    """测试 Pipeline。"""

    def test_basic_pipe(self) -> None:
        result = Pipeline(5).pipe(lambda x: x * 2, "双倍").pipe(lambda x: x + 1, "加一").unwrap()
        assert result == 11

    def test_pipe_if(self) -> None:
        result = Pipeline(10).pipe_if(True, lambda x: x + 5, "加五").pipe_if(False, lambda x: x * 100, "跳过").unwrap()
        assert result == 15

    def test_error_recovery(self) -> None:
        result = (
            Pipeline(0)
            .pipe(lambda x: 1 // x, "除零")
            .recover(lambda e: -1)
            .unwrap()
        )
        assert result == -1

    def test_trace(self) -> None:
        p = Pipeline(1).pipe(lambda x: x, "步骤1").pipe(lambda x: x, "步骤2")
        assert len(p.trace) == 2


class TestBuilder:
    """测试 Builder。"""

    def test_basic_build(self) -> None:
        class Item:
            def __init__(self, name: str = "", price: float = 0.0) -> None:
                self.name = name
                self.price = price

        item = Builder(Item).set("name", "苹果").set("price", 5.5).build()
        assert item.name == "苹果"
        assert item.price == 5.5

    def test_set_if(self) -> None:
        class Item:
            def __init__(self, name: str = "", tag: str = "") -> None:
                self.name = name
                self.tag = tag

        item = Builder(Item).set("name", "物品").set_if(False, "tag", "VIP").build()
        assert item.tag == ""

    def test_validation(self) -> None:
        class Obj:
            def __init__(self, x: int = 0) -> None:
                self.x = x

        try:
            Builder(Obj).set("x", -1).validate(lambda d: d["x"] > 0).build()
            assert False, "应抛出 ValidationError"
        except ValidationError:
            pass


class TestQuery:
    """测试 Query。"""

    def test_where_and_order(self) -> None:
        result = Query([5, 3, 1, 4, 2]).where(lambda x: x > 2).order_by(lambda x: x).to_list()
        assert result == [3, 4, 5]

    def test_limit_offset(self) -> None:
        result = Query([1, 2, 3, 4, 5]).offset(1).limit(3).to_list()
        assert result == [2, 3, 4]

    def test_select(self) -> None:
        result = Query([1, 2, 3]).select(lambda x: x * 10).to_list()
        assert result == [10, 20, 30]

    def test_distinct(self) -> None:
        result = Query([1, 2, 2, 3, 3, 3]).distinct().to_list()
        assert result == [1, 2, 3]

    def test_aggregate(self) -> None:
        total = Query([1, 2, 3, 4]).aggregate(lambda acc, x: acc + x, 0)
        assert total == 10

    def test_sum_avg(self) -> None:
        assert Query([10, 20, 30]).sum() == 60
        assert Query([10, 20, 30]).avg() == 20.0

    def test_group_by(self) -> None:
        groups = Query([1, 2, 3, 4]).group_by(lambda x: x % 2)
        assert len(groups[0]) == 2
        assert len(groups[1]) == 2

    def test_first_empty(self) -> None:
        assert Query([]).first() is None
        assert Query([42]).first() == 42

    def test_count_exists(self) -> None:
        assert Query([1, 2]).count() == 2
        assert Query([]).exists() is False


class TestEventBus:
    """测试 EventBus。"""

    def test_on_emit(self) -> None:
        bus = EventBus()
        results: list[str] = []
        bus.on("test", lambda p: results.append(p))
        bus.emit("test", "数据1")
        bus.emit("test", "数据2")
        assert results == ["数据1", "数据2"]

    def test_once(self) -> None:
        bus = EventBus()
        results: list[int] = []
        bus.once("single", lambda p: results.append(p))
        bus.emit("single", 1)
        bus.emit("single", 2)
        assert results == [1]

    def test_off(self) -> None:
        bus = EventBus()
        results: list[int] = []
        bus.on("evt", lambda p: results.append(p))
        bus.off("evt")
        bus.emit("evt", 999)
        assert results == []

    def test_multi_handler(self) -> None:
        bus = EventBus()
        r1: list[int] = []
        r2: list[int] = []
        bus.on("multi", lambda p: r1.append(p))
        bus.on("multi", lambda p: r2.append(p))
        bus.emit("multi", 42)
        assert r1 == [42] and r2 == [42]


class TestStateMachine:
    """测试 StateMachine。"""

    def test_basic_transition(self) -> None:
        sm = StateMachine("idle")
        sm.add_transition("idle", "start", "running")
        sm.add_transition("running", "stop", "idle")
        sm.trigger("start")
        assert sm.current == "running"
        sm.trigger("stop")
        assert sm.current == "idle"

    def test_illegal_transition(self) -> None:
        sm = StateMachine("idle")
        sm.add_transition("idle", "start", "running")
        try:
            sm.trigger("stop")
            assert False, "应抛出 StateTransitionError"
        except StateTransitionError:
            pass

    def test_callbacks(self) -> None:
        log: list[str] = []
        sm = StateMachine("a")
        sm.add_transition("a", "go", "b")
        sm.on_exit("a", lambda: log.append("exit_a"))
        sm.on_enter("b", lambda: log.append("enter_b"))
        sm.on_transition(lambda f, t, to: log.append(f"trans_{f}_{t}_{to}"))
        sm.trigger("go")
        assert "exit_a" in log
        assert "enter_b" in log
        assert "trans_a_go_b" in log

    def test_history(self) -> None:
        sm = StateMachine("s1")
        sm.add_transition("s1", "next", "s2")
        sm.add_transition("s2", "next", "s3")
        sm.trigger("next").trigger("next")
        assert sm.history == ["s1", "s2", "s3"]

    def test_can_trigger(self) -> None:
        sm = StateMachine("idle")
        sm.add_transition("idle", "go", "active")
        assert sm.can_trigger("go") is True
        assert sm.can_trigger("fly") is False


class TestRegistry:
    """测试 Registry。"""

    def test_register_and_get(self) -> None:
        reg: Registry[Any] = Registry()

        @reg.register("fmt_json")
        class JsonFmt:
            def format(self, s: str) -> str:
                return f'{{"v":"{s}"}}'

        assert reg.has("fmt_json")
        cls = reg.get("fmt_json")
        assert cls().format("hi") == '{"v":"hi"}'

    def test_list_names(self) -> None:
        reg: Registry[Any] = Registry()
        reg.register_instance("a", 1)
        reg.register_instance("b", 2)
        assert sorted(reg.list_names()) == ["a", "b"]

    def test_not_found(self) -> None:
        reg: Registry[Any] = Registry()
        try:
            reg.get("nonexistent")
            assert False
        except EntityNotFoundError:
            pass


class TestConfig:
    """测试 Config。"""

    def test_default_values(self) -> None:
        c = Config()
        assert c.chunk_size == WSS_CHUNK_SIZE
        assert c.log_level == "INFO"

    def test_override(self) -> None:
        c = Config().override(log_level="DEBUG", max_workers=8)
        assert c.log_level == "DEBUG"
        assert c.max_workers == 8

    def test_from_dict(self) -> None:
        c = Config.from_dict({"log_level": "WARNING", "extra_ignored": True})
        assert c.log_level == "WARNING"

    def test_validate_ok(self) -> None:
        Config().validate()  # 不应抛出异常

    def test_validate_bad_chunk(self) -> None:
        try:
            Config(chunk_size=0).validate()
            assert False
        except ConfigurationError:
            pass

    def test_to_dict(self) -> None:
        d = Config().to_dict()
        assert "chunk_size" in d


class TestContainer:
    """测试 Container。"""

    def test_instance(self) -> None:
        c = Container().instance(str, "hello")
        assert c.resolve(str) == "hello"

    def test_singleton(self) -> None:
        c = Container().singleton("svc", lambda c: {"created": time.monotonic()})
        r1 = c.resolve("svc")
        r2 = c.resolve("svc")
        assert r1 is r2

    def test_factory(self) -> None:
        c = Container().factory("new", lambda c: {"ts": time.monotonic()})
        r1 = c.resolve("new")
        time.sleep(0.001)
        r2 = c.resolve("new")
        assert r1 is not r2

    def test_not_registered(self) -> None:
        try:
            Container().resolve("missing")
            assert False
        except ConfigurationError:
            pass


class TestDecorators:
    """测试装饰器。"""

    def test_validate_args(self) -> None:
        @validate_args(x=lambda v: v > 0)
        def fn(x: int) -> int:
            return x

        assert fn(5) == 5
        try:
            fn(-1)
            assert False
        except ValidationError:
            pass

    def test_retry(self) -> None:
        counter = {"n": 0}

        @retry(max_attempts=3, delay=0.001, backoff=1.0)
        def flaky() -> str:
            counter["n"] += 1
            if counter["n"] < 3:
                raise ValueError("暂时失败")
            return "ok"

        counter["n"] = 0
        assert flaky() == "ok"

    def test_timed(self) -> None:
        @timed
        def work() -> int:
            return 42

        assert work() == 42

    def test_cached(self) -> None:
        counter = {"n": 0}

        @cached(maxsize=5, ttl_seconds=10)
        def compute(x: int) -> int:
            counter["n"] += 1
            return x * x

        counter["n"] = 0
        assert compute(3) == 9
        assert compute(3) == 9
        assert counter["n"] == 1  # 只计算了一次

    def test_contract(self) -> None:
        @contract(pre=lambda x: x >= 0, post=lambda r: r >= 0)
        def safe_sqrt(x: float) -> float:
            return x ** 0.5

        assert safe_sqrt(4.0) == 2.0
        try:
            safe_sqrt(-1.0)
            assert False
        except BusinessRuleError:
            pass

    def test_guard_none(self) -> None:
        @guard_none("name")
        def greet(name: str) -> str:
            return f"你好,{name}"

        assert greet("世界") == "你好,世界"
        try:
            greet(None)  # type: ignore[arg-type]
            assert False
        except ValidationError:
            pass

    def test_safe_execute(self) -> None:
        @safe_execute(default=-1)
        def risky(x: int) -> int:
            return 10 // x

        assert risky(0) == -1
        assert risky(5) == 2

    def test_coerce_types(self) -> None:
        @coerce_types(x=int, y=float)
        def add(x: int, y: float) -> float:
            return x + y

        assert add("3", "4.5") == 7.5

    def test_immutable(self) -> None:
        @immutable
        class Pt:
            def __init__(self, x: int) -> None:
                self.x = x

        p = Pt(10)
        assert p.x == 10
        try:
            p.x = 20  # type: ignore[misc]
            assert False
        except AttributeError:
            pass

    def test_deprecated(self) -> None:
        @deprecated("旧接口", "2.0")
        def old() -> str:
            return "旧"

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            assert old() == "旧"
            assert len(w) >= 1


class TestDomainObjects:
    """测试领域对象。"""

    def test_file_hash_creation(self) -> None:
        fh = FileHash(md5="abc123", sha1="def456")
        assert fh.md5 == "abc123"

    def test_file_hash_immutable(self) -> None:
        fh = FileHash(md5="a", sha1="b")
        try:
            fh.md5 = "c"  # type: ignore[misc]
            assert False
        except dataclasses.FrozenInstanceError:
            pass

    def test_file_hash_validation(self) -> None:
        try:
            FileHash(md5="", sha1="b")
            assert False
        except ValidationError:
            pass

    def test_file_record_lifecycle(self) -> None:
        fr = FileRecord(name="doc.pdf", size=1024)
        assert fr.status == "pending"
        fr.mark_uploaded()
        assert fr.status == "uploaded"

    def test_transfer_task(self) -> None:
        tt = TransferTask(direction="upload")
        fr = FileRecord(name="a.txt", size=10)
        tt.add_file(fr)
        assert len(tt.files) == 1
        assert len(tt.events) == 1

    def test_transfer_task_validation(self) -> None:
        try:
            TransferTask(direction="invalid")
            assert False
        except ValidationError:
            pass


class TestSerialization:
    """测试序列化往返。"""

    def test_file_hash_roundtrip(self) -> None:
        original = FileHash(md5="abc", sha1="def")
        restored = FileHash.from_dict(original.to_dict())
        assert restored == original

    def test_file_hash_json_roundtrip(self) -> None:
        original = FileHash(md5="md5val", sha1="sha1val")
        restored = FileHash.from_json(original.to_json())
        assert restored == original

    def test_file_record_roundtrip(self) -> None:
        original = FileRecord(name="test.bin", size=999, hash_info=FileHash(md5="m", sha1="s"))
        d = original.to_dict()
        restored = FileRecord.from_dict(d)
        assert restored.name == original.name
        assert restored.size == original.size
        assert restored.hash_info == original.hash_info

    def test_transfer_info_roundtrip(self) -> None:
        original = TransferInfo(tid="t1", bid="b1", ufileid="u1", token="tok")
        restored = TransferInfo.from_json(original.to_json())
        assert restored == original


class TestRepository:
    """测试仓储 CRUD。"""

    def test_save_and_find(self) -> None:
        repo = InMemoryFileRecordRepository()
        fr = FileRecord(name="f.txt", size=50)
        repo.save(fr)
        found = repo.find_by_id(fr.id)
        assert found is not None
        assert found.name == "f.txt"

    def test_find_all(self) -> None:
        repo = InMemoryFileRecordRepository()
        repo.save(FileRecord(name="a", size=1))
        repo.save(FileRecord(name="b", size=2))
        assert len(repo.find_all()) == 2

    def test_delete(self) -> None:
        repo = InMemoryFileRecordRepository()
        fr = FileRecord(name="x", size=10)
        repo.save(fr)
        assert repo.delete(fr.id) is True
        assert repo.exists(fr.id) is False
        assert repo.delete("nonexistent") is False

    def test_update(self) -> None:
        repo = InMemoryFileRecordRepository()
        fr = FileRecord(name="orig", size=100)
        repo.save(fr)
        fr.mark_uploaded()
        repo.save(fr)
        found = repo.find_by_id(fr.id)
        assert found is not None and found.status == "uploaded"


class TestSpecifications:
    """测试规约模式。"""

    def test_file_size_spec(self) -> None:
        spec = FileSizeSpec(1000)
        assert spec.is_satisfied_by(FileRecord(name="s.txt", size=500)) is True
        assert spec.is_satisfied_by(FileRecord(name="b.txt", size=2000)) is False

    def test_and_spec(self) -> None:
        small = FileSizeSpec(1000)
        txt = FileNamePatternSpec(r".*\.txt$")
        combined = small & txt
        assert combined.is_satisfied_by(FileRecord(name="a.txt", size=100)) is True
        assert combined.is_satisfied_by(FileRecord(name="a.bin", size=100)) is False

    def test_or_spec(self) -> None:
        small = FileSizeSpec(100)
        txt = FileNamePatternSpec(r".*\.txt$")
        combined = small | txt
        assert combined.is_satisfied_by(FileRecord(name="a.bin", size=50)) is True
        assert combined.is_satisfied_by(FileRecord(name="a.txt", size=9999)) is True

    def test_not_spec(self) -> None:
        small = FileSizeSpec(100)
        big = ~small
        assert big.is_satisfied_by(FileRecord(name="x", size=200)) is True
        assert big.is_satisfied_by(FileRecord(name="x", size=50)) is False


class TestExceptions:
    """测试异常体系。"""

    def test_module_error_structure(self) -> None:
        e = ModuleError("测试", code="T001", context={"k": "v"})
        assert e.message == "测试"
        assert e.code == "T001"
        assert e.context == {"k": "v"}

    def test_validation_error(self) -> None:
        e = ValidationError("校验失败", field="email", value="bad", reason="格式错误")
        assert e.field == "email"
        assert e.reason == "格式错误"
        assert "email" in e.context.get("field", "")

    def test_exception_chain(self) -> None:
        try:
            try:
                raise ValueError("原始错误")
            except ValueError as ve:
                raise DomainError("领域错误") from ve
        except DomainError as de:
            assert de.__cause__ is not None
            assert isinstance(de.__cause__, ValueError)


def _get_all_test_classes() -> list[type]:
    """获取所有测试类。

    Returns:
        测试类列表。
    """
    return [
        TestResult,
        TestOption,
        TestPipeline,
        TestBuilder,
        TestQuery,
        TestEventBus,
        TestStateMachine,
        TestRegistry,
        TestConfig,
        TestContainer,
        TestDecorators,
        TestDomainObjects,
        TestSerialization,
        TestRepository,
        TestSpecifications,
        TestExceptions,
    ]


def _run_tests() -> bool:
    """执行全部内嵌测试,返回是否全部通过。

    Returns:
        全部通过返回 True。
    """
    print("=" * 60)
    print("运行内嵌测试")
    print("=" * 60)
    runner = _TestRunner()
    return runner.run_all(_get_all_test_classes())


# ═══════════════════════════════════════════════════════════════
# 区域 21: 演示场景构造
# ═══════════════════════════════════════════════════════════════

def _run_demo() -> None:
    """完整功能演示,覆盖 22 个方面,全部真实执行。"""
    sep = lambda title: print(f"\n{'='*60}\n  {title}\n{'='*60}")

    # 1. 日志系统初始化
    sep("1. 日志系统初始化")
    setup_logging(logging.DEBUG)
    _logger.info("日志系统已初始化为 DEBUG 级别")
    _logger.debug("这是一条 DEBUG 级别消息")
    _logger.warning("这是一条 WARNING 级别消息")
    print("日志系统初始化完成")

    # 2. 配置对象创建/读取/环境变量覆盖/CLI覆盖
    sep("2. 配置对象")
    cfg = Config()
    print(f"默认配置: {cfg.to_dict()}")
    cfg2 = cfg.override(log_level="WARNING", max_workers=8)
    print(f"覆盖后配置: log_level={cfg2.log_level}, max_workers={cfg2.max_workers}")
    cfg3 = Config.from_env(prefix="WSS_")
    print(f"从环境变量加载: {cfg3.to_dict()}")
    cfg.validate()
    print("配置校验通过")

    # 3. 依赖注入容器组装
    sep("3. 依赖注入容器")
    container = create_container(cfg)
    resolved_cfg = container.resolve(Config)
    print(f"从容器解析 Config: chunk_size={resolved_cfg.chunk_size}")
    repo = container.resolve(InMemoryFileRecordRepository)
    print(f"从容器解析仓储: {type(repo).__name__}")
    bus = container.resolve(EventBus)
    print(f"从容器解析事件总线: {type(bus).__name__}")

    # 4. 值对象创建与不可变验证
    sep("4. 值对象 (FileHash)")
    fh = FileHash(md5="d41d8cd98f00b204e9800998ecf8427e", sha1="da39a3ee5e6b4b0d3255bfef95601890afd80709")
    print(f"FileHash: md5={fh.md5[:16]}..., sha1={fh.sha1[:16]}...")
    try:
        fh.md5 = "changed"  # type: ignore[misc]
    except (dataclasses.FrozenInstanceError, AttributeError) as e:
        print(f"不可变验证: 尝试修改被阻止 -> {type(e).__name__}")

    # 5. 实体创建与业务方法调用
    sep("5. 实体 (FileRecord)")
    fr = FileRecord(name="report.pdf", size=1048576, hash_info=fh)
    print(f"文件记录: name={fr.name}, size={format_file_size(fr.size)}, status={fr.status}")
    fr.mark_uploaded()
    print(f"标记上传后: status={fr.status}")

    # 6. 聚合根行为与不变量维护
    sep("6. 聚合根 (TransferTask)")
    task = TransferTask(direction="upload")
    task.add_file(FileRecord(name="file1.txt", size=100))
    task.add_file(FileRecord(name="file2.txt", size=200))
    print(f"任务文件数: {len(task.files)}, 事件数: {len(task.events)}")
    task.complete()
    print(f"任务完成后文件状态: {[f.status for f in task.files]}")
    print(f"最后事件: {task.events[-1]['type']}")

    # 7. Builder 链式构建对象
    sep("7. Builder")

    class Product:
        def __init__(self, name: str = "", price: float = 0.0, category: str = "") -> None:
            self.name = name
            self.price = price
            self.category = category

    product = (
        Builder(Product)
        .set("name", "高级键盘")
        .set("price", 299.99)
        .set_if(True, "category", "电子产品")
        .validate(lambda d: d.get("price", 0) > 0)
        .build()
    )
    print(f"构建产品: name={product.name}, price={product.price}, category={product.category}")

    # 8. Pipeline 链式数据处理
    sep("8. Pipeline")
    recorded: list[Any] = []
    result = (
        Pipeline(100)
        .pipe(lambda x: x * 2, "乘二")
        .pipe_if(True, lambda x: x + 50, "加五十")
        .pipe_if(False, lambda x: x * 0, "跳过归零")
        .tap(lambda x: recorded.append(x))
        .pipe(lambda x: x // 3, "除三")
        .unwrap()
    )
    print(f"Pipeline 结果: {result}")
    print(f"Pipeline 跟踪: {Pipeline(100).pipe(lambda x: x*2, '乘二').pipe(lambda x: x+50, '加').trace}")
    print(f"tap 记录的中间值: {recorded}")

    # 带恢复的 Pipeline
    recovered = (
        Pipeline(0)
        .pipe(lambda x: 10 // x, "除零会失败")
        .recover(lambda e: -999)
        .pipe(lambda x: x + 1, "加一")
        .unwrap()
    )
    print(f"恢复后的 Pipeline 结果: {recovered}")

    # 9. Result 成功链
    sep("9. Result 成功链")
    ok_result = (
        Ok(10)
        .map(lambda x: x * 3)
        .flat_map(lambda x: Ok(x + 7))
        .tap(lambda x: print(f"  tap 观察值: {x}"))
        .unwrap()
    )
    print(f"Ok 链最终结果: {ok_result}")

    # 10. Result 失败链
    sep("10. Result 失败链")
    err_result = (
        Err("输入无效")
        .map(lambda x: x * 2)
        .flat_map(lambda x: Ok(x))
    )
    print(f"Err 传播: is_err={err_result.is_err()}")
    print(f"unwrap_or 默认值: {err_result.unwrap_or(-1)}")

    # 11. Option 使用
    sep("11. Option (Some/Nothing)")
    some_val = Some(42).map(lambda x: x * 2).filter(lambda x: x > 50).unwrap()
    print(f"Some(42).map(*2).filter(>50): {some_val}")
    nothing_val = Nothing.map(lambda x: x + 1).unwrap_or(0)
    print(f"Nothing.map(+1).unwrap_or(0): {nothing_val}")
    filtered_away = Some(3).filter(lambda x: x > 10).unwrap_or(-1)
    print(f"Some(3).filter(>10).unwrap_or(-1): {filtered_away}")

    # 12. Query 内存集合查询
    sep("12. Query 集合查询")
    data = [
        {"name": "张三", "age": 30, "dept": "工程"},
        {"name": "李四", "age": 25, "dept": "设计"},
        {"name": "王五", "age": 35, "dept": "工程"},
        {"name": "赵六", "age": 28, "dept": "设计"},
        {"name": "孙七", "age": 32, "dept": "工程"},
    ]
    q_result = (
        Query(data)
        .where(lambda p: p["age"] >= 28)
        .order_by(lambda p: p["age"])
        .select(lambda p: f"{p['name']}({p['age']})")
        .to_list()
    )
    print(f"年龄>=28,按年龄排序: {q_result}")

    groups = Query(data).group_by(lambda p: p["dept"])
    for dept, members in groups.items():
        print(f"  部门 {dept}: {[m['name'] for m in members]}")

    avg_age = Query(data).avg(lambda p: p["age"])
    print(f"平均年龄: {avg_age}")

    total_age = Query(data).sum(lambda p: p["age"])
    print(f"年龄总和: {total_age}")

    first_eng = Query(data).where(lambda p: p["dept"] == "工程").first()
    print(f"工程部第一人: {first_eng['name'] if first_eng else 'N/A'}")

    # 13. Registry 策略注册与动态解析
    sep("13. Registry")
    fmt_reg: Registry[Any] = Registry()

    @fmt_reg.register("json")
    class JsonFormatter:
        def format(self, data: Any) -> str:
            return json.dumps(data, ensure_ascii=False)

    @fmt_reg.register("csv")
    class CsvFormatter:
        def format(self, data: list[str]) -> str:
            return ",".join(data)

    print(f"已注册格式化器: {fmt_reg.list_names()}")
    jf = fmt_reg.get("json")()
    print(f"JSON 格式化: {jf.format({'名称': '测试', '值': 42})}")
    cf = fmt_reg.get("csv")()
    print(f"CSV 格式化: {cf.format(['姓名', '年龄', '部门'])}")

    # 14. EventBus 订阅 + 发布 + 多处理器
    sep("14. EventBus")
    bus = EventBus()
    event_log: list[str] = []
    bus.on("file_uploaded", lambda p: event_log.append(f"处理器1: {p}"))
    bus.on("file_uploaded", lambda p: event_log.append(f"处理器2: {p}"))
    bus.once("file_uploaded", lambda p: event_log.append(f"一次性处理器: {p}"))
    bus.emit("file_uploaded", "report.pdf")
    bus.emit("file_uploaded", "data.csv")
    for entry in event_log:
        print(f"  {entry}")
    print(f"总事件记录数: {len(event_log)}")

    # 15. StateMachine 状态定义 + 迁移 + 回调 + 非法迁移捕获
    sep("15. StateMachine")
    sm_log: list[str] = []
    sm = (
        StateMachine("草稿")
        .add_transition("草稿", "提交", "审核中")
        .add_transition("审核中", "通过", "已发布")
        .add_transition("审核中", "驳回", "草稿")
        .add_transition("已发布", "下架", "已下架")
        .on_enter("审核中", lambda: sm_log.append("进入审核"))
        .on_exit("草稿", lambda: sm_log.append("离开草稿"))
        .on_transition(lambda f, t, to: sm_log.append(f"{f}->{to}"))
    )
    print(f"初始状态: {sm.current}")
    sm.trigger("提交")
    print(f"提交后: {sm.current}")
    sm.trigger("驳回")
    print(f"驳回后: {sm.current}")
    sm.trigger("提交").trigger("通过")
    print(f"再次提交并通过: {sm.current}")
    print(f"状态历史: {sm.history}")
    print(f"回调日志: {sm_log}")
    try:
        sm.trigger("提交")
    except StateTransitionError as e:
        print(f"非法迁移捕获: {e.message}")

    # 16. 仓储 CRUD 全流程
    sep("16. 仓储 CRUD")
    repo = InMemoryFileRecordRepository()
    f1 = FileRecord(name="alpha.txt", size=100)
    f2 = FileRecord(name="beta.doc", size=200)
    f3 = FileRecord(name="gamma.pdf", size=300)
    repo.save(f1)
    repo.save(f2)
    repo.save(f3)
    print(f"保存 3 个文件, 总数: {len(repo.find_all())}")
    found = repo.find_by_id(f2.id)
    print(f"查询 f2: {found.name if found else 'N/A'}")
    f2.mark_uploaded()
    repo.save(f2)
    updated = repo.find_by_id(f2.id)
    print(f"更新 f2 状态: {updated.status if updated else 'N/A'}")
    repo.delete(f3.id)
    print(f"删除 f3 后总数: {len(repo.find_all())}")
    print(f"f3 是否存在: {repo.exists(f3.id)}")
    all_names = [f.name for f in repo.find_all()]
    print(f"剩余文件: {all_names}")

    # 17. 应用服务/用例编排执行
    sep("17. 应用服务/用例")
    print("(用例需要网络连接到文叔叔服务器,此处演示对象创建和错误处理)")
    mock_client = WenShuShuClient.__new__(WenShuShuClient)
    mock_client._config = Config()
    mock_repo = InMemoryFileRecordRepository()
    use_case = UploadUseCase(mock_client, mock_repo)
    try:
        use_case.execute(UploadRequest(file_path="/nonexistent/file.txt"))
    except UseCaseError as e:
        print(f"用例错误捕获: [{e.code}] {e.message}")
        print(f"  上下文: {e.context}")

    # 18. 序列化往返
    sep("18. 序列化往返")
    orig_hash = FileHash(md5="abc123def456", sha1="789xyz000111")
    dict_form = orig_hash.to_dict()
    restored_hash = FileHash.from_dict(dict_form)
    print(f"FileHash dict 往返: {orig_hash == restored_hash}")
    json_form = orig_hash.to_json()
    restored_from_json = FileHash.from_json(json_form)
    print(f"FileHash JSON 往返: {orig_hash == restored_from_json}")
    print(f"JSON 内容: {json_form}")

    orig_ti = TransferInfo(tid="task123", bid="box456", ufileid="ufile789")
    ti_json = orig_ti.to_json()
    restored_ti = TransferInfo.from_json(ti_json)
    print(f"TransferInfo JSON 往返: {orig_ti == restored_ti}")

    orig_fr = FileRecord(name="测试文件.zip", size=9999, hash_info=orig_hash)
    fr_dict = orig_fr.to_dict()
    restored_fr = FileRecord.from_dict(fr_dict)
    print(f"FileRecord dict 往返: name={restored_fr.name}, size={restored_fr.size}, hash_match={restored_fr.hash_info == orig_hash}")

    # 19. 异常捕获与结构化错误信息展示
    sep("19. 异常体系展示")
    exceptions_demo = [
        ValidationError("邮箱格式错误", field="email", value="bad@", reason="缺少域名"),
        BusinessRuleError("库存不足", context={"product": "键盘", "stock": 0}),
        EntityNotFoundError("用户未找到", entity_type="User", identifier="U12345"),
        StateTransitionError("无法从已关闭状态重新打开", context={"current": "closed", "target": "open"}),
        ConfigurationError("数据库连接串未配置", context={"key": "DB_URL"}),
        ExternalServiceError("第三方API超时", context={"service": "payment", "timeout": 30}),
        UseCaseError("创建订单失败", context={"user_id": "U001", "reason": "余额不足"}),
    ]
    for exc in exceptions_demo:
        print(f"  [{exc.code}] {exc.message}")
        print(f"    上下文: {exc.context}")

    # 20. 装饰器效果演示
    sep("20. 装饰器效果")

    @timed
    def slow_add(a: int, b: int) -> int:
        """带计时的加法。"""
        time.sleep(0.01)
        return a + b

    r = slow_add(10, 20)
    print(f"@timed slow_add(10,20) = {r}")

    call_counter = {"n": 0}

    @retry(max_attempts=3, delay=0.005, backoff=1.0)
    def flaky_op() -> str:
        call_counter["n"] += 1
        if call_counter["n"] < 3:
            raise ConnectionError("连接失败")
        return "成功"

    call_counter["n"] = 0
    print(f"@retry flaky_op() = {flaky_op()}")

    @cached(maxsize=10, ttl_seconds=60)
    def expensive(n: int) -> int:
        return n * n * n

    print(f"@cached expensive(5) = {expensive(5)}")
    print(f"@cached expensive(5) 再次 = {expensive(5)} (缓存命中)")

    @validate_args(age=lambda v: 0 < v < 200)
    def create_user(name: str, age: int) -> str:
        return f"{name}({age}岁)"

    print(f"@validate_args create_user = {create_user('张三', 25)}")
    try:
        create_user("李四", -5)
    except ValidationError as e:
        print(f"@validate_args 校验拦截: {e.message}")

    @contract(pre=lambda x: x > 0, post=lambda r: len(r) > 0)
    def make_stars(x: int) -> str:
        return "*" * x

    print(f"@contract make_stars(5) = '{make_stars(5)}'")

    # 21. 资源管理演示
    sep("21. 资源管理")
    with managed_resource(lambda: io.StringIO("这是模拟的文件内容")) as f:
        content = f.read()
        print(f"managed_resource 读取内容: '{content}'")
    print("资源已自动释放(StringIO 已 close)")

    with managed_resource(lambda: {"conn": "模拟连接"}, cleanup=lambda r: print(f"  清理资源: {r}")) as res:
        print(f"使用资源: {res}")

    # 22. 规约模式组合
    sep("22. 规约模式组合")
    small_file = FileSizeSpec(1024)
    txt_file = FileNamePatternSpec(r".*\.txt$")

    # & 组合
    small_txt = small_file & txt_file
    test_files = [
        FileRecord(name="readme.txt", size=500),
        FileRecord(name="image.png", size=500),
        FileRecord(name="huge.txt", size=9999),
        FileRecord(name="tiny.bin", size=10),
    ]
    print("规约: 小于1KB 且 .txt 文件:")
    for f in test_files:
        print(f"  {f.name}({f.size}B): {small_txt.is_satisfied_by(f)}")

    # | 组合
    small_or_txt = small_file | txt_file
    print("规约: 小于1KB 或 .txt 文件:")
    for f in test_files:
        print(f"  {f.name}({f.size}B): {small_or_txt.is_satisfied_by(f)}")

    # ~ 取反
    not_txt = ~txt_file
    print("规约: 非 .txt 文件:")
    for f in test_files:
        print(f"  {f.name}: {not_txt.is_satisfied_by(f)}")

    # 复合链: (小文件 & txt) | (~txt & 小文件)  即 小文件
    complex_spec = (small_file & txt_file) | (~txt_file & small_file)
    print("复合规约 (小且txt) 或 (非txt且小) = 小文件:")
    for f in test_files:
        print(f"  {f.name}({f.size}B): {complex_spec.is_satisfied_by(f)}")

    print("\n" + "=" * 60)
    print("  全部 22 个演示方面执行完毕")
    print("=" * 60)


# ═══════════════════════════════════════════════════════════════
# 区域 22: CLI 解析 + main() + 入口
# ═══════════════════════════════════════════════════════════════

def _parse_cli_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 命令行参数列表,为 None 时使用 sys.argv。

    Returns:
        解析后的命名空间。
    """
    parser = argparse.ArgumentParser(
        prog="use_wenshushu",
        description="文叔叔(wenshushu.cn)文件传输工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            使用示例:
              python use_wenshushu.py upload "file.exe"
              python use_wenshushu.py download "https://www.wenshushu.cn/f/xxx"
              python use_wenshushu.py --test
              python use_wenshushu.py --demo
        """),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--test", action="store_true", help="仅运行内嵌测试")
    parser.add_argument("--demo", action="store_true", help="仅运行功能演示")
    parser.add_argument("--verbose", "-v", action="store_true", help="DEBUG 级别日志")
    parser.add_argument("--dry-run", action="store_true", help="解析参数但不执行")
    parser.add_argument("--config", action="append", metavar="K=V", default=[], help="覆盖配置项(可多次)")
    parser.add_argument("--log-file", metavar="PATH", help="日志输出到文件")
    parser.add_argument("command", nargs="?", choices=["upload", "u", "download", "d"], help="操作命令")
    parser.add_argument("target", nargs="?", help="文件路径(上传)或 URL(下载)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """主入口: 解析 CLI -> 初始化日志 -> 调度测试/演示/上传/下载 -> 返回退出码。

    Args:
        argv: 命令行参数列表。

    Returns:
        退出码。
    """
    args = _parse_cli_args(argv)

    # 构建配置
    config_overrides: dict[str, Any] = {}
    for kv in args.config:
        if "=" in kv:
            k, v = kv.split("=", 1)
            config_overrides[k.strip()] = v.strip()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    config_overrides.setdefault("log_level", "DEBUG" if args.verbose else "INFO")
    if args.log_file:
        config_overrides["log_file"] = args.log_file

    try:
        cfg = Config.from_env().override(**{k: v for k, v in config_overrides.items() if hasattr(Config, k)})
        cfg.validate()
    except ConfigurationError as exc:
        print(f"配置错误: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR

    setup_logging(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        log_file=cfg.log_file,
    )

    if args.dry_run:
        print("dry-run 模式: 参数解析成功,不执行任何操作")
        print(f"  命令: {args.command}")
        print(f"  目标: {args.target}")
        print(f"  配置: {cfg.to_dict()}")
        return EXIT_SUCCESS

    # 无参数时默认运行测试+演示
    run_test = args.test or (not args.command and not args.demo)
    run_demo = args.demo or (not args.command and not args.test)

    if args.test and not args.command:
        run_demo = False
    if args.demo and not args.command:
        run_test = False

    test_passed = True
    if run_test:
        test_passed = _run_tests()

    if run_demo:
        _run_demo()

    if args.command:
        if not _HAS_CRYPTO_DEPS:
            print("错误: 执行上传/下载功能需要安装依赖:", file=sys.stderr)
            print("  pip install requests base58 pycryptodomex", file=sys.stderr)
            return EXIT_CONFIG_ERROR

        if not args.target:
            print("错误: 请提供文件路径(上传)或 URL(下载)", file=sys.stderr)
            return EXIT_CONFIG_ERROR

        try:
            client = WenShuShuClient(cfg)
            if args.command in ("upload", "u"):
                if not os.path.isfile(args.target):
                    print(f"错误: 文件不存在: {args.target}", file=sys.stderr)
                    return EXIT_CONFIG_ERROR
                client.upload(args.target)
            elif args.command in ("download", "d"):
                client.download(args.target)
            return EXIT_SUCCESS
        except (ValidationError, ConfigurationError) as exc:
            print(f"参数/配置错误: {exc}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        except (ExternalServiceError, UseCaseError, DomainError) as exc:
            print(f"业务错误: {exc}", file=sys.stderr)
            traceback.print_exc()
            return EXIT_BUSINESS_ERROR
        except Exception as exc:
            print(f"未知错误: {exc}", file=sys.stderr)
            traceback.print_exc()
            return EXIT_UNKNOWN_ERROR

    if run_test and not test_passed:
        return EXIT_TEST_FAIL

    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
