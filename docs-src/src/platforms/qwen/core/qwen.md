# Qwen 平台说明

## 概览

Qwen 平台（通义千问网页版）是本项目中功能最丰富的平台，支持：

- 文本聊天（t2t，含 thinking / search 模式）
- 视觉理解（vision，OpenAI image_url 格式）
- 图片生成（T2I）
- 视频生成（i2v）
- TTS 语音合成
- 文件上传（OSS STS PUT）

## 架构

```
QwenAdapter (adapter_impl.py)
  └── QwenClient (client.py)
      ├── 账号管理 (_account_states, _rebuild_candidates)
      ├── 登录系统 (_bg_login, 并发批量登录)
      ├── Cookie 管理 (_bg_cookie_refresh, 指纹生成)
      ├── 模型刷新 (_models_cache, ModelsCache)
      ├── 持久化 (_bg_persist, 60s 间隔)
      └── 请求处理 (_do_request, SSE 解析)
```

## 关键文件

| 文件 | 说明 |
|------|------|
| `client.py` | 核心客户端，包含所有 HTTP 请求逻辑 |
| `accounts.py` | Account 数据类 + 账号列表（758KB，含大量数据） |
| `shared.py` | God-module（1754 行），包含指纹、cookie、header、payload、上传、SSE 解析等一切逻辑 |
| `adapter_impl.py` | 适配器实现，委托给 QwenClient |

## 账号系统

- 账号定义在 `accounts.py` 的 `ACCOUNTS` 列表中
- 每个账号有独立的 `token`, `user_id`, `password_hash`
- 登录状态通过 `is_login` 标志跟踪
- Token 过期自动触发重新登录

## 代理切换

Qwen 平台是唯一支持 **WAF 自动代理切换** 的平台：

1. `_do_request` 检测到响应 `Content-Type: text/html` → 抛出 `WAFBlockedError`
2. `complete()` 重试循环捕获该异常 → 自动启用代理 24 小时
3. 代理状态持久化到 `persist/qwen/usage.json`
4. 24 小时后自动关闭 → 若再次遇到 WAF → 再次启用

### 前提条件

Qwen 必须在 `config.toml` 的 `[platforms_proxy].enabled_platforms` 中：

```toml
[platforms_proxy]
enabled_platforms = ["qwen"]
```

不在列表中时，WAF 自动触发和手动 `set_proxy_enabled()` 均无效。

### 持久化格式

```json
{
  "accounts": { ... },
  "cookies": { ... },
  "proxy": {
    "enabled": true,
    "auto_enabled_at": 1718000000.0
  },
  "updated": 1718000000.0
}
```

## 请求流程

1. `_do_request` 使用候选项的 token 创建对话
2. 构建请求载荷（`build_payload`）和 headers
3. POST 到 Qwen API，SSE 流式响应
4. 有状态解析 SSE 事件（`parse_sse_event`）：
   - `response_created` → 获取 response_id
   - `answer` → yield 文本
   - `thinking_summary` → yield thinking dict
   - `tool_call` → 解析工具调用
   - `usage` → yield 用量
5. 后台清理对话（`_cleanup_chat`）

## 持久化

- 路径：`persist/qwen/usage.json`
- 内容：账号状态 + cookies + 代理状态
- 间隔：60 秒自动保存
- 关闭时立即保存

## 注意事项

1. **`shared.py` 是 God-module** — 几乎所有辅助逻辑都在此文件中
2. **`accounts.py` 很大（758KB）** — 包含大量账号数据
3. **WAF 检测仅检查 Content-Type** — 不包含状态码或 body 关键词
4. **所有 10000 个账号在启动时从持久化恢复** — 初始候选项数量巨大
5. **图片/视频/TTS 文件保存到本地磁盘** — 使用 `GENERATED_*_DIR` 目录
