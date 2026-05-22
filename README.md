# Qwen API Server

> 基于 Qwen 网页接口的 OpenAI / Anthropic 兼容 API 代理服务器，支持多账号轮询、公平调度、XML 函数调用

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## <span>📋</span> 目录

- [项目简介](#-项目简介)
- [功能特性](#-功能特性)
- [快速开始](#-快速开始)
- [安装指南](#-安装指南)
- [使用说明](#-使用说明)
- [项目结构](#-项目结构)
- [配置说明](#-配置说明)
- [API 文档](#-api-文档)
- [测试指南](#-测试指南)
- [构建独立二进制](#-构建独立二进制)
- [常见问题](#-常见问题)
- [联系方式](#-联系方式)

---

## <span>🎯</span> 项目简介

本项目是一个 **Qwen API 代理服务器**，通过将 Qwen 网页版接口封装为标准的 OpenAI / Anthropic 兼容 API，使任何支持 OpenAI 格式的应用程序（如 OpenWebUI、Chatbot UI、LangChain 等）都能直接使用 Qwen 的强大能力。

### 核心架构

系统采用 **server-client** 双层架构：

- **Server 层** (`qwen_server.py`)：基于 FastAPI，接收外部 OpenAI / Anthropic 格式请求，通过 FIFO 公平调度器分发
- **Client 层** (`qwen_client.py`)：管理多个 Qwen 账号，与 Qwen 网页接口通信，实现 **Track-and-Stop 多臂赌博机算法**进行最优账号选择

### 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.104+, Uvicorn |
| HTTP 客户端 | aiohttp 3.9+, httpx 0.25+ |
| 数据校验 | Pydantic 2.0+ |
| WebSocket | websockets 12.0+ |
| 图像处理 | Pillow 10.0+ |
| 构建工具 | Nuitka (跨平台编译) |
| 部署方式 | Vercel Serverless, 独立二进制 |

### 为什么选择本项目

| 特性 | 本方案 | 其他方案 |
|------|--------|----------|
| API 兼容性 | OpenAI + Anthropic + OpenWebUI | 通常仅 OpenAI |
| 多账号管理 | 1000+ 账号智能调度 | 手动切换 |
| 调度算法 | Track-and-Stop 最优选择 + FIFO 公平队列 | 简单轮询 |
| 函数调用 | Nous XML 格式 | 有限支持 |
| 媒体生成 | 图像、视频、TTS、嵌入 | 部分支持 |
| 部署方式 | 二进制 + Vercel + 源码 | 通常仅源码 |

---

## <span>✨</span> 功能特性

### 核心功能

- ✅ **OpenAI 兼容 API** — 完整支持 `/v1/chat/completions`、`/v1/models`、`/v1/embeddings` 等标准端点
- ✅ **Anthropic 兼容 API** — 支持 `/v1/messages`、文件上传 / 下载、token 计数等 Anthropic 格式
- ✅ **多账号智能调度** — Track-and-Stop 算法自动选择最优账号，FIFO 公平队列避免饥饿
- ✅ **Nous XML 函数调用** — 支持 `<function=name>args</function>` 格式的函数调用和工具使用
- ✅ **OpenWebUI 模型标识** — 支持能力标识（如 `qwen3-coder-plus::text`、`qwen3-coder-plus::image`）
- ✅ **流式输出** — 所有聊天端点支持 SSE 流式响应

### 高级功能

- 🔧 **图像生成** — 支持 flux、turbo、sana、zimage 等模型
- 🔧 **视频生成** — 支持 16:9、9:16、1:1 多种比例
- 🔧 **语音合成 (TTS)** — 文本转语音
- 🔧 **语音识别** — 转录和翻译
- 🔧 **深度研究** — Deep Research 模式
- 🔧 **学习模式** — Learn 模式
- 🔧 **Artifacts** — 代码 / 文档生成
- 🔧 **图像编辑** — 图像编辑端点
- 🔧 **文件管理** — 完整的 Anthropic 风格文件上传 / 下载 API
- 🔧 **断点续传** — 支持请求中断后恢复
- 🔧 **Cookie 持久化** — 会话状态自动保存
- 🔧 **大文本自动转文件** — 超过阈值自动转为文件引用
- 🔧 **生产级监控** — `/v1/metrics`、`/v1/status` 端点提供实时指标

---

## <span>🚀</span> 快速开始

### 环境要求

- Python >= 3.9
- pip >= 21.0
- Git >= 2.30

### 30 秒快速体验

```bash
# 克隆项目
git clone https://github.com/nichengfuben/provider-v2.git
cd provider-v2

# 安装依赖
pip install -r requirements.txt

# 配置账号（见下方安装指南）

# 启动服务器（默认端口 13280）
python qwen_server.py
```

### 验证安装

访问 http://localhost:13280/docs 查看自动生成的 API 文档。

使用 curl 快速测试：

```bash
curl http://localhost:13280/v1/models
```

---

## <span>📦</span> 安装指南

### 前置准备：配置账号

在项目根目录创建 `qwen_accounts.py` 文件：

```python
ACCOUNTS = [
    <{"email": "your-email@example.com", "password": "your-password"}>,
    # 可添加更多账号
]
```

> ⚠️ 该文件已在 `.gitignore` 中排除，不会被提交到仓库。

### 方式一：源码安装

```bash
# 1. 克隆仓库
git clone https://github.com/nichengfuben/provider-v2.git
cd provider-v2

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置账号（见上方前置准备）

# 4. 启动服务器
python qwen_server.py
```

### 方式二：预编译二进制

从 GitHub Releases 下载对应平台的可执行文件：

**Windows：**
```powershell
.\qwen-server.exe
```

**Linux / macOS：**
```bash
chmod +x qwen-server-linux  # 或 qwen-server-macos
./qwen-server-linux
```

### 方式三：Vercel 部署

项目已配置 `vercel.json`，可直接部署到 Vercel：

```bash
# 安装 Vercel CLI
npm i -g vercel

# 部署
vercel
```

> 数据目录会自动重定向到 `/tmp/data/`。

---

## <span>💻</span> 使用说明

### 基础用法 - 聊天补全

```bash
curl http://localhost:13280/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '<{"model": "qwen3-coder-plus", "messages": [{"role": "user", "content": "请用一句话解释什么是机器学习"}], "stream": false}'
```

### 流式输出

```bash
curl http://localhost:13280/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '<{"model": "qwen3-coder-plus", "messages": [{"role": "user", "content": "你好"}], "stream": true}'
```

### Python 客户端示例

```python
import requests

resp = requests.post(
    "http://localhost:13280/v1/chat/completions",
    json={
        "model": "qwen3-coder-plus",
        "messages": [{"role": "user", "content": "写一个 Python 快速排序函数"}],
        "temperature": 0.7,
        "max_tokens": 500
    }
)
print(resp.json()["choices"][0]["message"]["content"])
```

### 多轮对话

```python
messages = [
    <{"role": "user", "content": "什么是 Python？"}>,
    <{"role": "assistant", "content": "Python 是一种广泛使用的高级编程语言..."}>,
    <{"role": "user", "content": "它有哪些特点？"}>
]

resp = requests.post("http://localhost:13280/v1/chat/completions",
    json=<{"model": "qwen3-coder-plus", "messages": messages}>
)
```

### 可用模型

**文本模型：**
- `qwen3-coder-plus`（默认）
- `qwen3-max`
- `qwen3-235b-a22b`
- `qwen3.5-plus`
- `qwq-32b`
- `qwen-max-latest`
- 等 20+ 模型

**图像模型：**
- `flux`（默认）
- `turbo`
- `sana`
- `zimage`

### 配置参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | string | `qwen3-coder-plus` | 模型名称 |
| `messages` | array | - | 消息列表 |
| `stream` | boolean | `false` | 是否启用流式输出 |
| `temperature` | number | `0.7` | 温度参数 (0-2) |
| `max_tokens` | number | - | 最大输出 token 数 |
| `top_p` | number | `1.0` | Top-p 采样 |

### 完整示例

查看 `qwen_example.py` 获取更多使用示例。

---

## <span>🏗️</span> 项目结构

```
provider-v2/
├── 📁 script/                   # 构建和分发脚本
│   ├── 📁 qwen/                # Qwen 模块副本
│   └── 📁 ollama/              # Ollama 模块
├── 📁 api/                     # Vercel Serverless 入口
│   └── 📄 index.py
├── 📁 data/                    # 运行时数据（gitignored）
├── 📄 qwen_server.py           # 主服务器 (~5200 行)
├── 📄 qwen_client.py           # 账号客户端 (~7000 行)
├── 📄 qwen_util.py             # 工具模块 (~3600 行)
├── 📄 qwen_accounts.py         # 账号配置（gitignored）
├── 📄 ollama_server.py         # Ollama 服务器 (~2600 行)
├── 📄 proxy.py                 # HTTP 代理注入模块
├── 📄 net.py                   # 透明网络代理模块
├── 📄 test.py                  # 性能测试套件
├── 📄 build.py                 # Nuitka 构建脚本
├── 📄 list_compressor.py       # 数据压缩工具
├── 📄 requirements.txt         # Python 依赖
├── 📄 vercel.json              # Vercel 配置
└── 📄 .github/workflows/       # CI/CD 配置
```

### 核心文件说明

| 文件 | 说明 |
|------|------|
| `qwen_server.py` | 主 FastAPI 服务器，暴露 OpenAI / Anthropic API |
| `qwen_client.py` | 管理 Qwen 账号，实现多臂赌博机算法选择最优账号 |
| `qwen_util.py` | 模型定义、XML 函数调用模板、数据存储类、`ServerConfig` |
| `ollama_server.py` | Ollama 兼容 API 服务器，动态模型发现 |
| `proxy.py` | 全局 HTTP 代理注入（import 即生效） |
| `api/index.py` | Vercel 入口，自动重定向 data/ 到 /tmp/data/ |

---

## <span>⚙️</span> 配置说明

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `SCHED_CHAT_CONCURRENT` | `50` | 聊天并发请求数 |
| `SCHED_CHAT_QUEUE` | `500` | 聊天队列最大长度 |
| `SCHED_CHAT_TIMEOUT` | `120` | 聊天请求超时（秒） |
| `SCHED_MEDIA_CONCURRENT` | `10` | 媒体并发请求数 |
| `SCHED_MEDIA_QUEUE` | `100` | 媒体队列最大长度 |
| `SCHED_MEDIA_TIMEOUT` | `180` | 媒体请求超时（秒） |
| `SCHED_AUX_CONCURRENT` | `20` | 辅助并发请求数 |
| `SCHED_AUX_QUEUE` | `200` | 辅助队列最大长度 |
| `SCHED_AUX_TIMEOUT` | `300` | 辅助请求超时（秒） |
| `SPECIAL_CODE_MODE` | `false` | 启用 code_interpreter 特殊处理 |

### 使用示例

```bash
# 设置更高的并发
SCHED_CHAT_CONCURRENT=100 SCHED_MEDIA_CONCURRENT=20 python qwen_server.py

# 启用代码解释器特殊模式
SPECIAL_CODE_MODE=true python qwen_server.py
```

### 服务器配置

服务器配置定义在 `qwen_util.py` 的 `ServerConfig` 类中：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `13280` | 监听端口 |
| `DEBUG` | `True` | 调试模式 |

### 客户端配置

客户端配置定义在 `qwen_client.py` 的 `ClientConfig` 类中：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `DEFAULT_MODEL` | `qwen3-coder-plus` | 默认文本模型 |
| `DEFAULT_IMAGE_MODEL` | `flux` | 默认图像模型 |

---

## <span>🔌</span> API 文档

### 接口概览

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/v1/models` | 获取可用模型列表 |
| GET | `/v1/models/:id` | 获取模型详情 |
| POST | `/v1/chat/completions` | 聊天补全（OpenAI） |
| POST | `/v1/messages` | 消息（Anthropic） |
| POST | `/v1/responses` | 响应（Anthropic 风格） |
| POST | `/v1/images/generations` | 图像生成 |
| POST | `/v1/images/edits` | 图像编辑 |
| POST | `/v1/videos` | 视频生成 |
| POST | `/v1/audio/speech` | 语音合成 |
| POST | `/v1/audio/transcriptions` | 语音转录 |
| POST | `/v1/audio/translations` | 语音翻译 |
| POST | `/v1/embeddings` | 嵌入向量 |
| POST | `/v1/research` | 深度研究 |
| POST | `/v1/learn` | 学习模式 |
| POST | `/v1/artifacts` | Artifacts 模式 |
| POST | `/v1/files` | 文件上传 |
| GET | `/v1/files/:id/content` | 文件内容 |
| GET | `/v1/metrics` | 服务器指标 |
| GET | `/v1/status` | 服务器状态 |
| GET | `/health` | 健康检查 |
| GET | `/docs` | Swagger API 文档 |

### 聊天补全端点详情

```http
POST /v1/chat/completions
Content-Type: application/json
```

**请求体：**
```json
<{
  "model": "qwen3-coder-plus",
  "messages": [
    <{"role": "system", "content": "你是一个有帮助的助手"}>,
    <{"role": "user", "content": "解释一下量子计算"}>
  ],
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false
}>
```

**响应示例：**
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "created": 1234567890,
  "model": "qwen3-coder-plus",
  "choices": [<{
    "index": 0,
    "message": <{
      "role": "assistant",
      "content": "量子计算是一种..."
    }>,
    "finish_reason": "stop"
  }>],
  "usage": <{
    "prompt_tokens": 15,
    "completion_tokens": 100,
    "total_tokens": 115
  }>
}
```

### 函数调用格式

本服务器使用 **Nous XML** 格式进行函数调用：

```xml
<function=weather><{"location": "Beijing"}></function>
<function_call_result>晴天，25°C</function_call_result>
```

> 提示词模板会自动注入到系统提示中，模型会自动学会使用此格式调用工具。

### OpenWebUI 能力标识

支持在模型名后添加能力标识：

| 标识 | 说明 |
|------|------|
| `::text` | 文本对话 |
| `::image` | 图像理解 |
| `::video` | 视频生成 |
| `::tts` | 语音合成 |
| `::stt` | 语音识别 |

示例：`qwen3-coder-plus::text`

---

## <span>🧪</span> 测试指南

### 运行性能测试

```bash
python test.py
```

测试套件包含：
- 短回答延迟测试
- 中等回答性能测试
- 长回答吞吐量测试
- 代码生成速度测试
- 复杂推理能力测试

### 手动测试

```bash
# 健康检查
curl http://localhost:13280/health

# 模型列表
curl http://localhost:13280/v1/models

# 服务器状态
curl http://localhost:13280/v1/status

# 服务器指标
curl http://localhost:13280/v1/metrics
```

---

## <span>🔨</span> 构建独立二进制

### 使用构建脚本

```bash
# 全平台构建
python build.py

# 清理构建产物
python build.py --clean
```

### 平台特定构建

**Windows：**
```powershell
.\build.bat
```

**Linux / macOS：**
```bash
./build.sh
```

### CI/CD

项目使用 GitHub Actions 自动构建：

- 推送 `v*` 标签时触发
- 构建 Windows、Linux、macOS 三个平台的二进制文件
- 自动创建 GitHub Release

```bash
# 创建发布标签
git tag v1.0.0
git push origin v1.0.0
```

---

## <span>❓</span> 常见问题

<details>
<summary><b>Q1: 启动时报错「未找到账号列表」怎么办？</b></summary>

**原因：** 缺少 `qwen_accounts.py` 文件。

**解决方案：** 在项目根目录创建该文件，参考上方「前置准备：配置账号」章节。
</details>

<details>
<summary><b>Q2: 如何修改服务器端口？</b></summary>

编辑 `qwen_util.py`，修改 `ServerConfig.PORT` 值，然后重启服务器。
</details>

<details>
<summary><b>Q3: 支持哪些 OpenAI SDK？</b></summary>

本服务器完全兼容 OpenAI 格式的 SDK，包括但不限于：
- OpenAI Python SDK
- OpenAI Node.js SDK
- LangChain
- OpenWebUI
- 任何使用 `/v1/chat/completions` 格式的应用
</details>

<details>
<summary><b>Q4: 如何提高并发性能？</b></summary>

通过环境变量调整调度器配置：
```bash
SCHED_CHAT_CONCURRENT=100 SCHED_MEDIA_CONCURRENT=20 python qwen_server.py
```
</details>

<details>
<summary><b>Q5: 如何在 Vercel 上部署？</b></summary>

1. Fork 本仓库
2. 在 Vercel 中导入项目
3. 设置环境变量（如需要）
4. 部署

> ⚠️ 注意：Vercel Serverless 环境有执行时长限制（默认 10 秒，Pro 用户 60 秒），长时间运行的请求可能会超时。
</details>

<details>
<summary><b>Q6: 数据目录可以自定义路径吗？</b></summary>

可以通过设置 `DATA_DIR` 环境变量来自定义数据目录：
```bash
DATA_DIR=/path/to/data python qwen_server.py
```
</details>

### 更多支持

- 📖 查看 API 文档：http://localhost:13280/docs
- 💬 [社区讨论](https://github.com/nichengfuben/provider-v2/discussions)
- 🐛 [问题反馈](https://github.com/nichengfuben/provider-v2/issues)

---

## <span>📮</span> 联系方式

- **作者**：nichengfuben
- **邮箱**：[nichengfuben@outlook.com](mailto:nichengfuben@outlook.com)
- **主页**：https://github.com/nichengfuben/provider-v2

### 技术支持

- 📧 技术支持邮箱：[nichengfuben@outlook.com](mailto:nichengfuben@outlook.com)
- 🐛 [问题反馈](https://github.com/nichengfuben/provider-v2/issues)
- 💬 [社区讨论](https://github.com/nichengfuben/provider-v2/discussions)

---

<div align="center">

**如果这个项目对你有帮助，请给一个 ⭐️ Star！**

Made with ❤️ by [nichengfuben](https://github.com/nichengfuben)

</div>
