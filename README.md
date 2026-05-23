# Provider-V2

> 高性能 AI 模型代理网关，提供 OpenAI 兼容 API，支持多平台接入与智能请求分发。

## 分支说明

| 分支 | 定位 | 说明 |
|------|------|------|
| **main** | 稳定版本 | 平台白名单 — cerebras, chatmoe, codebuddy, cursor, deepseek, nvidia, qwen, openrouter, chutes |
| **dev** | 活跃开发 | 包含当前 `src/platforms/` 下的全部平台（含实验/新增平台） |
| **classical** | 经典架构 | 保留重构前的经典版本，用于对比和回退参考 |

> **⚠️ 贡献者重要提示**：
> - **禁止直接提交到 `main` 和 `classical` 分支**
> - 所有新功能开发和 Bug 修复请基于 `dev` 分支创建功能分支
> - PR 目标必须为 `dev`，由作者审核后合并
> - `main` 和 `classical` 仅用于稳定版本发布和存档

![Version](https://img.shields.io/badge/version-2.1.3-blue)
![Python](https://img.shields.io/badge/python-3.9+-green)
![Platforms](https://img.shields.io/badge/platforms-17+-orange)
![License](https://img.shields.io/badge/license-MIT-gray)

## 📋 目录

- [项目简介](#-项目简介)
- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [配置说明](#️-配置说明)
- [API 使用](#-api-使用)
- [项目结构](#️-项目结构)
- [架构概览](#-架构概览)
- [平台开发](#-平台开发)
- [开发路线图](#️-开发路线图)
- [常见问题](#-常见问题)

## 🎯 项目简介

Provider-V2 是一个 AI 模型代理网关服务器，位于客户端（浏览器/SDK）与多个 AI 平台后端之间，提供统一的 OpenAI 兼容 API 接口。

### 核心能力

- **统一接口** — 通过单一端点访问多个 AI 平台（Qwen、DeepSeek、Ollama 等 17+ 平台）
- **智能分发** — 根据模型名称自动路由请求到对应平台
- **并发控制** — 支持请求并发限制与候选项选择
- **代理支持** — 灵活的 HTTP/HTTPS/SOCKS 代理配置，支持平台级自动切换
- **配置热重载** — 修改 `config.toml` 后自动生效，无需重启
- **流式输出** — 完整支持 Server-Sent Events 流式响应

### 技术栈

| 类别 | 技术 |
|------|------|
| 运行时 | Python 3.9+ |
| HTTP 框架 | aiohttp.web (异步，非 ASGI) |
| 事件循环 | uvloop (Unix), asyncio (Windows) |
| 配置格式 | TOML (tomllib/tomli) |
| 数据校验 | Pydantic |
| 日志 | loguru |
| 架构 | Runner-Worker 双进程 |

## ✨ 功能特性

- ✅ **OpenAI 兼容 API** — `POST /v1/chat/completions`，无缝对接现有 SDK
- ✅ **多平台支持** — Qwen (DashScope)、DeepSeek、Ollama 及 17+ 扩展平台
- ✅ **流式与非流式** — 完整支持 `stream: true/false`
- ✅ **模型列表** — `GET /v1/models` 返回可用模型
- ✅ **函数调用** — XML 标签格式的工具调用支持
- ✅ **健康检查** — `GET /health` 端点
- ✅ **认证中间件** — API Key 鉴权，支持黑白名单策略
- ✅ **CORS 支持** — 跨域请求友好
- ✅ **代理系统** — 全局/平台级代理，Qwen 平台支持 WAF 自动切换
- ✅ **配置热重载** — 修改配置自动生效

## 🚀 快速开始

### 环境要求

- Python >= 3.9
- pip 包管理器

### 安装与运行

```bash
# 1. 克隆项目
git clone https://github.com/nichengfuben/provider-v2.git
cd provider-v2

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动服务
python main.py
```

服务默认监听 `http://0.0.0.0:1337`。

### 验证安装

```bash
curl http://localhost:1337/health
```

返回 `{"status": "ok"}` 即表示启动成功。

### 快速测试

```bash
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-turbo",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 📦 安装指南

### 依赖说明

| 依赖 | 版本 | 用途 |
|------|------|------|
| aiohttp | >= 3.9.0 | 异步 HTTP 服务器/客户端 |
| pydantic | >= 2.0.0 | 数据校验 |
| loguru | >= 0.7.0 | 日志管理 |
| wasmtime | >= 0.40.0 | WASM 运行时 (DeepSeek PoW) |
| tomli | >= 2.0.0 | TOML 解析 (Python < 3.11) |

完整依赖列表见 `requirements.txt`。

### 跨平台说明

- **Linux/macOS**: 自动使用 `uvloop` 提升性能
- **Windows**: 使用默认 asyncio 事件循环
- **IDLE 环境**: 自动禁用双进程架构，单进程运行

## ⚙️ 配置说明

配置文件为项目根目录下的 `config.toml`。支持通过环境变量 `CONFIG_PATH` 指定其他路径。

### 完整配置示例

```toml
[server]
version = "2.1.3"
host = "0.0.0.0"
port = 1337
debug = false

[auth]
enabled = false                    # 是否启用 API Key 认证
keys = ["your-api-key-here"]       # 允许的 API Key 列表
group_list_type = "blacklist"      # 黑白名单策略
group_list = []

[gateway]
concurrent_enabled = false         # 是否启用并发控制
concurrent_count = 3               # 最大并发数
min_tokens = 10                    # 最小 token 数

[anthropic]
# Anthropic 格式输出配置
tool_call_format = "xml"           # tool call 格式: "xml" 或 "native"

[proxy]
proxy_server = "http://127.0.0.1:7890"  # 代理地址
proxy_enabled = true                      # 是否启用全局代理
proxy_urls = []                           # 额外代理 URL 列表（支持正则匹配）

[platforms_proxy]
enabled = true                     # 是否启用平台代理切换
enabled_platforms = ["qwen"]       # 允许切换代理的平台

[platforms]
platform_list_type = "blacklist"   # 平台黑白名单策略
platform_list = []                 # 黑名单/白名单中的平台名

# 注意：平台账号配置（如 API Key、用户名密码等）在各平台的 accounts.py 文件中
# 例如：src/platforms/qwen/accounts.py、src/platforms/deepseek/accounts.py
# config.toml 中的 [platforms.xxx] 仅用于启用/禁用平台
[platforms.qwen]
enabled = true

[platforms.deepseek]
enabled = true

[platforms.ollama]
enabled = true

[model_mapping]
# 模型名称到平台的映射（可选，通常由平台适配器自动注册）
# "qwen-turbo" = "qwen"

[fncall]
call_start_tag = "<function_calls>"
call_end_tag = "</function_calls>"
tools_start_tag = "<tools>"
tools_end_tag = "</tools>"

[debug]
level = "INFO"                     # 日志级别: DEBUG/INFO/WARNING/ERROR
```

### 配置优先级

1. 环境变量 `CONFIG_PATH` 指定的文件 (最高优先级)
2. 项目根目录 `config.toml`
3. 代码默认值 (最低优先级)

### 认证配置

```toml
[auth]
enabled = true
keys = ["sk-key1", "sk-key2"]
group_list_type = "whitelist"   # "blacklist" 或 "whitelist"
group_list = ["sk-key1"]        # 白名单模式: 仅允许列表中的 key
```

请求时携带 Header:
```
Authorization: Bearer sk-key1
# 或
X-API-Key: sk-key1
```

### 代理系统

代理支持多级控制:

| 层级 | 配置 | 说明 |
|------|------|------|
| 全局代理 | `[proxy]` 节 | 所有请求使用指定代理 |
| 环境变量 | `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` | 自动检测 |
| 平台切换 | `[platforms_proxy]` 节 | 指定平台可动态切换代理 |
| Qwen 自动 | 内置逻辑 | WAF 检测 → 自动启用 24 小时 → 自动关闭 |

## 💻 API 使用

### 聊天补全

```http
POST /v1/chat/completions
POST /chat/completions
```

**请求体:**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 否 | 模型名称，默认 `qwen-turbo` |
| messages | array | 是 | 消息列表 |
| stream | boolean | 否 | 是否流式输出，默认 `false` |
| temperature | number | 否 | 温度参数 |
| max_tokens | integer | 否 | 最大 token 数 |
| tools | array | 否 | 工具定义列表 |

**非流式请求示例:**

```bash
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-turbo",
    "messages": [
      {"role": "system", "content": "你是一个助手"},
      {"role": "user", "content": "请解释什么是异步编程"}
    ],
    "temperature": 0.7
  }'
```

**流式请求示例:**

```bash
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-turbo",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'
```

### 模型列表

```http
GET /v1/models
GET /v1/models/{model_name}
```

```bash
curl http://localhost:1337/v1/models
```

### 健康检查

```http
GET /health
```

```bash
curl http://localhost:1337/health
# 返回: {"status": "ok"}
```

### 函数调用

```http
POST /v1/function/call
GET /v1/functions
```

## 🏗️ 项目结构

```
provider-v2/
├── main.py                  # 入口文件 (Runner-Worker 双进程架构)
├── config.toml              # 主配置文件
├── requirements.txt         # Python 依赖
├── CLAUDE.md                # AI 编码代理指导文件
├── agents.md                # 顶层 AI 代理指导
│
├── src/
│   ├── core/                # 核心模块
│   │   ├── config/          # 模块化配置系统
│   │   │   ├── __init__.py  # 导出公共 API
│   │   │   ├── base.py      # 配置基类与数据类
│   │   │   ├── sections.py  # 各配置段定义 (server/auth/gateway/proxy等)
│   │   │   ├── manager.py   # 配置加载、热重载与路由匹配
│   │   │   └── resolver.py  # 模型到平台的路由解析
│   │   ├── server.py        # aiohttp 应用创建与中间件
│   │   ├── http.py          # 共享 HTTP 工具
│   │   └── scheduler.py     # 异步任务调度器
│   │
│   ├── routes/              # HTTP 路由
│   │   ├── chat.py          # 聊天补全端点
│   │   ├── models.py        # 模型列表端点
│   │   ├── function_call.py # 函数调用端点
│   │   └── health.py        # 健康检查端点
│   │
│   ├── platforms/           # 平台适配器 (17+)
│   │   ├── qwen/            # Qwen (DashScope) 平台
│   │   ├── deepseek/        # DeepSeek 平台 (Web 抓取)
│   │   ├── ollama/          # Ollama 本地服务
│   │   ├── cerebras/        # Cerebras 平台
│   │   ├── nvidia/          # NVIDIA NIM 平台
│   │   ├── openrouter/      # OpenRouter 平台
│   │   ├── chatmoe/         # ChatMoe 平台
│   │   ├── cursor/          # Cursor 平台
│   │   ├── codebuddy/       # CodeBuddy 平台
│   │   ├── chutes/          # Chutes 平台
│   │   ├── caiyuesbk/       # 彩月 SBK 平台
│   │   ├── apiairforce/     # APiAirForce 平台
│   │   ├── n1n/             # N1N 平台
│   │   ├── perplexity/      # Perplexity 平台
│   │   ├── openai_fm/       # OpenAI-FM 平台
│   │   ├── edge_tts/        # Edge TTS 语音合成
│   │   ├── gtts/            # Google TTS 语音合成
│   │   └── aitianhu2/       # AItianhu2 平台 (开发中)
│   │
│   └── logger.py            # 日志模块
│
├── docs-src/                # 文档源文件
│   ├── core/                # 核心模块文档
│   │   ├── ARCHITECTURE.md  # 整体架构图
│   │   └── proxy.md         # 代理系统文档
│   └── platforms/           # 平台开发规范
│
├── .scripts/                # 工具脚本 (被 .gitignore 排除)
│   ├── gen_platforms.py     # 平台配置生成
│   ├── gen_accounts.py      # 账户配置生成
│   └── ...
│
└── persist/                 # 持久化数据
    ├── qwen/                # Qwen 模型缓存
    ├── deepseek/            # DeepSeek 模型与 WASM 元数据
    └── ollama/              # Ollama 服务发现数据
```

## 🏛️ 架构概览

### Runner-Worker 双进程模型

```
main.py
├── Runner 进程 (父进程)
│   └── 监控 Worker 子进程
│       · exit code 42 → 自动重启
│       · Ctrl+C → 终止 Worker
│       · 最多 50 次重启
│
└── Worker 进程 (子进程, WORKER_PROCESS=1)
    └── asyncio 事件循环
        · aiohttp.web 服务器
        · 所有平台适配器
        · 配置热重载
```

### 请求处理流程

```
客户端 → aiohttp.web → 中间件 (CORS/认证/错误) → 路由处理器 → 平台适配器 → AI 后端
                                    ↓
                              根据 model 字段自动选择平台
```

### 平台适配器接口

所有平台适配器实现统一的 `PlatformAdapter` 抽象基类:

| 方法 | 说明 |
|------|------|
| `name` | 平台标识 (与目录名一致) |
| `init(session)` | 初始化 (必须立即返回，耗时操作放后台) |
| `candidates()` | 返回当前可用候选项 |
| `ensure_candidates(count)` | 确保候选项数量 |
| `complete(...)` | 聊天补全，yield 文本/字典 |
| `close()` | 清理资源 |

### 平台目录规范

```
src/platforms/{platform}/
├── __init__.py          # 包初始化
├── adapter.py           # 重导出 adapter_impl (不写逻辑)
├── util.py              # 工具函数 (延迟导入)
├── client.py            # HTTP 客户端
├── accounts.py          # 账户管理 (可选)
└── core/
    ├── adapter_impl.py  # 适配器核心实现
    ├── constants.py     # 常量定义
    └── ...
```

## 🔌 平台开发

新平台开发请阅读 `docs-src/platforms/PLATFORM_GUIDE.md`。

### 关键原则

1. **`init()` 必须立即返回** — 不得阻塞，耗时操作交后台 Task
2. **`adapter.py` 不写逻辑** — 仅重导出 `core/adapter_impl.py`
3. **`util.py` 使用 `__getattr__` 延迟导入** — 避免循环依赖
4. **共享 Session** — 所有客户端使用 `main.py` 创建的单一 Session
5. **SSL 全局禁用** — 所有请求 `ssl=False`

### yield 协议

`complete()` 方法 yield 的数据类型:

| 类型 | 说明 |
|------|------|
| `str` | 文本增量 |
| `dict` | `{"thinking": "..."}` 思考内容 |
| `dict` | `{"usage": {"prompt_tokens": N, "completion_tokens": N}}` 用量 |
| `dict` | `{"tool_calls": [...]}` 工具调用 |

## ❓ 常见问题

<details>
<summary><b>Q: 启动后无法访问服务？</b></summary>

**排查步骤:**

1. 检查端口是否被占用: `netstat -an | grep 1337`
2. 检查防火墙是否放行该端口
3. 查看日志输出是否有错误信息
4. 尝试修改 `config.toml` 中的 `port` 为其他值

</details>

<details>
<summary><b>Q: 如何启用 API Key 认证？</b></summary>

在 `config.toml` 中设置:

```toml
[auth]
enabled = true
keys = ["your-api-key"]
```

请求时携带 `Authorization: Bearer your-api-key` 或 `X-API-Key: your-api-key`。

</details>

<details>
<summary><b>Q: 如何添加新平台？</b></summary>

1. 在 `src/platforms/` 下创建平台目录
2. 遵循 `docs-src/platforms/PLATFORM_GUIDE.md` 规范
3. 实现 `PlatformAdapter` 抽象类
4. 在 `config.toml` 中添加平台配置

</details>

<details>
<summary><b>Q: 配置修改后如何生效？</b></summary>

Provider-V2 支持**配置热重载**。修改 `config.toml` 后，后台 watcher 会在 2 秒内自动检测并重载配置，无需重启服务。

</details>

<details>
<summary><b>Q: 如何配置代理？</b></summary>

**方式一: 全局代理**

```toml
[proxy]
proxy_server = "http://127.0.0.1:7890"
proxy_enabled = true
```

**方式二: 环境变量**

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
```

**方式三: 平台级代理** (仅对 `enabled_platforms` 中的平台有效)

```toml
[platforms_proxy]
enabled_platforms = ["qwen"]
```

</details>

<details>
<summary><b>Q: 如何在 IDLE 中调试？</b></summary>

在 IDLE 中运行时，双进程架构自动禁用，以单进程模式运行。这便于调试，但会失去自动重启功能。

</details>

## 🗺️ 开发路线图

### ✅ 已完成

- [x] 模块化配置系统 (`src/core/config/` — base/sections/manager/resolver)
- [x] 17+ 平台适配器 (Qwen, DeepSeek, Ollama, Cerebras, NVIDIA, OpenRouter, ChatMoe, Cursor, CodeBuddy, Chutes, CaiYueSBK, APiAirForce, N1N, Perplexity, OpenAI-FM, Edge TTS, Gtts, AItianhu2)
- [x] Watchdog 配置热重载 (2 秒轮询检测 mtime)
- [x] Runner-Worker 双进程架构与自动重启 (exit code 42)
- [x] 平台代理切换系统 (Qwen WAF 自动触发 24 小时)
- [x] XML 格式函数调用 (`<function_calls>` 自定义格式)
- [x] 日志颜色自动回退 (支持 Git Bash / Windows Terminal / 管道)
- [x] SSL 全局禁用 (TCPConnector CERT_NONE)

### 🚧 进行中

- [ ] AItianhu2 平台适配器完善
- [ ] 平台级 accounts 配置统一
- [ ] 集成测试框架

### 📋 计划中

- [ ] Docker 容器化支持
- [ ] CI/CD 配置 (GitHub Actions)
- [ ] 请求指标与 Prometheus 导出
- [ ] 模型缓存跨平台共享

## 📜 许可证

本项目采用 MIT 许可证。详见 [LICENSE](./LICENSE) 文件。

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

> **⚠️ 重要**：所有贡献必须提交到 `dev` 分支，**禁止直接提交到 `main` 或 `classical` 分支**。
> `main` 和 `classical` 由作者维护，仅用于稳定版本发布。

1. Fork 本仓库
2. 基于 `dev` 分支创建功能分支 (`git checkout -b feature/your-feature`)
3. 提交更改 (`git commit -m 'Add your feature'`)
4. 推送到分支 (`git push origin feature/your-feature`)
5. 创建 Pull Request，**目标分支必须为 `dev`**，由作者审核后合并

## 📮 联系方式

- **作者**: nichengfuben
- **邮箱**: nichengfuben@outlook.com
- **主页**: https://github.com/nichengfuben/provider-v2

### 技术支持

- 📧 技术支持邮箱: nichengfuben@outlook.com
- 🐛 [问题反馈](https://github.com/nichengfuben/provider-v2/issues)
- 💬 [社区讨论](https://github.com/nichengfuben/provider-v2/discussions)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star！**

Made with ❤️ by [nichengfuben](https://github.com/nichengfuben)

</div>
