# Provider-V2

> 一个基于 aiohttp 的异步 OpenAI 兼容 API 网关，支持多 AI 平台后端路由

![Version](https://img.shields.io/badge/version-2.1.1-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-green)
![License](https://img.shields.io/badge/license-MIT-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

## 📋 目录

- [🎯 项目简介](#-项目简介)
- [✨ 功能特性](#-功能特性)
- [🚀 快速开始](#-快速开始)
- [📦 安装指南](#-安装指南)
- [💻 使用说明](#-使用说明)
- [🔌 API 文档](#-api-文档)
- [⚙️ 配置说明](#️-配置说明)
- [🏗️ 项目结构](#️-项目结构)
- [🔄 架构设计](#-架构设计)
- [🧪 测试指南](#-测试指南)
- [📝 开发指南](#-开发指南)
- [❓ 常见问题](#-常见问题)
- [📄 更新日志](#-更新日志)
- [🤝 贡献指南](#-贡献指南)
- [📮 联系方式](#-联系方式)

## 🎯 项目简介

Provider-V2 是一个轻量级、高性能的 OpenAI 兼容 API 网关，采用异步架构设计，能够将标准 OpenAI 格式的聊天请求路由到多个 AI 平台后端（Qwen、DeepSeek、Ollama 等）。

### 项目背景

在多云 AI 服务场景下，开发者需要统一管理多个 AI 平台的 API 调用。Provider-V2 提供了一个标准化的接口层，屏蔽了不同平台的实现差异，支持请求代理、并发控制、热重载配置等企业级特性。

### 核心功能

- ✅ **OpenAI 兼容接口** - 完全兼容 `/v1/chat/completions` 标准接口
- ✅ **多平台路由** - 支持 Qwen、DeepSeek、Ollama 等多个 AI 平台
- ✅ **流式响应** - 支持 SSE 格式的流式输出
- ✅ **配置热重载** - 修改 `config.toml` 后 2 秒内自动生效，无需重启
- ✅ **并发控制** - 内置异步任务调度器，支持并发限制
- ✅ **代理支持** - 支持 HTTP/SOCKS 代理配置
- ✅ **认证中间件** - 支持 Bearer Token 和 X-API-Key 认证
- ✅ **自动重启** - Runner-Worker 架构保证服务高可用

### 技术栈

| 类别 | 技术 |
|------|------|
| 运行时 | Python 3.8+ |
| HTTP 框架 | aiohttp >= 3.9.0 |
| 数据验证 | pydantic >= 2.0.0 |
| 日志系统 | loguru >= 0.7.0 |
| 配置格式 | TOML |
| 架构模式 | 异步 + Runner-Worker 双进程 |

### 为什么选择本项目

| 特性 | Provider-V2 | 其他网关 |
|------|-------------|----------|
| 异步架构 | ✅ 原生异步 | ❌ 同步或伪异步 |
| 配置热重载 | ✅ 自动检测 | ❌ 需要重启 |
| 轻量级 | ✅ 无外部依赖 | ❌ 依赖 Redis/数据库 |
| 多平台 | ✅ 可扩展架构 | ❌ 单一平台 |
| 自动重启 | ✅ 进程守护 | ❌ 需外部工具 |

## ✨ 功能特性

### 核心功能

- ✅ **标准 API 接口** - 完全兼容 OpenAI API 规范，无缝对接现有客户端
- ✅ **智能平台路由** - 根据模型名称自动选择对应平台后端
- ✅ **流式/非流式响应** - 支持 `stream: true/false` 两种模式
- ✅ **并发请求控制** - 可配置的并发请求数量和最小 token 限制
- ✅ **API 认证** - 支持黑名单/白名单模式的 API Key 认证

### 高级功能

- 🔧 **平台代理** - 可为不同平台独立配置代理开关
- 🔧 **WAF 自动检测** - Qwen 平台支持 WAF 拦截自动检测并启用代理
- 🔧 **模型列表查询** - 支持 `/v1/models` 端点查询可用模型
- 🔧 **函数调用** - 支持 XML 标签格式的函数调用格式

### 即将推出

- 🚧 **DeepSeek 完整实现** - 当前为 Stub 状态
- 🚧 **更多平台支持** - OpenRouter、Perplexity、Cerebras 等
- 🚧 **请求日志记录** - 详细的请求/响应日志
- 🚧 **性能监控** - 请求延迟和吞吐量指标

## 🚀 快速开始

### 环境要求

- Python >= 3.8
- pip >= 21.0
- 操作系统：Windows / Linux / macOS

### 30 秒快速体验

```bash
# 克隆项目
git clone https://github.com/nichengfuben/provider-v2.git

# 进入目录
cd provider-v2

# 安装依赖
pip install -r requirements.txt

# 启动服务
python main.py
```

启动成功后，服务将运行在 `http://0.0.0.0:1337`

### 验证安装

```bash
# 健康检查
curl http://localhost:1337/health

# 查看可用模型
curl http://localhost:1337/v1/models

# 发送聊天请求（示例）
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-turbo",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

## 📦 安装指南

### 方式一：源码安装（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/nichengfuben/provider-v2.git
cd provider-v2

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置服务（可选）
# 编辑 config.toml 文件，修改端口、认证等配置

# 4. 启动服务
python main.py
```

### 方式二：指定配置文件启动

```bash
# 使用自定义配置文件路径
CONFIG_PATH=/path/to/your/config.toml python main.py
```

### 依赖说明

| 依赖包 | 版本要求 | 用途 |
|--------|----------|------|
| aiohttp | >= 3.9.0 | 异步 HTTP 框架 |
| pydantic | >= 2.0.0 | 数据验证和模型定义 |
| loguru | >= 0.7.0 | 日志系统 |
| tomli | >= 2.0.0 | TOML 配置解析（Python < 3.11） |
| aiohttp-socks | >= 0.8.0 | SOCKS 代理支持 |

### 系统特定说明

#### Windows

```powershell
# 安装 Python 依赖
pip install -r requirements.txt

# 启动服务
python main.py

# 停止服务：Ctrl+C
```

#### macOS / Linux

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 后台运行
nohup python main.py > provider.log 2>&1 &

# 停止服务
pkill -f "python main.py"
```

## 💻 使用说明

### 基础用法

#### 发送聊天请求

```python
import requests

# 非流式请求
response = requests.post(
    "http://localhost:1337/v1/chat/completions",
    json={
        "model": "qwen-turbo",
        "messages": [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "你好"}
        ],
        "temperature": 0.7,
        "max_tokens": 1000
    }
)

print(response.json())
```

#### 流式请求

```python
import requests

response = requests.post(
    "http://localhost:1337/v1/chat/completions",
    json={
        "model": "qwen-turbo",
        "messages": [{"role": "user", "content": "你好"}],
        "stream": True
    },
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode("utf-8"))
```

### 高级用法

#### 配置 API 认证

在 `config.toml` 中启用认证：

```toml
[auth]
enabled = true
keys = ["your-api-key-here"]
group_list_type = "blacklist"
group_list = []
```

使用 API Key 发送请求：

```bash
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-api-key-here" \
  -d '{"model": "qwen-turbo", "messages": [{"role": "user", "content": "你好"}]}'
```

或使用 X-API-Key 请求头：

```bash
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"model": "qwen-turbo", "messages": [{"role": "user", "content": "你好"}]}'
```

#### 配置代理

为 Qwen 平台启用代理：

```toml
[proxy]
proxy_server = "http://110.42.196.178:40000"
proxy_enabled = true

[platforms_proxy]
enabled_platforms = ["qwen"]
```

#### 并发控制

```toml
[gateway]
concurrent_enabled = true
concurrent_count = 5
min_tokens = 10
```

### 使用 OpenAI SDK 调用

```python
from openai import OpenAI

# 初始化客户端，指向本地网关
client = OpenAI(
    api_key="your-api-key",  # 如果未启用认证，可填任意值
    base_url="http://localhost:1337/v1"
)

response = client.chat.completions.create(
    model="qwen-turbo",
    messages=[{"role": "user", "content": "你好"}]
)

print(response.choices[0].message.content)
```

## 🔌 API 文档

### 接口概览

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/v1/chat/completions` | 聊天完成（OpenAI 兼容） |
| POST | `/chat/completions` | 聊天完成（兼容路径） |
| GET | `/v1/models` | 列出可用模型 |
| GET | `/v1/models/{model}` | 获取模型详情 |
| POST | `/v1/function/call` | 函数调用 |
| GET | `/v1/functions` | 列出可用函数 |
| GET | `/health` | 健康检查 |

### 接口详情

#### 聊天完成

```http
POST /v1/chat/completions
Content-Type: application/json
Authorization: Bearer <api-key>
```

**请求体：**

```json
{
  "model": "qwen-turbo",
  "messages": [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}
```

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| model | string | 是 | 模型名称，用于路由到对应平台 |
| messages | array | 是 | 消息列表，包含 role 和 content |
| temperature | number | 否 | 温度参数，默认 1.0 |
| max_tokens | number | 否 | 最大生成 token 数 |
| stream | boolean | 否 | 是否启用流式输出，默认 false |

**非流式响应示例：**

```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "qwen-turbo",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！有什么可以帮助你的？"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

**流式响应示例（SSE 格式）：**

```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"role":"assistant","content":"你"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"index":0,"delta":{"content":"好"},"finish_reason":null}]}

data: [DONE]
```

#### 列出模型

```http
GET /v1/models
```

**响应示例：**

```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen-turbo",
      "object": "model",
      "created": 1234567890,
      "owned_by": "qwen"
    }
  ]
}
```

#### 健康检查

```http
GET /health
```

**响应示例：**

```json
{
  "status": "ok",
  "version": "2.1.1"
}
```

### 平台路由规则

| 模型前缀 | 路由平台 | 说明 |
|----------|----------|------|
| `deepseek` 或 `deepseek-` | DeepSeek | 当前为 Stub 状态 |
| 其他所有模型 | Qwen | 默认平台 |

### 错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未授权（认证失败） |
| 403 | 禁止访问（IP/Key 黑名单） |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

**错误响应格式：**

```json
{
  "error": {
    "message": "错误描述",
    "type": "error_type",
    "code": 400
  }
}
```

## ⚙️ 配置说明

### 配置文件

Provider-V2 使用 `config.toml` 作为主配置文件，位于项目根目录。

### 完整配置示例

```toml
[server]
version = "2.1.1"
host = "0.0.0.0"
port = 1337
debug = false

[auth]
enabled = false
keys = []
group_list_type = "blacklist"
group_list = []

[gateway]
concurrent_enabled = false
concurrent_count = 3
min_tokens = 10

[proxy]
proxy_server = "http://110.42.196.178:40000"
proxy_enabled = true
proxy_urls = []

[platforms_proxy]
enabled_platforms = ["qwen"]

[platforms]
platform_list_type = "blacklist"
platform_list = ["deepseek"]

[platforms.qwen]
enabled = true

[platforms.deepseek]
enabled = true

[platforms.ollama]
enabled = true

[fncall]
call_start_tag = "<function_calls>"
call_end_tag = "</function_calls>"
tools_start_tag = "<tools>"
tools_end_tag = "</tools>"

[debug]
level = "INFO"
```

### 配置项详解

#### `[server]` - 服务器配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| host | string | `"0.0.0.0"` | 监听地址 |
| port | number | `1337` | 监听端口 |
| debug | boolean | `false` | 调试模式 |

#### `[auth]` - 认证配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | boolean | `false` | 是否启用 API 认证 |
| keys | array | `[]` | 允许的 API Key 列表 |
| group_list_type | string | `"blacklist"` | 列表类型：`blacklist` 或 `whitelist` |
| group_list | array | `[]` | 黑名单/白名单 Key 列表 |

#### `[gateway]` - 网关配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| concurrent_enabled | boolean | `false` | 是否启用并发控制 |
| concurrent_count | number | `3` | 最大并发请求数 |
| min_tokens | number | `10` | 最小 token 数 |

#### `[proxy]` - 代理配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| proxy_server | string | `""` | 代理服务器地址 |
| proxy_enabled | boolean | `false` | 全局代理开关 |
| proxy_urls | array | `[]` | 代理 URL 列表 |

#### `[platforms_proxy]` - 平台代理配置

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled_platforms | array | `[]` | 支持独立代理开关的平台列表 |

#### `[platforms]` - 平台管理

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| platform_list_type | string | `"blacklist"` | 列表类型：`blacklist` 或 `whitelist` |
| platform_list | array | `[]` | 黑名单/白名单平台列表 |

#### `[platforms.*]` - 平台配置

每个平台可独立配置：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| enabled | boolean | `true` | 平台开关 |
| api_key | string | `""` | 平台 API Key（可选） |

### 环境变量

| 变量名 | 说明 |
|--------|------|
| `CONFIG_PATH` | 指定配置文件路径 |
| `QWEN_API_KEY` | Qwen 平台 API Key |
| `DEEPSEEK_API_KEY` | DeepSeek 平台 API Key |
| `HTTP_PROXY` | HTTP 代理地址 |
| `HTTPS_PROXY` | HTTPS 代理地址 |
| `ALL_PROXY` | 全局代理地址 |

### 配置优先级

1. 环境变量（最高优先级）
2. `config.toml` 配置文件
3. 代码默认值

### 配置热重载

修改 `config.toml` 后，系统会在 **2 秒内** 自动检测并应用新配置，**无需重启服务**。

## 🏗️ 项目结构

```
provider-v2/
├── 📁 src/                    # 源代码目录
│   ├── 📁 core/               # 核心模块
│   │   ├── config.py          # 配置管理（支持热重载）
│   │   ├── server.py          # aiohttp 应用创建和中间件
│   │   ├── http.py            # 共享 HTTP 工具
│   │   └── scheduler.py       # 异步任务调度器
│   ├── 📁 routes/             # 路由处理器
│   │   ├── chat.py            # 聊天接口处理器
│   │   ├── models.py          # 模型列表接口
│   │   ├── function_call.py   # 函数调用接口
│   │   └── health.py          # 健康检查
│   ├── 📁 platforms/          # 平台适配器
│   │   ├── 📁 qwen/           # Qwen 平台（完整实现）
│   │   ├── 📁 deepseek/       # DeepSeek 平台（Stub）
│   │   ├── 📁 ollama/         # Ollama 平台（基础实现）
│   │   └── 📁 ...             # 其他平台（占位）
│   └── logger.py              # 日志模块（基于 loguru）
├── 📁 persist/                # 运行时数据目录
├── 📁 docs-src/               # 文档源文件
├── 📁 .scripts/               # 工具脚本
├── 📄 main.py                 # 入口文件（Runner-Worker 架构）
├── 📄 config.toml             # 主配置文件
├── 📄 requirements.txt        # Python 依赖
└── 📄 agents.md               # AI 编码代理指南
```

### 核心模块说明

| 模块 | 路径 | 说明 |
|------|------|------|
| 配置系统 | `src/core/config.py` | TOML 配置加载和热重载 |
| 服务器 | `src/core/server.py` | aiohttp 应用、CORS/认证/错误中间件 |
| 聊天处理 | `src/routes/chat.py` | 请求解析、平台路由、响应格式化 |
| Qwen 适配器 | `src/platforms/qwen/` | 阿里云 DashScope API 完整实现 |
| DeepSeek 适配器 | `src/platforms/deepseek/` | 占位实现，核心文件为空 |
| Ollama 适配器 | `src/platforms/ollama/` | 本地 Ollama 服务对接 |

## 🔄 架构设计

### Runner-Worker 双进程架构

```
┌─────────────────────────────────────────┐
│          Runner 进程（父进程）            │
│  ┌───────────────────────────────────┐  │
│  │  - 监控 Worker 子进程              │  │
│  │  - 处理自动重启（退出码 42）       │  │
│  │  - 传递 Ctrl+C 信号               │  │
│  │  - 最多重启 50 次                 │  │
│  └───────────────────────────────────┘  │
│                    │                    │
│                    ▼                    │
│  ┌───────────────────────────────────┐  │
│  │       Worker 进程（子进程）         │  │
│  │  ┌─────────────────────────────┐  │  │
│  │  │  - asyncio 事件循环         │  │  │
│  │  │  - aiohttp HTTP 服务器      │  │  │
│  │  │  - 中间件链（CORS/Auth/Error）│ │  │
│  │  │  - 路由处理器                │  │  │
│  │  │  - 平台适配器               │  │  │
│  │  │  - 配置热重载任务            │  │  │
│  │  └─────────────────────────────┘  │  │
│  └───────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 请求处理流程

```
客户端请求
    │
    ▼
┌──────────────┐
│  CORS 中间件  │  ← 添加跨域头，处理 OPTIONS 预检
└──────────────┘
    │
    ▼
┌──────────────┐
│  Auth 中间件  │  ← 验证 Bearer Token 或 X-API-Key
└──────────────┘
    │
    ▼
┌──────────────┐
│  Error 中间件 │  ← 捕获未处理异常，返回 500 JSON
└──────────────┘
    │
    ▼
┌──────────────┐
│  路由处理器   │  ← 解析请求 JSON，选择平台
└──────────────┘
    │
    ▼
┌──────────────┐
│  平台适配器   │  ← 调用对应平台 API（Qwen/DeepSeek/Ollama）
└──────────────┘
    │
    ▼
┌──────────────┐
│  响应返回     │  ← JSON 或 SSE 流式响应
└──────────────┘
```

### 关键设计决策

1. **异步架构**：使用 aiohttp 原生异步，避免同步阻塞
2. **进程守护**：Runner-Worker 模式保证服务高可用
3. **配置热重载**：后台任务轮询文件修改，2 秒内生效
4. **适配器模式**：每个平台独立实现，易于扩展
5. **SSL 禁用**：全局 `ssl=False`，简化部署

## 🧪 测试指南

> ⚠️ **注意**：本项目当前**未配置测试框架**，无 `pytest`、`unittest` 等测试基础设施。

### 手动测试

#### 健康检查测试

```bash
curl http://localhost:1337/health
```

预期响应：

```json
{"status": "ok", "version": "2.1.1"}
```

#### 模型列表测试

```bash
curl http://localhost:1337/v1/models
```

#### 聊天功能测试

```bash
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-turbo",
    "messages": [{"role": "user", "content": "你好"}],
    "max_tokens": 50
  }'
```

### 未来测试计划

- [ ] 集成 pytest 框架
- [ ] 单元测试核心模块
- [ ] 集成测试 API 端点
- [ ] 平台适配器 Mock 测试
- [ ] CI/CD 自动化测试

## 📝 开发指南

### 开发环境搭建

```bash
# 1. Fork 并克隆项目
git clone https://github.com/nichengfuben/provider-v2.git
cd provider-v2

# 2. 安装依赖
pip install -r requirements.txt

# 3. 创建功能分支
git checkout -b feature/your-feature-name
```

### 代码规范

- 使用类型注解
- 公共 API 使用 docstring
- 错误处理使用 try/except
- 异步函数使用 async/await
- 新文件使用 `from __future__ import annotations`
- 日志使用 `src.logger.get_logger()`

### 添加新平台适配器

1. 在 `src/platforms/` 下创建平台目录：

```
src/platforms/your_platform/
├── __init__.py
├── adapter.py        # 主适配器（重新导出）
├── util.py           # 工具函数
└── core/
    ├── adapter_impl.py  # 适配器实现
    ├── client.py        # HTTP 客户端
    ├── accounts.py      # 账户管理
    └── constants.py     # 常量定义
```

2. 实现 `chat()` 和 `chat_stream()` 方法
3. 在 `config.toml` 中添加平台配置
4. 更新平台路由逻辑

### 提交规范

采用 Conventional Commits 规范：

```
<type>(<scope>): <description>

[optional body]
```

**Type 类型：**

- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `refactor`: 重构
- `chore`: 构建/工具相关

### 分支命名

- `feature/xxx`: 新功能
- `fix/xxx`: Bug 修复
- `docs/xxx`: 文档更新

## ❓ 常见问题

<details>
<summary><b>Q1: 启动后无法访问服务怎么办？</b></summary>

**排查步骤：**

```bash
# 1. 检查端口是否被占用
netstat -ano | findstr :1337

# 2. 检查防火墙
# Windows: 允许端口通过防火墙
netsh advfirewall firewall add rule name="Provider-V2" dir=in action=allow protocol=TCP localport=1337

# 3. 查看日志输出
# 确认服务已启动并监听正确地址
```

</details>

<details>
<summary><b>Q2: 如何修改监听端口？</b></summary>

**解决方案：**

编辑 `config.toml`：

```toml
[server]
port = 8080  # 修改为你想要的端口
```

保存后等待 2 秒自动生效，或重启服务。

</details>

<details>
<summary><b>Q3: 如何查看 Qwen 平台 API Key？</b></summary>

**解决方案：**

设置环境变量：

```bash
# Linux/macOS
export QWEN_API_KEY="your-api-key"

# Windows PowerShell
$env:QWEN_API_KEY="your-api-key"
```

或在代码中直接配置。

</details>

<details>
<summary><b>Q4: DeepSeek 平台为什么不可用？</b></summary>

**说明：**

当前 DeepSeek 平台核心实现（`adapter_impl.py` 和 `client.py`）为 **Stub 状态**，仅包含注释代码。完整实现开发中。

</details>

<details>
<summary><b>Q5: 配置修改后多久生效？</b></summary>

**答案：**

修改 `config.toml` 后，系统会在 **2 秒内** 自动检测并应用新配置，**无需手动重启**。

</details>

<details>
<summary><b>Q6: 如何在 IDLE 中运行？</b></summary>

**解决方案：**

项目已支持 IDLE 环境检测，在 IDLE 中运行时会自动禁用 Runner-Worker 架构（自动重启不可用），直接启动 Worker。

</details>

## 📄 更新日志

### [2.1.1] - 当前版本
#### 功能
- ✅ 完整实现 Qwen 平台适配器
- ✅ 支持流式/非流式响应
- ✅ 配置热重载功能
- ✅ Runner-Worker 双进程架构
- ✅ CORS/认证/错误中间件
- ✅ 并发请求控制
- ✅ 平台代理支持

#### 已知问题
- ⚠️ DeepSeek 平台核心实现未完成
- ⚠️ 无自动化测试框架
- ⚠️ 部分平台为 Stub 状态（openrouter, perplexity, cerebras 等）

### 历史版本

> 详细构建说明请查看 `.scripts/build.txt`

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. **报告 Bug**：通过 [Issues](https://github.com/nichengfuben/provider-v2/issues) 提交 Bug 报告
2. **功能建议**：在 [Discussions](https://github.com/nichengfuben/provider-v2/discussions) 中提出新想法
3. **代码贡献**：提交 Pull Request
4. **文档改进**：帮助完善文档
5. **平台适配**：添加新的 AI 平台支持

### Pull Request 流程

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 行为准则

- 遵循项目现有代码风格
- 添加必要的类型注解
- 使用 docstring 描述公共 API
- 保持向后兼容性（如适用）

## 📜 许可证

本项目采用 MIT 许可证。

```
MIT License

Copyright (c) 2024 nichengfuben

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

## 👥 作者

- **nichengfuben** - [GitHub](https://github.com/nichengfuben)

## 📮 联系方式

- **作者**：nichengfuben
- **邮箱**：nichengfuben@outlook.com
- **主页**：https://github.com/nichengfuben/provider-v2

### 技术支持

- 📧 技术支持邮箱：nichengfuben@outlook.com
- 🐛 [问题反馈](https://github.com/nichengfuben/provider-v2/issues)
- 💬 [社区讨论](https://github.com/nichengfuben/provider-v2/discussions)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star！**

Made with ❤️ by [nichengfuben](https://github.com/nichengfuben)

</div>
