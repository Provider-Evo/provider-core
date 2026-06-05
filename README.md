# Provider (Classical)

> 重构前的历史版本：两个独立的 FastAPI 代理服务器（Qwen 网页接口 + Ollama 本地模型），提供 OpenAI / Anthropic 兼容 API。
>
> **本分支 `classical` 为冻结的历史快照，仅供对比与回退参考，不再接受更新。** 日常使用与开发请切换到 `main` 或 `dev` 分支。

![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688.svg)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)

## 分支说明

| 分支 | 定位 | 说明 |
|------|------|------|
| **main** | 稳定发布 | 经过验证的稳定版本，适合生产部署与日常使用 |
| **dev** | 活跃开发 | 相比 main 包含更多最新更改与功能，但可能不够稳定 |
| **classical** | 历史快照 | 重构前的冻结版本（即本分支），仅供对比与回退参考 |

## 项目简介

本目录保留的是 Provider 在大规模重构为 aiohttp 多平台架构之前的形态。它由**两个相互独立的 FastAPI 服务器**组成：

- `qwen_server.py` — 把 Qwen 网页接口封装为 OpenAI / Anthropic 兼容 API，支持多账号轮询、公平调度、Nous XML 函数调用
- `ollama_server.py` — 把本地 Ollama 服务封装为 OpenAI / Anthropic 兼容 API，支持动态模型发现

两个服务器共享 `qwen_util.py`、`proxy.py`、`net.py`、`list_compressor.py` 等基础模块，但**不共享进程**，需要分别启动。

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI 0.104+、Uvicorn 0.24+ |
| HTTP 客户端 | aiohttp 3.9+、httpx 0.25+ |
| 数据校验 | Pydantic 2.0+ |
| WebSocket | websockets 12.0+ |
| 图像处理 | Pillow 10.0+ |
| 构建工具 | Nuitka（跨平台编译为独立二进制） |
| 部署方式 | Vercel Serverless（仅 qwen_server）+ 独立二进制 |

## 文件清单

本分支实际包含以下文件（不含 `data/` 等运行时产物）：

```
classical/
├── qwen_server.py         # Qwen 网页接口代理服务器（FastAPI，~5200 行）
├── qwen_client.py         # Qwen 账号客户端（多臂赌博机调度）
├── qwen_util.py           # 共享配置 ServerConfig / ClientConfig、XML fncall 模板、数据类
├── qwen_accounts.py       # Qwen 账号列表（已 gitignore）
├── qwen_login.py          # Qwen 登录辅助
├── qwen_example.py        # 调用示例
├── ollama_server.py       # Ollama 代理服务器（FastAPI，~2700 行，独立启动）
├── proxy.py               # 全局 HTTP 代理注入（import 即生效）
├── net.py                 # 透明网络代理模块
├── list_compressor.py     # 列表压缩工具
├── requirements.txt       # Python 依赖
├── build.py               # Nuitka 构建脚本（构建 qwen_server）
├── build.bat / build.sh   # 平台特定构建入口
├── api/index.py           # Vercel Serverless 入口（将 data/ 重定向到 /tmp/data/）
├── script/                # 打包/分发用的脚本副本
│   ├── qwen/              #   qwen 模块副本
│   ├── ollama/            #   ollama 模块副本（ollama_client、ollama_util）
│   ├── servers.py
│   ├── proxy.py
│   ├── net.py
│   └── list_compressor.py
├── .github/workflows/     # CI/CD：v* 标签触发全平台构建 + Release
└── .vercel/               # Vercel 部署说明
```

> 注意：`script/` 下的文件与根目录的同名文件是**不同副本**，仅用于打包分发，不参与服务器运行时逻辑。

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动 Qwen 代理服务器

1. 在项目根目录创建 `qwen_accounts.py`：

    ```python
    ACCOUNTS = [
        {"email": "your-email@example.com", "password": "your-password"},
    ]
    ```

2. 启动：

    ```bash
    python qwen_server.py
    ```

    默认监听 `0.0.0.0:13280`，配置在 `qwen_util.ServerConfig` 中。

3. 访问自动生成的 Swagger 文档：http://localhost:13280/docs

### 启动 Ollama 代理服务器

```bash
python ollama_server.py
```

Ollama 服务器是独立进程，端口在其自身的 `ServerConfig` 中定义（默认也为 13280，如需并行启动需修改其中一个的端口）。

## 主要端点（Qwen 服务器）

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/v1/models` | 模型列表（OpenAI 兼容） |
| POST | `/v1/chat/completions` | 聊天补全（OpenAI 兼容） |
| POST | `/v1/messages` | 消息（Anthropic 兼容） |
| POST | `/v1/images/generations` | 图像生成（flux / turbo / sana / zimage） |
| POST | `/v1/audio/speech` | 语音合成 |
| POST | `/v1/audio/transcriptions` | 语音转录 |
| POST | `/v1/embeddings` | 嵌入向量 |
| POST | `/v1/files` | Anthropic 风格文件上传 |
| GET | `/v1/metrics`、`/v1/status` | 服务器指标与状态 |
| GET | `/health` | 健康检查 |
| GET | `/docs` | Swagger UI |

函数调用采用 **Nous XML** 格式，系统提示词会自动注入函数调用模板，模型在生成回复时使用该格式调用工具。

## 构建独立二进制（Qwen 服务器）

```bash
# 全平台构建
python build.py

# 清理构建产物
python build.py --clean
```

构建产物位于 `dist/`，使用 Nuitka 编译为独立可执行文件。

### 平台特定入口

- Windows: `build.bat`
- Linux / macOS: `build.sh`

### CI/CD

推送 `v*` 标签触发 GitHub Actions 自动构建 Windows / Linux / macOS 三个平台的二进制，并创建 GitHub Release：

```bash
git tag v1.0.0
git push origin v1.0.0
```

## Vercel 部署（仅 Qwen 服务器）

`api/index.py` 作为 Vercel Serverless 入口，在导入项目代码前将 `data/` 路径透明重定向到 `/tmp/data/`（Vercel 无状态限制）。

```bash
npm i -g vercel
vercel
```

## 与当前架构的差异

| 维度 | classical（本分支） | 当前 main / dev |
|------|---------------------|-----------------|
| 服务器框架 | FastAPI + Uvicorn | aiohttp.web |
| 架构 | 单文件服务器（qwen_server.py ~5200 行） | Runner-Worker 双进程 + 平台适配器 |
| 平台支持 | 仅 Qwen 网页接口 + Ollama | 11+ 平台（Qwen、DeepSeek、Ollama、Cursor 等） |
| 配置 | 硬编码于 `qwen_util.ServerConfig` | `config.toml` 文件驱动 |
| WebUI | 无 | 内置 WebUI 管理台（根路径 `/`） |
| 部署 | Vercel + Nuitka 二进制 | 源码运行（`python main.py`） |

如需使用当前稳定版本，请切换到 `main` 分支；如需最新功能，请切换到 `dev` 分支。

---

<div align="center">

**本分支仅供历史参考。** 生产使用请访问 [main 分支](https://github.com/nichengfuben/provider-v2/tree/main)。

Made with ❤️ by [nichengfuben](https://github.com/nichengfuben)

</div>
