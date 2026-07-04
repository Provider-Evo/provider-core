# -*- coding: utf-8 -*-
"""函数式编程构造模块。

提供 Result、Option、Pipeline、Builder、Query、EventBus、Registry、StateMachine
等函数式编程构造,用于构建可组合、可预测的业务逻辑。
"""
from __future__ import annotations

import threading
from typing import Any, Callable, Generic, Iterator, TypeVar

from .exceptions import (
    EntityNotFoundError,
    ModuleError,
    StateTransitionError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# 类型变量
# ---------------------------------------------------------------------------
T = TypeVar("T")
U = TypeVar("U")


# ===========================================================================
# Result 单子
# ===========================================================================

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


# ===========================================================================
# Option 单子
# ===========================================================================

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


# ===========================================================================
# Pipeline 数据处理管道
# ===========================================================================

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


# ===========================================================================
# Builder 通用对象构建器
# ===========================================================================

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


# ===========================================================================
# Query 内存集合查询引擎
# ===========================================================================

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


# ===========================================================================
# EventBus 事件总线
# ===========================================================================

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


# ===========================================================================
# Registry 策略/插件注册表
# ===========================================================================

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


# ===========================================================================
# StateMachine 有限状态机
# ===========================================================================

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
