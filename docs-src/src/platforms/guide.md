# 平台开发规范

> 本规范基于 Qwen 平台重构后的实际模式总结而成。所有新增平台 **必须**
> 遵循；已有平台应在下次维护时迁移到本规范。

---

## 一、目录结构

每个平台的 **顶层** 必须固定为 4 个核心文件 + 1 个账号配置文件 + 1 个
`core/` 包（``test.py`` 可选）：

```
src/platforms/{platform}/
├── __init__.py        ← 包初始化，仅导出 Adapter
├── adapter.py         ← 仅重导出 util.Adapter（不写逻辑）
├── util.py            ← 对外门面：__getattr__ 延迟导入 + 常量/工具 re-export
├── accounts.py        ← 账号配置（Account 数据类 + ACCOUNTS 列表）
├── test.py            ← 集成测试（可选）
└── core/              ← 实现细节包，对外不可直接 import
    ├── __init__.py
    └── （自由组织的若干小模块）
```

### 为什么 ``accounts.py`` 放顶层而不放 ``core/``

- **账号是部署配置，不是协议实现**：与 ``core/`` 下的 HTTP、加密、SSE
  解析等模块解耦
- **生产部署独立维护**：真实账号常需要按部署环境分支管理；放顶层让它
  可以单独被 ``.gitignore`` / 私密文件覆盖，而不影响 ``core/`` 提交流
- **导入路径稳定**：``from src.platforms.{platform}.accounts import
  ACCOUNTS`` 比深一层的 ``core.accounts`` 更直观，且暗示了 "用户可改"
  的语义
- ``core/`` 内任何模块都可以直接 import 顶层 ``accounts``，依赖方向
  不被破坏（顶层文件只可被 ``core/`` 引用，不可反过来）

### 1.1 `core/` 是 **自由的**

`core/` 内部 **不规定文件清单**。开发者按业务职责自由拆分模块；唯一
要求是 **每个文件都单一职责** 且 **遵循命名规范**（见 §2）。

参考：Qwen 平台的 `core/` 包含 30 个职责单一的模块；ChatGPT、Claude
等平台可能只需 5~10 个。**不要为了凑齐"必备文件"而创建空壳模块。**

### 1.2 顶层文件的固定语义

| 文件 | 行数典型值 | 必做 | 禁做 |
|------|-----------:|------|------|
| `__init__.py` | < 10 行 | `from .adapter import Adapter` | 写任何业务逻辑 |
| `adapter.py`  | < 15 行 | `from .util import Adapter` 再 re-export | 写任何业务逻辑 |
| `util.py`     | < 80 行 | `__getattr__` 懒加载 Adapter + re-export 常量/纯函数 | 写业务逻辑、提前 import Adapter |
| `accounts.py` | 数据驱动 | 定义 `Account` 数据类 + 顶层 `ACCOUNTS: List[Account]` | 写网络/IO 逻辑；硬编码秘钥到版本库 |
| `test.py`     | 任意 | 端到端集成测试 | 当成单元测试 |

---

## 二、文件命名规范（强制）

### 2.1 硬性规则

1. **禁止使用** `_` 和 `-` 命名文件
2. **文件名必须是纯小写英文短词**，**8 字符以内** 为佳
3. **唯一例外**：Python 强制要求的 dunder 文件（`__init__.py` 等）
4. 文件名应直接反映 **该文件的核心导出物**（类名 / 主要函数族）

### 2.2 推荐命名词典

| 职责 | 推荐文件名 | 反面教材 |
|------|-----------|---------|
| 适配器实现 | `adaptercore.py` | `adapter_impl.py` |
| HTTP 客户端 | `client.py` | `http_client.py` |
| 账号数据 | `accounts.py` | `account_data.py` |
| 常量 | `constants.py`、`endpoints.py` | `const.py`、`api_urls.py` |
| 登录鉴权 | `auth.py` | `auth_service.py` |
| 对话会话 | `chat.py` | `chat_session.py` |
| 文件上传 | `upload.py` | `upload_service.py` |
| TTS 合成 | `tts.py` | `tts_service.py` |
| 视频生成 | `video.py` | `video_service.py` |
| SSE 解析 | `sse.py` | `sse_parser.py` |
| 流处理 | `stream.py` | `stream_handler.py` |
| 请求头构造 | `headers.py` | `http_headers.py` |
| 请求体构造 | `payloads.py` | `http_payloads.py` |
| 文件对象 | `files.py` | `file_objects.py` |
| MIME 类型 | `mimes.py` | `mime_types.py` |
| 媒体落盘 | `storage.py` | `media_storage.py` |
| 代理状态 | `proxy.py` | `proxy_state.py` |
| 错误类型 | `errors.py` | `exceptions.py` |
| 持久化 | `persistence.py` | `persist_layer.py` |
| 模型解析 | `models.py` | `models_extract.py` |
| 兼容门面 | `shared.py` | `legacy.py` |

---

## 三、依赖流动（强制）

```
┌──────────────────────┐                ┌──────────────────────┐
│ 外部代码             │                │ {platform}/accounts  │  数据
└─────────┬────────────┘                │ Account / ACCOUNTS   │  配置
          ↓                              └──────────▲───────────┘
┌──────────────────────┐                            │
│ {platform}/__init__  │  只能 import: adapter.Adapter
└─────────┬────────────┘                            │
          ↓                                          │
┌──────────────────────┐                            │
│ {platform}/adapter   │  只能 import: util.Adapter
└─────────┬────────────┘                            │
          ↓                                          │
┌──────────────────────┐                            │
│ {platform}/util      │  __getattr__ 懒加载 core.adaptercore.Adapter
│                      │  直接 re-export: core.shared 中的常量/纯函数
└─────────┬────────────┘                            │
          ↓ (lazy)                                  │
┌──────────────────────┐                            │
│ core/adaptercore     │  适配器实现，调用 core/client
└─────────┬────────────┘                            │
          ↓                                          │
┌──────────────────────┐                            │
│ core/client          │  协调器，注入并调用各服务模块────────┘
└─────────┬────────────┘  (从顶层 accounts 读取账号数据)
          ↓
┌──────────────────────────────────────┐
│ core/auth, upload, tts, video, ...   │  职责单一的服务模块
└─────────┬────────────────────────────┘
          ↓
┌──────────────────────────────────────┐
│ core/sse, payloads, headers, ...     │  无副作用的纯函数模块
└──────────────────────────────────────┘
```

### 关键约束

- **`core/` 内部** 可以任意横向引用，但要避免循环 import
- **`core/` 任意模块可以 import 顶层 `accounts`**，反之 **绝对禁止**
  顶层 `accounts.py` 引用 `core/` 任何模块
- **`adapter.py` 不得直接 import `core/`**（永远通过 `util.py`）
- **`util.py` 必须用 `__getattr__` 懒加载 Adapter**，避免冷启动开销
- **底层纯函数模块**（如 `sse.py`、`payloads.py`、`lzw.py`）不得依赖
  上层服务模块

---

## 四、God-Module 防治

### 4.1 单文件硬性上限

- **文件 800 行硬上限** — 超过必须拆分
- **文件 400 行软上限** — 应当考虑拆分
- **函数 50 行推荐 / 80 行硬上限** — 推荐尽量小；超过 50 行应考虑提取；
  超过 80 行必须拆分；天然不可拆的算法函数（如完整 LZW 编码、
  解析器 dispatch 大表）允许豁免，但需在 docstring 中说明
- **嵌套 4 层硬上限** — 超过必须用 early-return 或子函数扁平化

### 4.2 拆分原则

按 **业务职责** 而非按 **代码类型** 拆分：

[OK] **正确**：`auth.py`（登录全流程） + `chat.py`（对话生命周期）
[NG] **错误**：`utils.py`（一堆杂项） + `helpers.py`（一堆杂项）

[OK] **正确**：`upload.py`（OSS 上传全流程，含 STS / PUT / 重试）
[NG] **错误**：`requests.py`（所有 HTTP 调用）

### 4.3 `shared.py` 的角色（重要）

历史上，许多平台的 `shared.py` 是一个 **God-module**（包含加密、HTTP、
SSE、payload 等所有逻辑，可达 1700+ 行）。新规范禁止此模式：

- [OK] `shared.py` **只能是薄门面**（thin facade），≤ 250 行
- [OK] 它的唯一职责是 **re-export** 各个职责单一子模块的符号
- [OK] 目的是 **向后兼容** 旧代码的 `from .shared import xxx` 写法
- [NG] **不得** 在 `shared.py` 中写任何函数体、类定义或业务逻辑
- 新平台 **不需要** `shared.py`（只在拆分历史 God-module 时引入）

---

## 五、服务模块设计（依赖注入）

### 5.1 模式

`core/client.py` 是 **协调器**（thin orchestrator），不写具体业务；
具体职责放到独立的服务模块，通过 **构造函数注入** 接收依赖。

```python
# core/upload.py
class UploadService:
    """OSS 文件上传服务。"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
    ) -> None:
        self._session = session
        self._resolve_proxy = proxy_resolver

    async def upload(self, data: bytes, filename: str, token: str,
                     user_id: str) -> Dict[str, Any]:
        ...
```

```python
# core/client.py
class Client:
    def _build_services(self, session: aiohttp.ClientSession) -> None:
        self._upload = UploadService(session, self._get_proxy_kwarg)
        self._chat   = ChatSession(session, self._get_proxy_kwarg,
                                   cookies_provider=lambda: self._cookies,
                                   fingerprint_provider=lambda: self._fp)
        self._tts    = TtsService(
            session=session,
            proxy_resolver=self._get_proxy_kwarg,
            cookies_provider=lambda: self._cookies,
            fingerprint_provider=lambda: self._fp,
            create_chat=self._chat.create,
            cleanup_chat=self._chat.cleanup,
        )
```

### 5.2 注入约定

- **`session`**：共享的 `aiohttp.ClientSession`
- **`proxy_resolver`**：返回当前应用的代理 URL 或 `None`
- **`cookies_provider` / `fingerprint_provider`**：**用 lambda 包装**，
  避免引用陈旧值（cookie 后台会被刷新）
- **跨服务协作**：用回调（如 `create_chat=self._chat.create`），
  不直接 import 兄弟服务

---

## 六、必须实现的方法

### 6.1 Adapter 子类（继承 `PlatformAdapter`）

| 方法 / 属性 | 类型 | 说明 |
|------------|------|------|
| `name` (property) | 抽象 | 平台标识名（小写，与目录名一致） |
| `init(session)` | 抽象 | 初始化——**必须立即返回**，耗时操作交后台 Task |
| `close()` | 抽象 | 关闭适配器，**取消后台任务**、释放资源 |
| `candidates()` | 抽象 | 返回当前可用候选项列表（反映实时状态） |
| `ensure_candidates(count)` | 抽象 | 确保候选项数量，返回实际数量 |
| `complete(candidate, messages, model, stream, **kw)` | 抽象 | 聊天补全，yield str 或 dict |

### 6.2 可选方法

| 方法 / 属性 | 默认行为 | 说明 |
|------------|---------|------|
| `supported_models` | `[]` | 支持的模型列表（建议合并内置+客户端+持久化）|
| `default_capabilities` | `{"chat": True}` | 平台能力字典 |
| `context_length` | `131072` | 上下文长度 |
| `set_proxy_enabled(enabled)` | no-op | 代理切换开关 |
| `is_proxy_allowed()` | `False` | 是否允许代理切换（受全局配置约束）|
| `is_proxy_enabled()` | `False` | 当前是否启用代理 |
| `fetch_remote_models()` | `[]` | 拉取远程模型列表 |
| `create_image(candidate, prompt, model, **kw)` | — | 图片生成 |
| `edit_image(candidate, image, prompt, model, **kw)` | — | 图片编辑 |
| `create_video(candidate, prompt, model, **kw)` | — | 视频生成 |
| `create_speech(candidate, input_text, model, voice, **kw)` | — | TTS 合成 |

---

## 七、初始化流程

### 7.1 非阻塞初始化（强制）

```python
class Adapter(PlatformAdapter):
    def __init__(self) -> None:
        self._client: Any = None
        self._init_task: Any = None
        self._bg_task: Any = None

    async def init(self, session: aiohttp.ClientSession) -> None:
        """立即返回；后台 Task 完成登录等耗时操作。"""
        from src.platforms.{platform}.core.client import Client  # noqa: PLC0415
        self._client = Client()
        self._init_task = asyncio.ensure_future(
            self._client.init_immediate(session)
        )
        self._bg_task = asyncio.ensure_future(
            self._client.background_setup()
        )

    async def close(self) -> None:
        for task in (self._init_task, self._bg_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        if self._client is not None:
            await self._client.close()
```

### 7.2 关键原则

1. **`init()` 必须立即返回** — 任何 I/O 都放到 `init_immediate` 之后
2. **耗时操作在后台 Task 中执行** — 登录、token 刷新、模型拉取
3. **`candidates()` 随时返回真实状态** — 即使后台任务未完成也要可用
4. **`close()` 必须取消后台 Task** — 否则会泄漏 task 引用

---

## 八、Client 协调器骨架

```python
# core/client.py
class Client:
    """{Platform} HTTP 协调器。

    职责限定为协调：账号 / 候选项 / 持久化 / 会话生命周期 /
    顶层错误处理与重试。具体业务下放给服务模块。
    """

    def __init__(self) -> None:
        self._session: Optional[aiohttp.ClientSession] = None
        self._account_states: Dict[str, Account] = {}
        self._candidates: List[Candidate] = []
        self._models: List[str] = list(MODELS)
        self._bg_tasks: List[asyncio.Task] = []
        self._closing: bool = False
        self._proxy = ProxyState()
        # 子服务在 init_immediate() 中实例化
        self._upload: Optional[UploadService] = None
        # ...

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._load_persist()
        self._rebuild_candidates()
        self._build_services(session)

    async def background_setup(self) -> None:
        await self._bg_login()
        self._bg_tasks.append(asyncio.ensure_future(self._bg_persist()))
        # ...

    async def close(self) -> None:
        self._closing = True
        for task in self._bg_tasks:
            task.cancel()
        for task in self._bg_tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._save_persist()
```

---

## 九、Candidate 构建

```python
def _rebuild_candidates(self) -> None:
    """根据当前账号状态重建候选项列表。"""
    self._candidates = [
        Candidate(
            id=make_id(self.name),
            platform=self.name,
            resource_id=acc.username[:12],
            models=list(self._models),
            context_length=acc.context_length,
            meta={
                "email": acc.username,
                "token": acc.token,
                "user_id": acc.user_id,
            },
            **CAPS,
        )
        for acc in self._account_states.values()
        if acc.is_login and acc.token
    ]
```

**规则**：
- `_rebuild_candidates` 必须是 **同步函数**（无锁、原子重建）
- 登录成功 / token 失效 / 设置变化 后立即调用
- `meta` 字段是约定数据袋，约定字段名：`token`、`user_id`、`email`

---

## 十、持久化模式

```python
# core/persistence.py
PERSIST_PATH = "persist/{platform}/usage.json"
PERSIST_INTERVAL = 60  # 秒

def load_persist(account_states, cookies, proxy) -> dict:
    """从磁盘加载状态，就地修改入参；返回最终生效的 cookies。"""
    ...

def save_persist(account_states, cookies, proxy) -> None:
    """原子写入磁盘（先 .tmp 再 os.replace）。"""
    ...
```

```python
# core/client.py
async def _bg_persist(self) -> None:
    while not self._closing:
        await asyncio.sleep(PERSIST_INTERVAL)
        if not self._closing:
            self._save_persist()
```

**规则**：
- **原子写**：先写 `<path>.tmp`，再 `os.replace`，最多重试 3 次
- **跨平台编码**：始终 `encoding="utf-8"`
- **目录懒创建**：`Path(...).parent.mkdir(parents=True, exist_ok=True)`
- **持久化字段是公开协议**：字段名变更视为破坏性变更，禁止随意改名

---

## 十一、代理切换

### 11.1 状态机模块

将代理覆盖状态独立为 `core/proxy.py`：

```python
class ProxyState:
    """三态：True=强制开启 / False=强制关闭 / None=跟随全局。"""
    def __init__(self) -> None:
        self.override: Optional[bool] = None

    def set_enabled(self, enabled: bool) -> None: ...
    def is_enabled(self) -> bool: ...
    def get_proxy_url(self) -> Optional[str]: ...
    def to_dict(self) -> dict: ...
    def load(self, override) -> None: ...
```

### 11.2 在请求中应用

```python
post_kwargs = {
    "json": payload,
    "headers": headers,
    "ssl": False,
    "timeout": aiohttp.ClientTimeout(connect=10, total=SSE_TIMEOUT),
    "proxy": self._get_proxy_kwarg(),
}
async with self._session.post(url, **post_kwargs) as resp:
    ...
```

### 11.3 配置约束（不变）

只有 `config.toml` 中 `[platforms_proxy].enabled_platforms` 列表中的
平台，`set_proxy_enabled()` 才会真正生效：

```toml
[platforms_proxy]
enabled_platforms = ["qwen"]
```

Adapter 侧的判断必须前置：

```python
def set_proxy_enabled(self, enabled: bool) -> None:
    if not self.is_proxy_allowed():
        return
    if self._client is not None:
        self._client.set_proxy_enabled(enabled)

def is_proxy_allowed(self) -> bool:
    from src.core.config import get_config  # noqa: PLC0415
    cfg = get_config()
    return self.name in cfg.platforms_proxy.enabled_platforms_set
```

---

## 十二、SSE 流处理

### 12.1 分两层

- **无状态层**：`core/sse.py` 提供 `parse_sse_event(data_str)` 和
  `parse_sse_line(data_str)`，纯函数，无任何 I/O 或累积状态
- **有状态层**：`core/stream.py` 提供 `StreamHandler` 类，封装
  `thinking_summary` 累积、`response_id` 捕获、媒体事件转 `tool_calls` 等

### 12.2 `StreamHandler` 不可复用

每次聊天请求 **必须新建实例**（含 `last_response_id`、内部 buffer、
累积计数等状态）：

```python
handler = StreamHandler(download_image=self._chat.download_image)
async with self._session.post(url, **post_kw) as resp:
    await self._raise_on_bad_response(resp, candidate)
    async for item in handler.stream(resp):
        yield item
# 流结束后才能读 handler.last_response_id（如 TTS 需要）
```

---

## 十三、Yield 协议

`complete()` 方法 yield 的数据类型：

| 类型 | 示例 | 说明 |
|------|------|------|
| `str` | `"hello"` | 文本增量 |
| `dict` | `{"thinking": "..."}` | 思考摘要增量 |
| `dict` | `{"usage": {"prompt_tokens": N, "completion_tokens": N}}` | token 用量 |
| `dict` | `{"tool_calls": [...]}` | OpenAI 兼容的工具调用 |

媒体事件（图片 / 视频 / 文档）统一映射到 `tool_calls`，函数名约定：

| 函数名 | 用途 | arguments 字段 |
|--------|------|----------------|
| `{platform}.image_gen` | 图片生成结果 | `{"url": "...", "local_path": "..."}` |
| `{platform}.video_gen` | 视频生成结果 | `{"url": "..."}` |

---

## 十四、错误处理

### 14.1 异常类型

- 平台异常 **必须有专属层级**，放在 `core/errors.py`：

  ```python
  class QwenError(Exception): ...
  class WAFBlockedError(QwenError): ...
  class TokenExpiredError(QwenError): ...
  ```

- **禁止裸 `except Exception:`** — 只捕获具体异常类型
- **禁止吞错** — 即便业务允许降级（如下载失败返回 `None`）也要
  `logger.warning(...)` 记录

### 14.2 重试策略

- 顶层 `complete()` 是重试入口，**指数退避**：`sleep(2 ** (attempt - 1))`
- 默认 `MAX_RETRIES = 3`
- **WAF 拦截** 触发重试（代理由 ProxySelector 智能选择决定）
- **Token 过期**（401 或返回体含 `Token has expired`）触发账号
  `is_login=False` + 重建候选项 + 持久化保存

---

## 十五、代码质量硬要求

### 15.1 头部规范

每个 `.py` 文件 **第一条非 docstring 语句必须是**：

```python
from __future__ import annotations
```

理由：保证 type annotations 在 Python 3.8 上以字符串形式存在，避免
3.9+ 才有的内置泛型语法（`list[str]`）破坏兼容性。

### 15.2 docstring

- **所有公开函数/方法/类** 必须有 PEP 257 docstring
- 至少包含 **Args / Returns**，有异常的必须列 **Raises**
- 纯函数 **应当** 包含 doctest 例子

### 15.3 静态约束

- **禁止 emoji**（代码或注释中皆禁）
- **禁止 `pass` 作为功能实现**（占位也禁；空协议方法用 `...`）
- **禁止硬编码**（路径、超时、URL 等必须放进 `constants.py` 或 `endpoints.py`）
- **不可变优先**：返回新对象而非修改入参
- **完整 type annotations**：所有公开 API 必须显式标注

### 15.4 跨版本 / 跨平台

- 兼容 Python **3.8 - 3.14**
- 路径用 `pathlib.Path`，原子重命名用 `os.replace`
- 文件 I/O 显式 `encoding="utf-8"`，关心换行符的场景显式 `newline=""`
- Windows 控制台编码用 `sys.stdout.reconfigure(encoding="utf-8")`

---

## 十六、关键约束清单（速查）

| 类别 | 强制约束 |
|------|---------|
| **顶层文件** | `__init__.py` / `adapter.py` / `util.py` / `accounts.py` + `core/`，缺一不可；前 3 个不写业务 |
| **`core/`** | 自由组织；按业务职责拆分，禁止 utils 类大杂烩文件 |
| **文件命名** | 纯小写英文短词；禁用 `_`、`-`；8 字符以内为佳；dunder 文件例外 |
| **代码体量** | 文件 800 行 / 函数 80 行硬上限（推荐函数 < 50）；超出必须拆分（算法可豁免并在 docstring 说明）|
| **God-module** | `shared.py` 只能是薄门面（≤ 250 行），不写业务 |
| **依赖流向** | `__init__ → adapter → util → core/adaptercore → core/client → core/服务 → core/纯函数` |
| **`util.py`** | 必须 `__getattr__` 懒加载 Adapter |
| **服务模块** | 构造函数注入依赖（session / proxy_resolver / cookies_provider 等） |
| **初始化** | `init()` 必须立即返回；耗时操作交后台 Task |
| **持久化** | 原子写（`.tmp` + `os.replace` + 3 次重试）；`encoding="utf-8"` |
| **代理** | `core/proxy.py` 状态机；Adapter 层用 `is_proxy_allowed()` 前置守卫 |
| **SSE** | 解析分两层（`sse.py` 无状态 + `stream.py` 有状态）；`StreamHandler` 单次使用 |
| **异常** | 平台异常放 `core/errors.py`；禁止裸 `except Exception` |
| **代码** | 头部 `from __future__ import annotations`；全 docstring；禁 emoji / `pass` 实现 |
| **HTTP** | `ssl=False`；共享 Session；显式 `timeout`；`proxy=self._get_proxy_kwarg()` |
| **跨平台** | 兼容 Python 3.8–3.14；`pathlib.Path`；显式编码 |

---

## 十七、参考实现

`src/platforms/qwen/` 是本规范的 **参考实现**。新平台开发可：

1. 复制 `src/platforms/qwen/` 整个目录作为模板
2. 替换 `accounts.py` 中的账号配置
3. 替换平台标识、URL、模型列表、加密逻辑
4. 删除不需要的服务模块（如平台不支持 TTS 则删 `tts.py`）
5. **保持顶层 4 核心文件 + `accounts.py` + `core/` 的结构与命名规范不变**


## 补充说明

当前项目的唯一 skill 已迁移到 `.agents/provider-guide/`，旧的 `.agents/rules/` 将废弃。
