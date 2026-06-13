# noobkeys 平台文档

## 平台概述

NoobKeys 是一个 OpenAI 兼容协议的纯文本对话中转服务，提供 Claude、
GPT-OSS、Qwen、Kimi 等多模型访问，支持流式与非流式响应。

## 目录职责

- `adapter.py`：平台门面导出。
- `accounts.py`：平台部署配置（API Key，由 `.gitignore` 过滤）。
- `util.py`：稳定导出与懒加载门面。
- `core/`：平台具体实现（adaptercore / client / constants / headers / payloads / sse）。

## 能力

- chat: 支持
- vision / tools / thinking / search / embedding: 不支持

## 模型列表

- `claude-opus-4-5-20251101`
- `claude-haiku-4-5-20251001`
- `claude-sonnet-4-5-20250929`
- `claude-sonnet-4-20250514`
- `claude-3-7-sonnet-20250219`
- `claude-3-5-haiku-latest`
- `moonshotai/kimi-k2-instruct-0905`
- `openai/gpt-oss-120b`
- `qwen/qwen3-32b`

## Reasoning 处理

- `openai/gpt-oss-120b` 非流式使用 `message.reasoning`、流式使用
  `delta.reasoning`（部分 chunk 携带 `channel: "analysis"`），统一映射为
  `{"thinking": ...}`。
- `qwen/qwen3-32b` 将 `<think>...</think>` 块嵌入在 `delta.content` 内，作为普通
  文本透传。

## 错误分类

- HTTP 401/403 或上游消息含 `Authentication failed`：Key 失效，立即下线。
- HTTP 402 或消息含 `insufficient`：余额不足，Key 下线，请求立即终止不重试。
- HTTP 429：Key 限速冷却。
- HTTP 5xx：指数退避重试（最多 3 次）。

## 测试入口

- 对应 MVP 测试位于 `tests/src/platforms/noobkeys/test_noobkeys_mvp.py`。

## 维护提示

- 修改前先对照 `docs-src/src/platforms/guide.md`。
- 如果上游协议变化（新增 reasoning 字段、tool_calls 格式），更新
  `core/sse.py` 与 `core/client.py` 中的解析逻辑，并记录到 `RECORD.md`。
