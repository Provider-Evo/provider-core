# Ollama 平台说明

## 概览

Ollama 平台连接本地 Ollama 服务器，支持：

- 文本聊天（t2t）
- 视觉理解（vision）
- 模型发现（自动扫描本地服务器）

## 架构

```
OllamaAdapter (adapter_impl.py)
  └── OllamaClient (client.py)
      ├── 服务器发现 (_bg_discover_servers, 多端口扫描)
      ├── 候选项管理 (_rebuild_candidates, 每个服务器一个 Candidate)
      ├── 聊天补全 (complete, 直接 POST 到 Ollama API)
      └── 缓存持久化 (servers.json, registry.json)
```

## 关键文件

| 文件 | 说明 |
|------|------|
| `client.py` | 核心客户端，服务器发现、聊天、缓存 |
| `adapter_impl.py` | 适配器实现 |

## 服务器发现

Ollama 平台在后台自动发现本地 Ollama 服务器：
- 扫描多个常见端口（11434 等）
- 每个发现的服务器成为一个 Candidate
- 服务器信息持久化到 `persist/ollama/servers.json`
- 模型-服务器注册表持久化到 `persist/ollama/registry.json`

## 代理

**Ollama 不支持代理切换。** Ollama 运行在本地（127.0.0.1），代理无意义。

`set_proxy_enabled()` 在 Ollama 上始终是无操作（使用基类默认实现）。

## 请求流程

1. 从 Candidate 获取服务器地址（`meta["base_url"]`）
2. 直接 POST 到 Ollama `/api/chat` 端点
3. SSE/NDJSON 流式解析
4. yield 文本块

## 注意事项

1. **本地服务** — 不需要代理
2. **服务器发现是后台任务** — 启动后自动扫描
3. **无 test.py** — 需要本地 Ollama 运行才能测试
4. **context_length 默认 128k** — 除非服务器返回特定值
