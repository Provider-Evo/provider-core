# Provider-V2 架构概览

## 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    Client (浏览器/SDK)                │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP (OpenAI / Anthropic 格式)
                       ▼
┌─────────────────────────────────────────────────────┐
│                   aiohttp.web 服务器                  │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │ OpenAI 路由   │  │ Anthropic 路由│                 │
│  │ (openai.py)  │  │ (anthropic.py)│                 │
│  └──────┬───────┘  └──────┬───────┘                 │
└─────────┼─────────────────┼─────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────┐
│                  Gateway (gateway.py)                │
│  · 候选项等待 (_wait_for_candidates)                 │
│  · TAS 选择器选择候选项                               │
│  · 单候选项执行 / 多候选项竞速                         │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Registry (registry.py)              │
│  · 平台适配器注册表                                    │
│  · get_candidates(model) → List[Candidate]           │
│  · adapter_for(candidate) → PlatformAdapter          │
└──────────────────────┬──────────────────────────────┘
                       │
           ┌───────────┼───────────┐
           ▼           ▼           ▼
     ┌──────────┐ ┌──────────┐ ┌──────────┐
     │  Qwen    │ │ DeepSeek │ │  Ollama  │
     │ Adapter  │ │ Adapter  │ │ Adapter  │
     └──────────┘ └──────────┘ └──────────┘
```

## Runner-Worker 双进程架构

```
main.py
  ├── Runner 进程（父进程）
  │   └── 监控 Worker 子进程
  │       · exit code 42 → 自动重启
  │       · Ctrl+C → 终止 Worker
  │       · 最多 50 次重启
  │
  └── Worker 进程（子进程，WORKER_PROCESS=1）
      └── asyncio 事件循环
          · aiohttp.web 服务器
          · 所有平台适配器
          · 配置热重载
          · 文件监视
```

## 核心模块

> **v2.2.65 重构**：`src/core/` 下的模块已重构为 `echotools` 包的薄包装层。
> 核心逻辑（配置管理、插件注册、函数调用解析、代理、进程管理等）统一迁移至 `echotools>=1.0.1`。
> `src/core/` 保留原始 API 接口，内部委托给 `echotools` 对应组件。

| 模块 | 路径 | 职责 | echotools 组件 |
|------|------|------|----------------|
| Server | `src/core/server.py` | aiohttp.web 应用创建、路由注册 | echotools Server |
| Registry | `src/core/dispatch/registry.py` | 平台适配器发现、注册、候选项查询 | echotools PluginRegistry |
| Gateway | `src/core/dispatch/gateway.py` | 请求分发、候选项选择、竞速执行 | echotools Gateway |
| Selector | `src/core/dispatch/selector.py` | TAS 算法选择最优候选项 | echotools Selector |
| Proxy | `src/core/server/proxy.py` | 代理支持（HTTP/HTTPS/SOCKS5）、环境变量检测 | echotools ProxyManager |
| Config | `src/core/config/` | TOML 配置加载、热重载 | echotools ConfigCenter |
| FnCall | `src/core/fncall/` | 工具调用解析、协议、注入 | echotools fncall |
| ModelsCache | `src/core/models_cache.py` | 模型列表缓存 | echotools ListCache |
| Tools | `src/core/tools.py` | 工具调用处理 | echotools Tools |

## 平台适配器接口

每个平台必须实现 `PlatformAdapter` 抽象基类：

```python
class PlatformAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    async def init(self, session: aiohttp.ClientSession) -> None: ...
    async def candidates(self) -> List[Candidate]: ...
    async def ensure_candidates(self, count: int) -> int: ...
    async def complete(self, candidate, messages, model, stream, ...) -> AsyncGenerator: ...
    async def close(self) -> None: ...

    # 可选方法
    def set_proxy_enabled(self, enabled: bool) -> None: ...
    def is_proxy_allowed(self) -> bool: ...
    def is_proxy_enabled(self) -> bool: ...
    def context_length(self) -> Optional[int]: ...  # 默认 128k
```

## 数据流

1. 客户端发送 OpenAI/Anthropic 格式请求
2. 路由层转换为内部格式（messages, model, tools, stream）
3. Gateway 通过 Registry 获取匹配 model 的候选项
4. Selector 按 TAS 算法选择最优候选项
5. 通过 Adapter.complete() 执行请求，yield 文本/结构化数据
6. 路由层将结果转换为客户端期望的格式返回

## 代理系统

代理支持多级控制：

| 层级 | 说明 |
|------|------|
| 全局代理 | `config.toml [proxy]` 或环境变量 `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` |
| 平台切换 | `adapter.set_proxy_enabled(bool)` — 仅对 `platforms_proxy.enabled_platforms` 中的平台有效 |
| Qwen 智能 | ProxySelector 根据历史成功率、延迟等指标自动选择代理或直连 |

详见 `proxy.md`。
