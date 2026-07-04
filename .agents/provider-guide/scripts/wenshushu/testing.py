# -*- coding: utf-8 -*-
"""测试框架与所有内嵌测试类。

包含 ``_TestRunner`` 自动发现运行器,以及覆盖 Result/Option/Pipeline/
Builder/Query/EventBus/StateMachine/Registry/Config/Container/装饰器/
领域对象/序列化/仓储/规约/异常 共 16 个测试类。
"""
from __future__ import annotations

import dataclasses
import time
import traceback
import warnings
from typing import Any

from .container import WSS_CHUNK_SIZE, Config, Container
from .domain import (
    FileHash,
    FileNamePatternSpec,
    FileRecord,
    FileSizeSpec,
    TransferInfo,
    TransferTask,
)
from .exceptions import (
    BusinessRuleError,
    ConfigurationError,
    DomainError,
    EntityNotFoundError,
    ModuleError,
    StateTransitionError,
    ValidationError,
)
from .fp import (
    Builder,
    Err,
    EventBus,
    Nothing,
    Ok,
    Pipeline,
    Query,
    Registry,
    Some,
    StateMachine,
)
from .repositories import InMemoryFileRecordRepository
from .utils import (
    cached,
    coerce_types,
    contract,
    deprecated,
    guard_none,
    immutable,
    retry,
    safe_execute,
    timed,
    validate_args,
)


# ===========================================================================
# 测试运行器
# ===========================================================================

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


# ===========================================================================
# 测试类
# ===========================================================================

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


# ===========================================================================
# 辅助函数
# ===========================================================================

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
