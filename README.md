# Provider-V2

> 统一 AI 模型网关，聚合多个 AI 平台，提供 OpenAI 和 Anthropic 兼容 API

## 分支说明

| 分支 | 定位 | 说明 |
|------|------|------|
| **main** | 稳定发布 | 经过验证的稳定版本，适合生产部署与日常使用 |
| **dev** | 活跃开发 | 相比 main 包含更多最新更改与功能，但可能不够稳定，建议仅在需要新特性时使用 |
| **classical** | 历史快照 | 重构前的冻结版本，仅供对比与回退参考，不再接受更新 |

> ⚠️ **重要**
> - **禁止直接提交到 `main` 和 `classical` 分支**
> - 所有新功能开发和 Bug 修复请基于 `dev` 分支创建功能分支
> - PR 目标必须为 `dev`，由作者审核后合并
> - `main` 仅用于稳定发布；`classical` 为只读存档

<div align="center">

![Status](https://img.shields.io/badge/status-v2.2.61-blue)
![Version](https://img.shields.io/badge/version-2.2.61-blue)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platforms](https://img.shields.io/badge/platforms-11+-orange)

[![GitHub stars](https://img.shields.io/github/stars/nichengfuben/provider-v2)](https://github.com/nichengfuben/provider-v2/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/nichengfuben/provider-v2)](https://github.com/nichengfuben/provider-v2/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](https://github.com/nichengfuben/provider-v2/pulls)

</div>

---

## 📋 目录

- [项目简介](#-项目简介)
- [功能特性](#-功能特性)
- [效果展示](#-效果展示)
- [快速开始](#-快速开始)
- [安装指南](#-安装指南)
- [使用说明](#-使用说明)
- [项目结构](#-项目结构)
- [配置说明](#-配置说明)
- [API 文档](#-api-文档)
- [测试指南](#-测试指南)
- [开发指南](#-开发指南)
- [路线图](#-路线图)
- [常见问题](#-常见问题)
- [贡献指南](#-贡献指南)
- [许可证](#-许可证)
- [联系方式](#-联系方式)

---

## 🎯 项目简介

### 项目背景

随着 AI 大模型技术的飞速发展，市场上涌现出众多优秀的 AI 平台（如 Qwen、DeepSeek、GLM、Cerebras 等）。每个平台都提供各自独立的 API 接口，格式各异，调用方式不同。开发者在集成多个平台时，面临以下痛点：

- **接口不统一**：每个平台的 API 格式各异，需要编写大量适配代码
- **切换成本高**：更换平台需要修改核心业务逻辑
- **缺乏容错机制**：单平台故障导致服务不可用
- **工具调用差异**：Function Calling 格式各平台实现不一致
- **推理增强不兼容**：thinking、search 等高级功能调用方式各异

**Provider-V2 应运而生**——一个高性能的 AI 模型网关，通过统一的 API 接口，让开发者可以轻松访问多个主流 AI 平台，无需关心各平台的差异性实现细节。

### 核心功能

- 🔌 **多平台聚合**：统一接入 Qwen、DeepSeek、GLM、Cerebras、Ollama、ChatMoe、Cursor、CodeBuddy、NVIDIA 等 11+ 平台
- 🔄 **API 兼容性**：同时兼容 OpenAI 和 Anthropic API 规范，无缝迁移现有项目
- ⚡ **并发竞速**：智能选择最快响应的候选项，显著降低延迟
- 🛠️ **工具调用支持**：完整的 function calling 功能，通过 XML 标签注入工具描述，支持中英文模板自定义
- 🧠 **推理增强**：支持 thinking 和 search 参数增强推理能力
- 📡 **流式响应**：完整支持 SSE 流式输出，实时展示生成内容
- 🔐 **鉴权中间件**：可配置的 API Key 鉴权机制，保障服务安全
- 🔄 **配置热加载**：修改配置文件后自动重载，无需重启服务
- 🌐 **代理支持**：全局代理配置，自动禁用 SSL 验证
- 🔁 **平台热重载**：平台代码变更时自动重载，无需重启进程

### 技术栈

| 类别 | 技术 | 版本要求 |
|------|------|----------|
| Web 框架 | aiohttp | >= 3.9.0 |
| 异步运行时 | uvicorn[standard] | >= 0.20.0 |
| HTTP 客户端 | aiohttp | >= 3.9.0 |
| 数据验证 | pydantic | >= 2.0.0 |
| 平台 SDK | cerebras-cloud-sdk | >= 1.0.0 |
| WASM 运行时 | wasmtime | >= 0.40.0 |
| HTML 解析 | beautifulsoup4 | >= 4.12.0 |
| 加密库 | pycryptodome | >= 3.20.0 |

### 为什么选择 Provider-V2

| 特性 | Provider-V2 | 直接接入各平台 |
|------|:-----------:|:-------------:|
| 统一 API | ✅ OpenAI/Anthropic 兼容 | ❌ 各平台 API 不同 |
| 并发竞速 | ✅ 自动选择最快响应 | ❌ 需自行实现 |
| 多平台切换 | ✅ 配置文件切换 | ❌ 需修改代码 |
| 工具调用 | ✅ 统一 fncall 接口，XML 模板可定制 | ❌ 格式各异 |
| 推理增强 | ✅ thinking/search 支持 | ❌ 仅部分支持 |
| 代理支持 | ✅ 全局代理配置 | ❌ 需逐个配置 |
| 热加载 | ✅ 配置和平台代码均可热重载 | ❌ 不支持 |
| 账号池 | ✅ 多账号轮询 | ❌ 需自行管理 |

---

## ✨ 功能特性

### 核心功能

| 功能 | 状态 | 说明 |
|------|:----:|------|
| **多平台聚合** | ✅ | 支持 11+ AI 平台 |
| **OpenAI 兼容 API** | ✅ | 完整支持 `/v1/chat/completions`、`/v1/models` 等接口 |
| **Anthropic 兼容 API** | ✅ | 完整支持 `/v1/messages`、`/v1/models` 等接口 |
| **并发竞速模式** | ✅ | 同时请求多个候选项，选择最快响应 |
| **工具调用（fncall）** | ✅ | XML 标签注入，中英文模板，支持多行参数 |
| **推理增强** | ✅ | 支持 thinking 和 search 参数增强 |
| **流式响应** | ✅ | 完整支持 SSE 流式输出 |
| **鉴权中间件** | ✅ | 可配置的 API Key 鉴权 |
| **配置热加载** | ✅ | 修改 config.toml 自动重载，无需重启 |
| **平台热重载** | ✅ | 修改平台代码自动重载适配器 |
| **代理支持** | ✅ | 全局代理配置，自动禁用 SSL 验证 |

### 高级功能

| 功能 | 状态 | 说明 |
|------|:----:|------|
| **智能 Token 回退** | ✅ | 平台返回 usage 为 0 时自动估算 |
| **模型映射** | ✅ | 支持自定义模型名称映射 |
| **健康检查** | ✅ | 内置 `/health` 健康检查端点 |
| **自动文档** | ✅ | 集成 Swagger UI 和 ReDoc |
| **WASM PoW** | ✅ | DeepSeek 平台自动管理 PoW 求解 |
| **账号池管理** | ✅ | 支持多账号轮询和自动登录 |
| **TAS 选择器** | ✅ | Thompson Sampling + 冷却机制，智能选择候选项 |
| **文件管理** | ✅ | 支持文件上传和管理 API（内存存储） |
| **Assistants API** | ✅ | 基础实现（内存存储） |

### 已支持平台

| 平台 | 状态 | 能力 |
|------|:----:|------|
| Qwen | ✅ | chat, tools, vision, search |
| DeepSeek | ✅ | chat, thinking, search |
| GLM | ✅ | chat, tools, vision |
| Cerebras | ✅ | chat |
| Ollama | ✅ | chat, embedding |
| ChatMoe | ✅ | chat |
| Cursor | ✅ | chat |
| CodeBuddy | ✅ | chat |
| NVIDIA | ✅ | chat |
| 更多平台 | 🚧 | 持续开发中 |

---

## 🖼️ 效果展示

### 服务启动

```bash
$ python main.py

2026-04-05 10:30:15 | INFO     | main | Provider-V2 已启动: http://0.0.0.0:1337
2026-04-05 10:30:15 | INFO     | registry | 发现 11 个平台适配器，开始注册
2026-04-05 10:30:16 | INFO     | registry | 平台 [qwen] 已注册 (3 模型)
2026-04-05 10:30:16 | INFO     | registry | 平台 [deepseek] 已注册 (2 模型)
2026-04-05 10:30:16 | INFO     | registry | 注册完成: ['qwen', 'deepseek', 'glm', ...]
```

### API 调用示例

```bash
# OpenAI 兼容调用
curl -X POST http://localhost:1337/v1/chat/completions \
  -H "Authorization: Bearer sk-xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-plus",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

**响应示例：**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "qwen-plus",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！我是 AI 助手，很高兴为你服务。"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  }
}
```

### 内置 WebUI

启动服务后直接访问 `http://localhost:1337/` 即可打开内置管理界面，支持主题切换、状态刷新、模型清单、配置管理与便携设置。

---

## 🚀 快速开始

### 环境要求

| 依赖 | 版本要求 |
|------|----------|
| Python | >= 3.8 |
| pip | >= 21.0 |
| 操作系统 | Windows / macOS / Linux |

### 30 秒快速体验

```bash
# 1. 克隆项目
git clone https://github.com/nichengfuben/provider-v2.git
cd provider-v2

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置平台账号
# 编辑 config.toml 文件，填入各平台的 API Key

# 4. 启动服务
python main.py
```

### 验证安装

访问以下地址验证服务是否正常运行：

| 地址 | 说明 |
|------|------|
| http://localhost:1337/health | 健康检查，返回 `{"status": "healthy"}` |
| http://localhost:1337/ | 内置 WebUI 管理界面 |
| http://localhost:1337/v1/models | 模型列表接口 |

---

## 📦 安装指南

### 方式一：pip 安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/nichengfuben/provider-v2.git
cd provider-v2

# 安装依赖
pip install -r requirements.txt
```

### 方式二：使用虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
.\venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 方式三：Docker 安装

**Dockerfile：**
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 1337

CMD ["python", "main.py"]
```

```bash
# 构建镜像
docker build -t provider-v2:latest .

# 运行容器
docker run -d -p 1337:1337 -v $(pwd)/config.toml:/app/config.toml provider-v2:latest
```

### 系统特定说明

#### Windows

```powershell
# 使用虚拟环境
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

> **注意**：Windows 平台使用 `asyncio` 事件循环，其他平台优先使用 `uvloop`。

#### macOS

```bash
# 安装 Homebrew（如已安装可跳过）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 安装 Python 3.11
brew install python@3.11

# 创建虚拟环境并安装
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

#### Linux (Ubuntu/Debian)

```bash
# 安装 Python 和依赖
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# 创建虚拟环境并安装
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py

# 使用 systemd 管理（可选）
sudo systemctl enable python3
```

---

## 💻 使用说明

### 基础用法

#### OpenAI API 调用

```python
import aiohttp
import asyncio

async def chat_with_openai():
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": "Bearer your-api-key",
            "Content-Type": "application/json"
        }
        data = {
            "model": "qwen-plus",
            "messages": [
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ],
            "stream": False
        }

        async with session.post(
            "http://localhost:1337/v1/chat/completions",
            headers=headers,
            json=data
        ) as response:
            result = await response.json()
            print(result["choices"][0]["message"]["content"])

asyncio.run(chat_with_openai())
```

#### Anthropic API 调用

```python
import aiohttp
import asyncio

async def chat_with_anthropic():
    async with aiohttp.ClientSession() as session:
        headers = {
            "x-api-key": "your-api-key",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        data = {
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1024,
            "messages": [
                {"role": "user", "content": "你好，请介绍一下你自己"}
            ]
        }

        async with session.post(
            "http://localhost:1337/v1/messages",
            headers=headers,
            json=data
        ) as response:
            result = await response.json()
            print(result["content"][0]["text"])

asyncio.run(chat_with_anthropic())
```

### 高级用法

#### 工具调用（Function Calling）

Provider-V2 使用 XML 标签格式将工具描述注入到提示中。模型需要按照以下格式返回函数调用：

```xml
<function=函数名>
<参数名1>
参数值
</参数名1>
<参数名2>
参数值
</参数名2>
</function>
```

**重要格式要求：**
- XML 标签名必须与参数名完全一致
- 标签和值之间**必须**有换行符
- 必须包含所有必需参数
- 支持多行参数（如代码块）

**示例代码：**

```python
import aiohttp
import asyncio

async def function_calling_example():
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": "Bearer your-api-key",
            "Content-Type": "application/json"
        }
        data = {
            "model": "qwen-plus",
            "messages": [
                {"role": "user", "content": "北京今天的天气怎么样？"}
            ],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "获取指定城市的天气",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {
                                    "type": "string",
                                    "description": "城市名称"
                                }
                            },
                            "required": ["city"]
                        }
                    }
                }
            ]
        }

        async with session.post(
            "http://localhost:1337/v1/chat/completions",
            headers=headers,
            json=data
        ) as response:
            result = await response.json()
            tool_call = result["choices"][0]["message"]["tool_calls"][0]
            print(f"模型调用了工具: {tool_call['function']['name']}")
            print(f"参数: {tool_call['function']['arguments']}")

asyncio.run(function_calling_example())
```

**自定义模板：**

可以在 `config.toml` 中自定义中英文提示模板：

```toml
[fncall.templates]
en = """
You are a helpful AI assistant that can interact with tools to solve tasks.

<chat_history>
{chat_history}
</chat_history>

# Available Tools

<tools>
{tool_descs}
</tools>

To call a function, wrap each parameter value in XML tags named after the parameter:

<function=function_name>
<first_parameter>
value
</first_parameter>
<second_parameter>
value
</second_parameter>
</function>

<IMPORTANT>
- The XML tag name MUST exactly match the parameter name defined above.
- There MUST be a line break between the opening tag and the value, and between the value and the closing tag.
- Required parameters MUST be included.
- Only provide reasoning BEFORE the function call, never after.
- If no function call is needed, answer normally without mentioning tools.
</IMPORTANT>"""

zh = """
你是一个乐于助人的AI助手，可以使用工具来解决任务。

<chat_history>
{chat_history}
</chat_history>

# 可用工具

<tools>
{tool_descs}
</tools>

调用函数时，将每个参数值用与参数名同名的XML标签包裹：

<function=函数名>
<第一个参数名>
值
</第一个参数名>
<第二个参数名>
值
</第二个参数名>
</function>

<IMPORTANT>
- XML标签名必须与参数名完全一致，不要添加前缀。
- 标签和值之间必须有换行符。
- 必须包含所有必需参数。
- 只能在函数调用之前提供推理说明，不能在之后。
- 如果不需要调用函数，请正常回答问题。
</IMPORTANT>"""
```

#### 流式响应

```python
import aiohttp
import asyncio
import json

async def streaming_example():
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": "Bearer your-api-key",
            "Content-Type": "application/json"
        }
        data = {
            "model": "qwen-plus",
            "messages": [
                {"role": "user", "content": "请写一首关于春天的诗"}
            ],
            "stream": True
        }

        async with session.post(
            "http://localhost:1337/v1/chat/completions",
            headers=headers,
            json=data
        ) as response:
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    data_str = line[6:]
                    if data_str == '[DONE]':
                        break
                    try:
                        chunk = json.loads(data_str)
                        if chunk['choices'][0]['delta'].get('content'):
                            print(chunk['choices'][0]['delta']['content'], end='', flush=True)
                    except json.JSONDecodeError:
                        continue

asyncio.run(streaming_example())
```

#### Thinking 推理增强

```python
import aiohttp
import asyncio

async def thinking_example():
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": "Bearer your-api-key",
            "Content-Type": "application/json"
        }
        data = {
            "model": "deepseek-reasoner",
            "messages": [
                {"role": "user", "content": "解释量子纠缠现象"}
            ],
            "extra_body": {
                "thinking": True  # 启用 thinking 模式
            }
        }

        async with session.post(
            "http://localhost:1337/v1/chat/completions",
            headers=headers,
            json=data
        ) as response:
            result = await response.json()
            if result.get("reasoning_content"):
                print("推理过程:", result["reasoning_content"])
            print("最终答案:", result["choices"][0]["message"]["content"])

asyncio.run(thinking_example())
```

### 请求参数说明

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `model` | string | - | 模型名称，如 `qwen-plus`、`deepseek-chat` |
| `messages` | array | - | 消息列表，格式为 `[{role, content}]` |
| `stream` | boolean | `false` | 是否启用流式输出 |
| `max_tokens` | integer | - | 最大生成 Token 数 |
| `temperature` | float | `1.0` | 温度参数，控制随机性（0-2） |
| `top_p` | float | `1.0` | 核采样参数（0-1） |
| `tools` | array | - | 工具定义列表（fncall） |
| `extra_body` | object | - | 额外参数，如 `thinking`、`search` |

---

## 🏗️ 项目结构

```
provider-v2/
├── 📁 persist/                  # 持久化数据目录
│   ├── 📁 deepseek/           # DeepSeek WASM 文件和状态
│   ├── 📁 ollama/             # Ollama 模型缓存
│   └── 📁 qwen/               # Qwen 账号状态
├── 📁 src/                     # 源代码目录
│   ├── 📁 core/               # 核心模块
│   │   ├── 📄 candidate.py    # 候选项定义
│   │   ├── 📄 config.py       # 配置管理
│   │   ├── 📄 errors.py       # 异常定义
│   │   ├── 📄 gateway.py      # 网关核心逻辑
│   │   ├── 📄 models_cache.py # 模型缓存
│   │   ├── 📄 proxy.py        # 代理配置
│   │   ├── 📄 registry.py     # 平台注册表
│   │   ├── 📄 retry.py        # 重试机制
│   │   ├── 📄 selector.py     # TAS 候选项选择器
│   │   ├── 📄 server.py       # 服务器创建
│   │   ├── 📄 tools.py        # 工具调用处理
│   │   └── 📄 watcher.py      # 文件监视器（热重载）
│   ├── 📁 platforms/          # 平台适配器
│   │   ├── 📄 base.py         # 适配器基类
│   │   ├── 📁 qwen/           # Qwen 平台
│   │   ├── 📁 deepseek/       # DeepSeek 平台
│   │   ├── 📁 glm/            # GLM 平台
│   │   ├── 📁 cerebras/       # Cerebras 平台
│   │   ├── 📁 ollama/         # Ollama 平台
│   │   ├── 📁 chatmoe/        # ChatMoe 平台
│   │   ├── 📁 cursor/         # Cursor 平台
│   │   ├── 📁 codebuddy/      # CodeBuddy 平台
│   │   └── 📁 nvidia/         # NVIDIA 平台
│   └── 📁 routes/             # 路由层
│       ├── 📄 anthropic.py    # Anthropic API 路由
│       ├── 📄 openai.py       # OpenAI API 路由
│       └── 📄 static.py       # 静态路由（健康检查等）
├── 📄 config.toml             # 配置文件
├── 📄 main.py                 # 应用入口
├── 📄 requirements.txt        # Python 依赖
├── 📄 README.md               # 项目文档
└── 📄 LICENSE                 # MIT 许可证
```

### 核心目录说明

| 目录 | 说明 |
|------|------|
| `src/core/` | 核心网关逻辑，包括配置管理、请求分发、TAS 候选项选择、文件监视热重载 |
| `src/platforms/` | 各平台适配器实现，自动发现机制，支持热重载 |
| `src/routes/` | HTTP 路由层，实现 OpenAI 和 Anthropic 兼容接口 |
| `persist/` | 平台状态持久化，如 DeepSeek WASM 文件、账号池等 |

---

## ⚙️ 配置说明

### 配置文件位置

Provider-V2 按以下顺序查找配置文件：
1. 环境变量 `CONFIG_PATH` 指定的路径
2. 项目根目录的 `config.toml`
3. 当前目录的 `config.toml`
4. 向上遍历 5 层目录查找 `config.toml`

### 完整配置示例

```toml
# Provider-V2 配置文件

# ============================================================
# 服务器配置
# ============================================================
[server]
host = "0.0.0.0"          # 监听地址
port = 1337               # 监听端口
debug = false             # 调试模式

[server.anthropic]
api_version = "2023-06-01"

[server.anthropic.model_mapping]
# 可选：自定义模型映射
# "claude-3-sonnet" = "qwen-plus"

# ============================================================
# 鉴权配置
# ============================================================
[auth]
enabled = false           # 是否启用鉴权
keys = [
    "sk-your-api-key-1",
    "sk-your-api-key-2"
]

# ============================================================
# 网关配置
# ============================================================
[gateway]
concurrent_enabled = true # 是否启用并发竞速
concurrent_count = 3      # 并发请求数
min_tokens = 10           # 选择胜者的最小 Token 阈值

# ============================================================
# 代理配置
# ============================================================
[proxy]
proxy_server = "http://127.0.0.1:40000"
proxy_enabled = false

# ============================================================
# 工具调用配置
# ============================================================
[fncall]
call_start_tag = "<function="
call_end_tag = "</function>"
tools_start_tag = "<tools>"
tools_end_tag = "</tools>"

[fncall.templates]
en = """
You are a helpful AI assistant that can interact with tools to solve tasks.

<chat_history>
{chat_history}
</chat_history>

# Available Tools

<tools>
{tool_descs}
</tools>

To call a function, wrap each parameter value in XML tags named after the parameter:

<function=function_name>
<first_parameter>
value
</first_parameter>
<second_parameter>
value
</second_parameter>
</function>

<IMPORTANT>
- The XML tag name MUST exactly match the parameter name defined above.
- There MUST be a line break between the opening tag and the value, and between the value and the closing tag.
- Required parameters MUST be included.
- Only provide reasoning BEFORE the function call, never after.
- If no function call is needed, answer normally without mentioning tools.
</IMPORTANT>"""

zh = """
你是一个乐于助人的AI助手，可以使用工具来解决任务。

<chat_history>
{chat_history}
</chat_history>

# 可用工具

<tools>
{tool_descs}
</tools>

调用函数时，将每个参数值用与参数名同名的XML标签包裹：

<function=函数名>
<第一个参数名>
值
</第一个参数名>
<第二个参数名>
值
</第二个参数名>
</function>

<IMPORTANT>
- XML标签名必须与参数名完全一致，不要添加前缀。
- 标签和值之间必须有换行符。
- 必须包含所有必需参数。
- 只能在函数调用之前提供推理说明，不能在之后。
- 如果不需要调用函数，请正常回答问题。
</IMPORTANT>"""
```

### 配置项详解

#### 服务器配置

```toml
[server]
host = "0.0.0.0"        # 监听地址，0.0.0.0 表示监听所有网卡
port = 1337             # 监听端口
debug = false           # 调试模式，开启后输出更多日志
```

#### Anthropic 兼容层配置

```toml
[server.anthropic]
api_version = "2023-06-01"  # Anthropic API 版本

[server.anthropic.model_mapping]
# 模型名称映射，将 Anthropic 模型名映射到实际平台模型
# "claude-3-sonnet" = "qwen-plus"
```

#### 鉴权配置

```toml
[auth]
enabled = true                      # 是否启用鉴权
keys = ["key1", "key2", "key3"]    # 允许的 API Key 列表
```

**鉴权方式**：
- 优先从 `Authorization: Bearer {key}` 头提取
- 失败后从 `x-api-key` 头提取
- 以下路径跳过鉴权：`/`、`/health`、`/v1/models`

#### 网关配置

```toml
[gateway]
concurrent_enabled = true    # 是否启用并发竞速
concurrent_count = 3         # 并发请求数（同时请求多少个候选项）
min_tokens = 10              # 选择胜者的最小 Token 阈值
```

**并发竞速机制**：
- 同时向 `concurrent_count` 个候选项发送请求
- 当任一候选项累积 Token 数 ≥ `min_tokens` 时立即选择该候选项
- 适用于低延迟场景，会消耗更多配额

#### 代理配置

```toml
[proxy]
proxy_server = "http://proxy.example.com:8080"  # 代理服务器地址
proxy_enabled = true                             # 是否启用代理
proxy_list_type = "whitelist"                    # 列表类型：whitelist（白名单）或 blacklist（黑名单）
proxy_urls = [                                   # URL 正则匹配列表
    ".*qwen\\.ai.*",
    ".*deepseek\\.com.*"
]
```

**说明：**
- `whitelist` 模式：仅匹配 `proxy_urls` 正则的请求走代理，其余直连
- `blacklist` 模式：匹配 `proxy_urls` 正则的请求直连，其余走代理
- 直接 IP 地址始终 bypass 代理
- `proxy_urls` 为空时：whitelist 模式全部直连，blacklist 模式全部走代理

> **注意**：代理在 `src.core.proxy` 模块导入时即生效，修改后需重启服务。

#### 工具调用配置

```toml
[fncall]
call_start_tag = "<function="      # 函数调用开始标签
call_end_tag = "</function>"       # 函数调用结束标签
tools_start_tag = "<tools>"        # 工具列表开始标签
tools_end_tag = "</tools>"         # 工具列表结束标签

[fncall.templates]
en = "..."    # 英文模板，支持 {chat_history} 和 {tool_descs} 占位符
zh = "..."    # 中文模板
```

### 配置热加载

- 修改 `config.toml` 后自动重载，无需重启服务
- 配置监听器每 2 秒检查一次变更
- 代理配置修改后需要重启服务

---

## 🔌 API 文档

### 接口概览

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/v1/models` | 获取模型列表 |
| POST | `/v1/chat/completions` | OpenAI 聊天补全 |
| POST | `/v1/messages` | Anthropic 聊天接口 |
| POST | `/v1/completions` | Legacy 文本补全 |
| POST | `/v1/embeddings` | 嵌入向量生成 |
| POST | `/v1/images/generations` | 图片生成 |
| POST | `/v1/audio/speech` | 语音合成 |
| POST | `/v1/audio/transcriptions` | 语音转录 |
| POST | `/v1/moderations` | 内容审核 |

### 接口详情

#### 健康检查

```http
GET /health
```

**响应示例：**
```json
{
  "status": "healthy",
  "timestamp": 1234567890
}
```

#### 获取模型列表

```http
GET /v1/models
Authorization: Bearer <api-key>
```

**响应示例：**
```json
{
  "object": "list",
  "data": [
    {
      "id": "qwen-plus",
      "object": "model",
      "created": 1234567890,
      "owned_by": "qwen",
      "capabilities": {
        "chat": true,
        "tools": true,
        "vision": true,
        "search": true
      }
    },
    {
      "id": "deepseek-chat",
      "object": "model",
      "created": 1234567890,
      "owned_by": "deepseek",
      "capabilities": {
        "chat": true,
        "thinking": true,
        "search": true
      }
    }
  ]
}
```

#### OpenAI 聊天补全

```http
POST /v1/chat/completions
Authorization: Bearer <api-key>
Content-Type: application/json
```

**请求示例：**
```json
{
  "model": "qwen-plus",
  "messages": [
    {"role": "system", "content": "你是一个乐于助人的助手"},
    {"role": "user", "content": "你好"}
  ],
  "stream": false,
  "max_tokens": 1024,
  "temperature": 0.7
}
```

**响应示例：**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "qwen-plus",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！我是 AI 助手，很高兴为你服务。"
      },
      "finish_reason": "stop",
      "logprobs": null
    }
  ],
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 20,
    "total_tokens": 30
  },
  "system_fingerprint": null
}
```

#### Anthropic 聊天接口

```http
POST /v1/messages
x-api-key: <api-key>
anthropic-version: 2023-06-01
Content-Type: application/json
```

**请求示例：**
```json
{
  "model": "claude-3-sonnet-20240229",
  "max_tokens": 1024,
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "stream": false
}
```

**响应示例：**
```json
{
  "id": "msg-xxx",
  "type": "message",
  "role": "assistant",
  "content": [
    {
      "type": "text",
      "text": "你好！我是 Claude，很高兴为你服务。"
    }
  ],
  "stop_reason": "end_turn",
  "stop_sequence": null,
  "usage": {
    "input_tokens": 10,
    "output_tokens": 20
  }
}
```

### 错误码说明

| HTTP 状态码 | 错误类型 | 说明 |
|------------|---------|------|
| 400 | `invalid_request_error` | 请求参数错误 |
| 401 | `authentication_error` | API Key 无效或缺失 |
| 404 | `not_found_error` | 资源不存在 |
| 429 | `rate_limit_error` | 请求频率超限 |
| 500 | `server_error` | 服务器内部错误 |
| 503 | `overloaded_error` | 服务过载，无可用候选项 |

### 完整 API 文档

启动服务后访问 `http://localhost:1337/` 通过内置 WebUI 的「模型」与「配置」选项卡查看接口清单与能力矩阵。

---

## 🧪 测试指南

### 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行特定测试文件
pytest tests/test_gateway.py

# 运行特定测试函数
pytest tests/test_gateway.py::test_dispatch

# 生成覆盖率报告
pytest --cov=src tests/
```

### 平台独立测试

每个平台都提供独立的 `test.py` 测试脚本：

```bash
# 测试 Qwen 平台
cd src/platforms/qwen
python test.py

# 测试 DeepSeek 平台
cd src/platforms/deepseek
python test.py
```

### 测试覆盖率要求

| 类型 | 最低覆盖率 |
|------|:---------:|
| 语句覆盖 | 70% |
| 分支覆盖 | 60% |
| 函数覆盖 | 80% |

---

## 📝 开发指南

### 开发状态

> ⚠️ **项目状态：Alpha 2.1 - 活跃开发中**
>
> 本项目正处于**活跃开发阶段**，代码和文档持续更新中。
>
> **贡献者请注意**：
> - 请将 Pull Request 提交到 **`dev` 分支**
> - `main` 分支仅用于稳定版本发布
> - 新功能开发请基于 `dev` 分支创建功能分支

### 开发环境搭建

```bash
# 1. Fork 并克隆项目
git clone https://github.com/你的用户名/provider-v2.git
cd provider-v2

# 2. 添加上游仓库
git remote add upstream https://github.com/nichengfuben/provider-v2.git

# 3. 切换到 dev 分支
git checkout dev

# 4. 创建功能分支
git checkout -b feature/你的功能名

# 5. 安装开发依赖
pip install -r requirements.txt
pip install pytest pytest-cov black isort mypy

# 6. 运行测试确保环境正常
pytest tests/
```

### 代码规范

- 遵循 PEP 8 代码风格
- 使用 `black` 进行格式化：`black src/`
- 使用 `isort` 进行导入排序：`isort src/`
- 使用 `mypy` 进行类型检查：`mypy src/`
- 添加类型注解
- 编写中文注释和文档字符串
- **不使用 f-string**，使用 `str.format()` 保持 Python 3.8 兼容

### Git 提交规范

采用 [Conventional Commits](https://conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Type 类型：**
| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档更新 |
| `style` | 代码格式调整 |
| `refactor` | 重构 |
| `test` | 测试相关 |
| `chore` | 构建/工具相关 |

**示例：**
```
feat(qwen): 添加 qwen3.5-122b 模型支持

- 更新 MODELS 列表
- 调整 max_tokens 限制

fix(gateway): 修复并发竞速时 token 计数错误
```

### 分支命名规范

| 分支类型 | 命名格式 | 示例 |
|----------|----------|------|
| 功能分支 | `feature/xxx` | `feature/qwen-new-model` |
| 修复分支 | `fix/xxx` | `fix/gateway-timeout` |
| 文档分支 | `docs/xxx` | `docs/api-update` |
| 重构分支 | `refactor/xxx` | `refactor/selector` |

### 添加新平台适配器

参考 [平台适配器开发指南](./src/PLATFORM_GUIDE.md) 了解如何添加新平台支持。

---

## 🗺️ 路线图

### 当前版本：v2.2.61

✅ 已完成（v2.2.61）：
- TAS 候选项自动调优重构：基于 4 个核心变量（错误时间、调用时间、token 速度、首包延迟）的自适应评分系统，持久化到 persist/gateway/，权重自动学习

✅ 已完成（v2.2.60）：
- 移除 `_format_conversation_history()` 中的 `is_webui` 检测逻辑，始终渲染 assistant tool_calls 和 tool results，所有协议所有客户端统一处理；跳过无内容的空 assistant 块

✅ 已完成（v2.2.59）：
- 修复 `dispatch()` 无 tools 时 system 消息处理：将 `role=system` 消息折叠到第一条 user 消息，确保所有平台（包括不原生支持 system role 的平台如 Qwen）都能收到系统指令

✅ 已完成（v2.2.58）：
- 修复 `create_embeddings()` 路由：改用 `get_candidates(model=, capability=)` 双重过滤，优先选择有请求模型的服务器，回退到仅 capability 过滤保证可用性

✅ 已完成（v2.2.57）：
- `DYNAMIC_DISCOVERY` 设为 `False`，Ollama 使用已重建的持久化缓存（480 台服务器），不再执行网络抓取和定时刷新

✅ 已完成（v2.2.56）：
- 修复 `background_setup()` 在 `DYNAMIC_DISCOVERY=False` 时直接 return，不再调用 `_do_refresh(force=True)` 覆盖持久化缓存（此 bug 导致 480 台服务器缓存被清空）
- `DYNAMIC_DISCOVERY` 临时恢复为 `True` 以重建被清空的缓存
- `collect_servers()` 的 `skip_network` 参数保留供未来使用

✅ 已完成（v2.2.55）：
- Ollama candidates() 运行时 embedding 检测：添加模型名关键词检测覆盖缓存中过期的 `embedding: false`
- Ollama collect_servers() 添加 skip_network 参数跳过网络抓取
- Ollama background_setup() DYNAMIC_DISCOVERY=False 时仍验证 ACCOUNTS 本地服务器

✅ 已完成（v2.2.54）：
- Ollama 动态服务器发现关闭：`DYNAMIC_DISCOVERY` 设为 `False`，Ollama 平台仅使用持久化缓存中的服务器数据，不再执行网络抓取和定时刷新

✅ 已完成（v2.2.53）：
- 代理 localhost 直连修复：`_should_proxy_url()` 新增 `_LOCAL_HOSTS` 正则匹配 `localhost` 和 `*.localhost`，启用全局代理时本地地址不再被误判为需要代理，修复 Ollama 等本地服务连接失败问题
- 日志颜色初始化修复：`_setup_handlers()` 尽早通过 tomllib 读取 `config.toml` 的 `debug.color`，确保首行日志就尊重 `color=false` 设置
- Ollama 动态发现开关：新增 `DYNAMIC_DISCOVERY` 常量，为 False 时跳过网络服务器发现和定时刷新，仅使用持久化缓存

✅ 已完成（v2.2.52）：
- Ollama embedding 支持：OllamaAdapter/OllamaClient 新增 `create_embedding()` 调用 `/api/embed`；增强 `detect_capabilities()` embedding 模型名称关键词检测；修复 `_verify_server()` URL 格式 bug；添加 `EMBED_PATH` 常量和 CAPS embedding 声明
- 日志颜色 bug 修复：`logger.py set_color()` 重建 console handler 使颜色变更立即生效；`main.py` Runner 读取 `config.toml` 决定 `CLICOLOR_FORCE`

✅ 已完成（v2.2.51）：
- 全平台合规审计与修正：18 个平台逐一对照 platform-guide 规范检查并修复偏差
- `core/constants.py` 补齐：apiairforce、caiyuesbk、cerebras、chatmoe 四个平台提取内联常量至标准 `constants.py`（BASE_URL、MODELS、CAPS 等）
- n1n 门面重写：`adapter.py` 从 783 行实现改为 5 行纯门面 re-export，`util.py` 引入 `__getattr__` 懒加载，常量统一从 `core/constants.py` 导入
- qwen 常量集中化：`BASE_URL`/`USER_AGENT` 从 `shared.py` 移至 `core/constants.py`，消除重复定义
- openaifm `util.py` 补齐 `MODELS`/`CAPS` 导出
- ollama、perplexity 清理顶层死代码兼容 shim

✅ 已完成（v2.2.48）：
- fncall 全协议健康检查：6 个协议逐一审计插值完整性、参数一致性、schema 字段完整性、prompt 结构一致性、测试覆盖；`format_tool_descs` 已支持嵌套 object/array/oneOf/anyOf/allOf/additionalProperties 递归渲染（max_depth=4），无需改动；上游 tools 透传链路（openai/anthropic/gateway）完整无裁剪
- original 协议 `render_prompt` 修复：`loop_warning` 参数此前被静默丢弃，现以 `<loop_warning>` XML 包装注入 prompt；该参数是工具调用死循环安全告警，所有协议都应无条件渲染

✅ 已完成（v2.2.47）：
- nous fncall 协议 `render_prompt` 修复：`'{tool_descs}\n\n'` 由普通字符串字面量改为拼接，工具定义（参数名/类型/必填/schema）现可正确注入 prompt；默认配置 `qwen = "nous"` 下所有工具调用请求此前均命中此 bug，模型只能靠报错摸索调用方式

✅ 已完成（v2.2.46）：
- aitianhu2 SSE 解析重写：移植上游 `_V1DeltaAccumulator`（228 行状态机），支持短键/长键双向规范化、字段继承、多通道并行、完整 JSONPatch op 集（add/replace/append/patch/truncate/remove）。**根因修复**：gpt-5.5 上游使用长键或省略重复字段时，旧解析器静默丢弃整段 antml 标签导致工具调用失效
- `openai.py::_stream_chat` 标签检测改用 `proto.detect_start(buffer)`，兼容 `<antml:function_calls >` / 带属性等变体；不支持该方法的协议回退到严格 `trigger_tags` 匹配
- 路由守卫放宽：delta 事件只要含 `o`/`op`/`p`/`path`/`v`/`value`/`c`/`channel` 任一即交状态机，仅有 `v` 靠继承的 delta 不再被丢弃

✅ 已完成（v2.2.45）：
- fncall `record_prompt` 字段激活：原字段定义在 `FncallCfg` 但全代码未读取，现作为 `print_prompt` 别名生效，两者任一为 `true` 都会把注入后的 prompt 落盘到 `logs/prompts/<uuid7>.txt`

✅ 已完成（v2.2.44）：
- antml fncall 解析：`_BLOCK_RE` 放宽以容忍 `<antml:function_calls >` / 带属性 / 换行等变体；`detect_start()` 同步放宽前缀匹配
- 非流式 chat completions：即使网关未产出 `tool_calls` 块（请求未带 `tools` 或流式解析器漏掉），也对整段 content 再跑一次协议解析提取 tool_calls
- aitianhu2 `chat.py::stream()` 增加 429 限流感知：解析 `please wait N seconds` 并抛结构化 `RateLimitError`；`client.py::complete()` 重试循环尊重上游冷却秒数
- aitianhu2 `/conversation` 旧端点 fallback 补齐 `openai-sentinel-chat-requirements-token` 头

✅ 已完成（v2.2.43）：
- aitianhu2 多账号重构：每个 Account → 独立 `aiohttp.ClientSession` + cookie jar + device_id + 持久化条目；N 账号暴露 N 个 Candidate，限速失败时自动切换账号
- aitianhu2 动态 `chatgpt-account-id`：`fetch_account_id()` 从 `/backend-api/accounts/check/v4-2023-04-27` 按 plan 优先级（team/plus/pro/business/enterprise）挑选；每个账号独立缓存 22h
- aitianhu2 持久化 schema 升级：`state.json` 形如 `{accounts: {...}, carids: {...}}`；旧扁平格式按 `api_key_hint` 透明迁移
- aitianhu2 CRITICAL bug 修复：`/f/conversation` 500 / 连接异常回退到旧 `/conversation` 端点；SSE 解析增加旧格式 `data["message"]`；`resolve_image` URL 检查放宽为 `not startswith("http")`
- aitianhu2 models fetch 移除多余 `chatgpt-account-id` header
- 所有服务（sentinel/chat/upload）的 `chatgpt-account-id` 改为方法参数，由账号级 `account_id` 驱动

✅ 已完成（v2.2.42）：
- `[gateway].group_list` 语义修正：名单决定"谁允许并发竞速"，不决定"谁能路由"；非名单内平台仍可路由但请求强制单发（n=1），竞速池需 ≥ 2 才启用并发

✅ 已完成（v2.2.41）：
- `[gateway]` 新增 `group_list_type`（whitelist/blacklist）+ `group_list`：并发竞速平台黑白名单
- `[platforms_proxy]` 新增 `group_list_type`：让 `enabled_platforms` 在白名单（默认，向后兼容）与黑名单之间切换
- Qwen / DeepSeek 代理切换统一走 `platforms_proxy.is_platform_enabled()`
- runtime 摘要导出新字段

✅ 已完成（v2.2.40）：
- `_auth_middleware` 移除 `/health` 与 `/v1/models` 的无条件放行：必须持有 `pv2_session` Cookie 或有效 Bearer/X-API-Key 才能访问；浏览器无凭证自动 302 到 `/login`，API 客户端 JSON 401

✅ 已完成（v2.2.39）：
- `_auth_middleware` 不再放行 `/`：未登录浏览器访问管理面板自动 302 到 `/login`，登录后 Cookie 驱动回到 `/`

✅ 已完成（v2.2.38）：
- WebUI 新增 `/login` 表单页（自包含内联 CSS，light/dark 自适应）
- `_auth_middleware` 接受 `pv2_session` Cookie 作为 Bearer 等价凭证
- `_auth_middleware` 放行 `/login` 与 `/static/`，解决未登录时 CSS/JS 401 导致 UI 风格丢失
- 浏览器访问受保护路由时无凭证自动 302 到 `/login`，API 客户端仍保持 JSON 401 协议
- 新增 `/logout` 路由清除 `pv2_session` Cookie

✅ 已完成（v2.2.37）：
- aitianhu2 认证失败 / 401 重认证时强制刷新 carids（清空模块缓存 + 绕过 48h 阈值）
- aitianhu2 落地页 200 但 carids 正则未匹配时记录页面片段便于排查

✅ 已完成（v2.2.36）：
- aitianhu2 流式对话：`system_hints` 非空时透传 `client_prepare_state: "success"`
- aitianhu2 流式对话：`prepare` 响应的 `conduit_token` 注入 stream `x-conduit-token` 头

✅ 已完成（v2.2.35）：
- aitianhu2 平台对齐上游：动态 carids 抓取 + 48h 刷新 + 持久化
- aitianhu2 图像生成透传 `system_hints=["picture_v2"]`
- aitianhu2 补全 sentinel/upload 的 `Authorization: Bearer` 头
- aitianhu2 认证加固：200 响应 `wrong-email-credentials` / 登录页检测
- aitianhu2 会话 22h 软刷新 + 24h 硬过期双保险

✅ 已完成（v2.2.34）：
- 非 WebUI 客户端一律不渲染工具调用历史

✅ 已完成（v2.2.33）：
- agent CLI 消息跳过渲染工具调用历史，避免双重渲染

✅ 已完成（v2.2.32）：
- 修复 LLM 工具调用死循环：历史中工具调用格式与协议指令格式不一致

✅ 已完成（v2.2.31）：
- 修复自动更新检查 Path 未导入导致的 NameError

✅ 已完成（v2.2.30）：
- 修复聊天发送按钮不可见：Tailwind backgroundColor 缺少 accent 定义

✅ 已完成（v2.2.29）：
- 修复 Anthropic 路由协议硬编码导致工具调用标签泄漏到客户端

✅ 已完成（v2.2.28）：
- 修复助手消息编辑按钮在浅色背景上不可见的问题

✅ 已完成（v2.2.27）：
- 消息编辑对话框按钮统一为「确定」+「取消」

✅ 已完成（v2.2.26）：
- 修复 qwen 平台 enabled_platforms=[] 时仍能使用代理的 bug

✅ 已完成（v2.2.25）：
- WebUI CustomDropdown 组件添加搜索筛选功能，选项超过5项时自动显示搜索框，列表最多显示5项

✅ 已完成（v2.2.24）：
- 废除 `/docs` 端点与 `/webui` 页面路由，根路径 `/` 直接服务内置 WebUI
- 静态资源前缀由 `/webui/static/` 简化为 `/static/`
- 删除 `DocLink`/`DocSection`、`build_doc_sections`、`render_page`、`render_webui` 等未使用的兼容导出
- 鉴权跳过集合仅保留 `/`、`/health`、`/v1/models`

✅ 已完成（v2.2.11）：
- 新增自动更新功能（autoupdate.enabled/branch/interval，git pull + exit 42 自动重启）

✅ 已完成（v2.2.10）：
- 修复工具调用 fncall 协议不一致问题（_single 缺少注入、_race 缺少 fncall_lang 参数、FncallStreamParser 协议错误）

✅ 已完成（v2.2.5）：
- 修复 antml 协议 prompt 缺少 Function Invocation Syntax
- 延迟 `_build_param_schema_index` 构建至确认有 function_calls 块后
- 修复 ServerCfg 缺少 version 字段
- 消除 silent `except Exception: pass` 模式（10 处）
- 补全缺失的 `from __future__ import annotations`（4 文件）
- 补全核心函数/类 docstring

✅ 已完成（v2.2.1）：
- 修复平台 accounts 模块导入路径（遵循平台开发规范）

✅ 已完成（v2.2.0）：
- 核心网关架构重构
- OpenAI 和 Anthropic API 兼容
- 11+ 平台适配器
- 并发竞速机制
- 工具调用（fncall）XML 模板可配置
- 配置热加载
- 文件监视热重载（平台代码热重载）
- TAS 选择器（Thompson Sampling + 冷却）
- 错误类命名修复（RequestTimeoutError）
- 热重载 BUG 修复（清理 sys.modules）

### v2.1（计划中）

- [ ] 更多平台适配器
- [ ] 请求缓存机制
- [ ] 负载均衡策略优化
- [ ] 更完善的监控指标
- [ ] WebSocket 实时通信支持

### v2.2（规划中）

- [ ] 分布式部署支持
- [ ] 请求限流和熔断
- [x] 可视化控制台
- [ ] 插件化架构

### 长期目标

- 成为最全面的 AI 模型网关
- 支持 30+ AI 平台
- 毫秒级延迟
- 99.99% 可用性

📢 欢迎在 [Issues](https://github.com/nichengfuben/provider-v2/issues) 中提出功能建议！

---

## ❓ 常见问题

<details>
<summary><b>Q1: 启动时提示 "ModuleNotFoundError: No module named 'xxx'" 怎么办？</b></summary>

**问题描述**：运行 `python main.py` 时提示缺少依赖模块

**解决方案：**
```bash
# 确保已安装所有依赖
pip install -r requirements.txt

# 或使用虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\activate
pip install -r requirements.txt
```
</details>

<details>
<summary><b>Q2: 如何配置代理服务器？</b></summary>

**解决方案：**

编辑 `config.toml` 文件：
```toml
[proxy]
proxy_server = "http://proxy.example.com:8080"
proxy_enabled = true
proxy_list_type = "blacklist"
proxy_urls = []
```

> **注意**：代理配置在 `src.core.proxy` 模块导入时即生效，修改后需重启服务。
</details>

<details>
<summary><b>Q3: 并发竞速模式下如何控制配额消耗？</b></summary>

**解决方案：**

编辑 `config.toml` 调整参数：
```toml
[gateway]
concurrent_enabled = true    # 启用并发竞速
concurrent_count = 2         # 减少并发数（降低配额消耗）
min_tokens = 50              # 增加 Token 阈值（减少早期切换）
```

**建议：**
- 配额紧张时设置 `concurrent_count = 1`（禁用竞速）
- 低延迟优先时设置 `concurrent_count = 3`，`min_tokens = 10`
</details>

<details>
<summary><b>Q4: DeepSeek 平台提示 "WASM 下载失败" 怎么办？</b></summary>

**可能原因：**
1. 代理配置不正确
2. 网络连接问题
3. `persist/deepseek/` 目录无写入权限

**排查步骤：**
```bash
# 检查目录权限
ls -la persist/deepseek/

# 手动创建目录
mkdir -p persist/deepseek/

# 检查代理配置
# 确保 config.toml 中 [proxy] 配置正确
```

**WASM 文件位置：**
- 保存路径：`persist/deepseek/sha3_wasm_bg.7b9ca65ddd.wasm`
- 自动下载 URL：`https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm`
- 更新检查频率：24 小时
</details>

<details>
<summary><b>Q5: 如何添加新的平台适配器？</b></summary>

**解决方案：**

1. 在 `src/platforms/` 下创建新目录
2. 创建 `adapter.py` 实现 `PlatformAdapter` 接口
3. 创建 `accounts.py` 管理账号
4. 创建 `client.py` 实现 HTTP 请求
5. 创建 `util.py` 实现工具函数

详细步骤请参考 [平台适配器开发指南](./src/PLATFORM_GUIDE.md)。
</details>

<details>
<summary><b>Q6: 工具调用（fncall）中 XML 标签格式有何要求？</b></summary>

**解决方案：**

Provider-V2 要求模型返回的 XML 遵循以下格式：

```xml
<function=函数名>
<参数名1>
参数值
</参数名1>
<参数名2>
参数值
</参数名2>
</function>
```

**关键要求：**
- XML 标签名必须与工具定义中的参数名完全一致
- 标签和值之间**必须**有换行符
- 支持多行参数（如代码块），换行符会被保留
- 必须包含所有必需参数

如果模型没有按此格式返回，Provider-V2 将无法正确解析工具调用。
</details>

<details>
<summary><b>Q7: 配置文件修改后不生效怎么办？</b></summary>

**解决方案：**

```bash
# 方法一：等待自动重载（最多延迟 2 秒）

# 方法二：重启服务
# Ctrl+C 停止，然后重新运行
python main.py

# 方法三：检查配置文件语法
python -c "import tomllib; print(tomllib.load(open('config.toml', 'rb')))"
```

**代理配置需要重启**：
- `config.toml` 中的 `[proxy]` 配置在模块导入时生效
- 修改代理配置后必须重启服务
</details>

<details>
<summary><b>Q8: 如何禁用鉴权？</b></summary>

**解决方案：**

编辑 `config.toml`：
```toml
[auth]
enabled = false  # 设置为 false
keys = []
```

**跳过鉴权的路径**：
- `/`
- `/health`
- `/v1/models`
</details>

### 更多问题

- 🐛 在 [Issues](https://github.com/nichengfuben/provider-v2/issues) 中报告问题
- 💬 加入社区讨论

---

## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献

1. **报告 Bug**：通过 [Issues](https://github.com/nichengfuben/provider-v2/issues) 提交详细报告
2. **功能建议**：在 [Discussions](https://github.com/nichengfuben/provider-v2/discussions) 中提出想法
3. **代码贡献**：提交 Pull Request 到 **`dev` 分支**
4. **文档改进**：帮助完善 README 和 API 文档
5. **分享经验**：在社区分享使用心得

### Pull Request 流程

```bash
# 1. 确保在 dev 分支基础上创建
git checkout dev
git pull upstream dev
git checkout -b feature/your-feature

# 2. 提交更改
git add .
git commit -m "feat: add your feature"

# 3. 运行测试
pytest tests/

# 4. 推送到你的 fork
git push origin feature/your-feature

# 5. 创建 Pull Request（目标分支：dev）
```

### 代码规范检查

```bash
# 格式化代码
black src/

# 排序导入
isort src/

# 类型检查
mypy src/

# 运行测试
pytest tests/
```

### 贡献者名单

感谢所有贡献者！

<a href="https://github.com/nichengfuben/provider-v2/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=nichengfuben/provider-v2" />
</a>

---

## 📜 许可证

本项目采用 [MIT 许可证](./LICENSE)。

```
MIT License

Copyright (c) 2026 Provider-V2 Contributors

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
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 📮 联系方式

- **作者**：nightpoem
- **邮箱**：nichengfuben@outlook.com
- **主页**：https://github.com/nichengfuben/provider-v2

### 技术支持

- 📧 技术支持邮箱：nichengfuben@outlook.com
- 🐛 [问题反馈](https://github.com/nichengfuben/provider-v2/issues)
- 💬 [社区讨论](https://github.com/nichengfuben/provider-v2/discussions)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star！**

Made with ❤️ by [nightpoem](https://github.com/nichengfuben)

</div>
