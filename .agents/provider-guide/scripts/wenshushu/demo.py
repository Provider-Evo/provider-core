# -*- coding: utf-8 -*-
"""演示场景构造模块。

提供 ``_run_demo`` 函数,覆盖 22 个方面的完整功能演示,
包括日志、配置、容器、值对象、实体、聚合根、Builder、Pipeline、
Result/Option、Query、Registry、EventBus、StateMachine、仓储、
用例、序列化、异常、装饰器、资源管理、规约模式等。
"""
from __future__ import annotations

import dataclasses
import io
import json
import logging
import time
from typing import Any

from .bootstrap import create_container
from .client import WenShuShuClient
from .container import Config
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
    EntityNotFoundError,
    ExternalServiceError,
    StateTransitionError,
    UseCaseError,
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
from .logging_setup import _logger, setup_logging
from .repositories import InMemoryFileRecordRepository
from .use_cases import UploadRequest, UploadUseCase
from .utils import (
    cached,
    contract,
    format_file_size,
    managed_resource,
    retry,
    timed,
    validate_args,
)


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
