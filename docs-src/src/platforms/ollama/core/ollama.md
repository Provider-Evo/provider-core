# Ollama 平台说明

## 概览

Ollama 平台连接本地 Ollama 服务器，支持：

- 文本聊天（t2t）
- 视觉理解（vision）
- 向量嵌入（embedding）
- 模型发现（自动扫描本地服务器）

## 架构

```
OllamaAdapter (adaptercore.py)
  └── OllamaClient (client.py)
      ├── 服务器发现 (_bg_discover_servers, 多端口扫描)
      ├── 候选项管理 (_rebuild_candidates, 每个服务器一个 Candidate)
      ├── 聊天补全 (complete, 直接 POST 到 Ollama API)
      ├── 向量嵌入 (create_embedding, POST 到 /api/embed)
      └── 缓存持久化 (servers.json, registry.json)
```

## 关键文件

| 文件 | 说明 |
|------|------|
| `client.py` | 核心客户端，服务器发现、聊天、嵌入、缓存 |
| `adaptercore.py` | 适配器实现 |
| `constants.py` | URL 常量（CHAT_PATH、EMBED_PATH）和能力声明（CAPS） |

## 服务器发现

Ollama 平台在后台自动发现本地 Ollama 服务器：
- 扫描多个常见端口（11434 等）
- 每个发现的服务器成为一个 Candidate
- 服务器信息持久化到 `persist/ollama/servers.json`
- 模型-服务器注册表持久化到 `persist/ollama/registry.json`

## 服务器地址处理

`_verify_server()` 支持两种地址格式：
- **完整 URL**（如 `http://192.168.1.100:11434`）：去除尾部斜杠后直接使用
- **裸 IP:端口**（如 `192.168.1.100:11434`）：自动补全 `http://` 前缀

## 能力检测

`detect_capabilities()` 从 `/api/show` 返回的模型详情中检测能力：
- **chat**：始终为 True（所有 Ollama 模型均支持）
- **vision**：通过 `model_info` 键名和 `details.families` 中的关键词（vision, projector, mmproj, clip）检测
- **embedding**：先检查 `parameters` 字段是否包含 "embedding"，未命中时回退到模型名称关键词匹配（embed, bge, nomic, text2vec, e5-, gte-, sentence）
- **tools**：通过 `template` 字段中的 ".Tools" 或 "tools" 关键词检测

## 向量嵌入

`OllamaClient.create_embedding()` 提供 OpenAI 兼容的嵌入接口：
- 调用 Ollama `/api/embed` 端点
- 支持单条字符串或字符串列表输入
- 返回 OpenAI 格式响应（`object: "list"`, `data[].embedding`）
- 超时 120 秒

`OllamaAdapter.create_embedding()` 委托给客户端实现，附带未初始化状态守卫。

常量 `EMBED_PATH = "/api/embed"` 定义在 `constants.py`，`CAPS` 中声明 `"embedding": True`。

## 代理

**Ollama 不支持代理切换。** Ollama 运行在本地（127.0.0.1），代理无意义。

`set_proxy_enabled()` 在 Ollama 上始终是无操作（使用基类默认实现）。

## 请求流程

### 聊天
1. 从 Candidate 获取服务器地址（`meta["base_url"]`）
2. 直接 POST 到 Ollama `/api/chat` 端点
3. SSE/NDJSON 流式解析
4. yield 文本块

### 嵌入
1. 从 Candidate 获取服务器地址（`meta["base_url"]`）
2. POST 到 Ollama `/api/embed` 端点
3. 解析 JSON 响应
4. 返回 OpenAI 兼容格式

## 注意事项

1. **本地服务** — 不需要代理
2. **服务器发现是后台任务** — 启动后自动扫描
3. **无 test.py** — 需要本地 Ollama 运行才能测试
4. **context_length 默认 128k** — 除非服务器返回特定值
5. **嵌入模型自动检测** — 通过模型名称关键词匹配，支持 bge、nomic、text2vec 等常见嵌入模型
