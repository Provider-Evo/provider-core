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
QwenAdapter (adaptercore.py)
  └── QwenClient (client.py) -- mixin composition
      ├── AuthMixin (auth.py) -- 登录、cookie 刷新、指纹生成
      ├── UploadMixin (upload.py) -- 文件上传 (OSS STS PUT)
      ├── MediaMixin (media.py) -- 视频生成 (i2v)、TTS 语音合成
      ├── LogsMixin (logs.py) -- 缓冲日志聚合
      ├── ChatSession (chat_session.py) -- 聊天生命周期操作
      ├── 账号管理 (_account_states, _rebuild_candidates)
      ├── 模型刷新 (_models_cache, ModelsCache)
      ├── 持久化 (_bg_persist, 60s 间隔)
      └── 请求处理 (_do_request, SSE 解析)

关停时 `QwenClient.close()` 先置 `_closing`、等待进行中的 chat cleanup，再关闭专用 `aiohttp.ClientSession`；上传与补全在 session 已关闭时快速失败，避免 `Session is closed` 未处理异常。

`QwenAdapter.ensure_initialized()` 在检测到 session 已关闭但 `_initialized` 仍为真时（例如插件热重载后）会自动 teardown 并重建 session；`init_immediate()` 会重置 `_closing`。`ChatSession` / `TtsService` / `VideoService` 通过 `_require_session` 惰性获取 session，避免持有已关闭的引用。
```

### 新增模块

1. **ChatSession (chat_session.py)**: 聊天生命周期操作
   - `create()`: 创建新对话
   - `stop()`: 停止生成
   - `delete()`: 删除对话
   - `cleanup()`: 清理对话（抑制传输故障与 session 已关闭）
   - `download_image()`: 下载图片资源
   - `send_placeholder_message()`: 发送占位符消息

2. **Runtime (runtime.py)**: 运行时兼容性垫片
   - 用于独立适配器执行（无需宿主项目）
   - 提供 Candidate、PlatformAdapter、ModelsCache、ProxySelector 等兼容类
   - 支持独立 MVP 测试

3. **bxumid.py**: Token 验证
   - `validate_bxumidtoken()`: 验证 bx-umidtoken 格式

## 关键文件

| 文件 | 说明 |
|------|------|
| `client.py` | 核心客户端，mixin 组合入口，HTTP 请求逻辑 |
| `auth.py` | AuthMixin -- 登录、cookie 刷新、指纹生成 |
| `upload.py` | UploadMixin -- 文件上传 (OSS STS PUT) |
| `media.py` | MediaMixin -- 视频生成 (i2v)、TTS 语音合成 |
| `logs.py` | LogsMixin -- 缓冲日志聚合 |
| `chat_session.py` | ChatSession -- 聊天生命周期操作 |
| `bxumid.py` | bx-umidtoken 值验证辅助函数 |
| `runtime.py` | 运行时兼容性垫片（独立适配器执行） |
| `accounts.py` | Account 数据类 + 账号列表（758KB，含大量数据） |
| `shared.py` | 共享常量和辅助函数 |
| `adaptercore.py` | 适配器实现，委托给 QwenClient（含 `supported_models` 属性） |

## 账号系统

- 账号定义在 `accounts.py` 的 `ACCOUNTS` 列表中
- 每个账号有独立的 `token`, `user_id`, `password_hash`
- 登录状态通过 `is_login` 标志跟踪
- Token 过期自动触发重新登录

## 代理切换

Qwen 平台支持手动代理切换和 **ProxySelector 智能选择**：

1. 手动切换：通过 `set_proxy_enabled(True/False)` 强制开启/关闭代理
2. 智能选择：`ProxySelector` 根据历史成功率、延迟等指标自动选择代理或直连
3. 代理状态持久化到 `persist/qwen/usage.json`

### 前提条件

Qwen 必须在 `config.toml` 的 `[platforms_proxy].enabled_platforms` 中：

```toml
[platforms_proxy]
enabled_platforms = ["qwen"]
```

不在列表中时，手动 `set_proxy_enabled()` 无效。

### 持久化格式

```json
{
  "accounts": { ... },
  "cookies": { ... },
  "proxy": {
    "enabled": true
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

1. **`client.py` 采用 mixin 架构** -- AuthMixin、UploadMixin、MediaMixin、LogsMixin 各司其职
2. **`accounts.py` 很大（758KB）** -- 包含大量账号数据
3. **WAF 检测仅检查 Content-Type** -- 不包含状态码或 body 关键词
4. **所有 10000 个账号在启动时从持久化恢复** -- 初始候选项数量巨大
5. **图片/视频/TTS 文件保存到本地磁盘** -- 使用 `GENERATED_*_DIR` 目录
6. **Token 过期自动处理** -- `chat_session.create_chat()` 检测 `unauthorized` 错误码或 "Token has expired" 详情，抛出 `TokenExpiredError`；`client.stream_chat()` 捕获后将对应账号标记为未登录、清除 token、重建候选列表并持久化，然后重新抛出以触发下一个候选重试
