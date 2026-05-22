# 平台开发规范

## 目录结构

每个平台必须遵循以下目录结构：

```
src/platforms/{platform_name}/
├── __init__.py              ← 包初始化（通常为空）
├── adapter.py               ← 仅重导出 adapter_impl（不写逻辑）
├── util.py                  ← 通过 __getattr__ 延迟导入 core/ 中的类
├── test.py                  ← 集成测试（可选）
└── core/
    ├── __init__.py          ← 包初始化
    ├── adapter_impl.py      ← 平台适配器实现（核心）
    ├── client.py            ← HTTP 客户端实现
    ├── accounts.py          ← 账号数据类
    ├── constants.py         ← 常量定义
    ├── shared.py            ← 共享工具函数（如适用）
    └── AGENTS.md            ← 平台特有的陷阱说明
```

## 必须实现的方法

### PlatformAdapter 子类

| 方法 | 类型 | 说明 |
|------|------|------|
| `name` (property) | 抽象 | 平台标识名（小写，与目录名一致） |
| `init(session)` | 抽象 | 初始化适配器——必须立即返回，耗时操作交后台 Task |
| `candidates()` | 抽象 | 返回当前可用候选项列表（反映实时状态） |
| `ensure_candidates(count)` | 抽象 | 确保候选项数量，返回实际数量 |
| `complete(candidate, messages, model, stream, ...)` | 抽象 | 聊天补全，yield str 或 dict |
| `close()` | 抽象 | 关闭适配器，释放资源 |

### 可选方法

| 方法 | 说明 |
|------|------|
| `supported_models` | 支持的模型列表（默认返回 []） |
| `default_capabilities` | 能力字典（默认 `{"chat": True}`） |
| `context_length` | 上下文长度（默认 128k = 131072） |
| `set_proxy_enabled(enabled, auto=False)` | 代理切换（默认无操作） |
| `is_proxy_allowed()` | 是否允许代理切换 |
| `is_proxy_enabled()` | 当前是否启用代理 |
| `fetch_remote_models()` | 拉取远程模型列表 |
| `create_image()` | 图片生成 |
| `create_speech()` | TTS 语音合成 |
| `create_video()` | 视频生成 |

## 初始化流程

```python
class MyAdapter(PlatformAdapter):
    async def init(self, session: aiohttp.ClientSession) -> None:
        # 1. 创建客户端（立即返回）
        self._client = MyClient()
        await self._client.init_immediate(session)

        # 2. 启动后台任务（登录、模型刷新等）
        self._bg_task = asyncio.ensure_future(self._background_setup())
```

### 关键原则

1. **`init()` 必须立即返回** — 不得阻塞
2. **耗时操作在后台 Task 中执行** — 登录、token 刷新、模型拉取
3. **`candidates()` 随时返回真实状态** — 即使后台任务未完成

## Client 设计模式

```python
class MyClient:
    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._candidates: List[Candidate] = []

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        # 构建候选项（从配置/缓存）
        self._rebuild_candidates()

    async def complete(self, candidate, messages, model, stream, ...) -> AsyncGenerator:
        token = candidate.meta.get("token", "")
        # 使用 self._session 发起请求
        async with self._session.post(url, ...) as resp:
            # 解析响应，yield 文本或 dict
            yield chunk

    # 代理切换支持（仅在平台被允许时有效）
    _proxy_override: Optional[bool] = None

    def set_proxy_enabled(self, enabled: bool) -> None:
        self._proxy_override = enabled if enabled else False

    def is_proxy_enabled(self) -> bool:
        return bool(self._proxy_override)

    def _get_proxy_kwarg(self) -> Optional[str]:
        from src.core.proxy import get_proxy_server
        if self._proxy_override is True:
            return get_proxy_server()
        elif self._proxy_override is False:
            return None
        return None
```

### 请求中应用代理

```python
post_kwargs = {"json": payload, "headers": headers, "ssl": False}
if self._proxy_override is not None:
    post_kwargs["proxy"] = self._get_proxy_kwarg()

async with self._session.post(url, **post_kwargs) as resp:
    ...
```

## Candidate 构建

```python
def _rebuild_candidates(self) -> None:
    self._candidates = []
    for account in self._accounts:
        if not account.token:
            continue
        cand = Candidate(
            id=make_id(self.name),
            platform=self.name,
            resource_id=account.username,
            chat=True,
            models=self._models,
            meta={"token": account.token, "user_id": account.user_id},
        )
        self._candidates.append(cand)
```

## 持久化模式

```python
PERSIST_PATH = "persist/{platform}/usage.json"
PERSIST_INTERVAL = 60  # 秒

def _load_persist(self) -> None:
    if not os.path.exists(PERSIST_PATH):
        return
    data = json.loads(Path(PERSIST_PATH).read_text(encoding="utf-8"))
    # 恢复状态...

def _save_persist(self) -> None:
    Path(PERSIST_PATH).parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps({...}, indent=2, ensure_ascii=False)
    # 原子写入...

async def _bg_persist(self) -> None:
    while not self._closing:
        await asyncio.sleep(PERSIST_INTERVAL)
        self._save_persist()
```

## Yield 协议

`complete()` 方法 yield 的数据类型：

| 类型 | 说明 |
|------|------|
| `str` | 文本增量 |
| `dict` | `{"thinking": "..."}` 思考内容 |
| `dict` | `{"usage": {"prompt_tokens": N, "completion_tokens": N}}` 用量 |
| `dict` | `{"tool_calls": [...]}` 工具调用 |

## 代理切换限制

**只有 `config.toml` 中 `[platforms_proxy].enabled_platforms` 列表中的平台，`set_proxy_enabled()` 才有效。**

不在列表中的平台，无论怎么调用 `set_proxy_enabled()` 都不会生效。

配置示例：
```toml
[platforms_proxy]
enabled_platforms = ["qwen"]  # 只有 qwen 平台的代理切换有效
```

## 注意事项

1. **`adapter.py` 不写逻辑** — 仅重导出 `adapter_impl.py`
2. **`util.py` 使用 `__getattr__` 延迟导入** — 避免循环依赖
3. **`shared.py` 可能很大** — Qwen 的 shared.py 包含所有核心逻辑
4. **SSL 全局禁用** — 所有请求 `ssl=False`
5. **共享 Session** — 所有客户端使用 `main.py` 创建的单一 Session
