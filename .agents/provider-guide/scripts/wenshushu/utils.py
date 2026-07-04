# -*- coding: utf-8 -*-
"""通用工具函数与装饰器模块。

包含哈希摘要、格式化、资源管理等工具函数,以及
validate_args、retry、timed、cached、singleton、deprecated、
immutable、contract、trace_calls、guard_none、safe_execute、
coerce_types 等装饰器。
"""
from __future__ import annotations

import contextlib
import functools
import hashlib
import inspect
import logging
import threading
import time
import uuid
import warnings
from typing import Any, Callable, Iterator, TypeVar

from .exceptions import BusinessRuleError, ValidationError

# ---------------------------------------------------------------------------
# 类型变量
# ---------------------------------------------------------------------------
T = TypeVar("T")

# ---------------------------------------------------------------------------
# 模块级 logger（与 legacy 保持一致）
# ---------------------------------------------------------------------------
_logger = logging.getLogger("use_wenshushu")

# ---------------------------------------------------------------------------
# 默认常量（与 legacy 保持一致）
# ---------------------------------------------------------------------------
DEFAULT_MAX_RETRY = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_RETRY_BACKOFF = 2.0
DEFAULT_CACHE_MAXSIZE = 128
DEFAULT_CACHE_TTL = 300


# ===========================================================================
# 哈希与格式化工具
# ===========================================================================

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
def managed_resource(
    factory: Callable[[], T],
    cleanup: Callable[[T], None] | None = None,
) -> Iterator[T]:
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


# ===========================================================================
# 装饰器
# ===========================================================================

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
