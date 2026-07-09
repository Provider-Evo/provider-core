# qwen 平台文档

## 目录职责

- `adapter.py`：平台门面导出。
- `accounts.py`：平台部署配置。
- `util.py`：稳定导出与懒加载门面。
- `core/`：平台具体实现。
- `mvp/`：独立 MVP 测试脚本（无需宿主项目依赖）。

## 文件结构

| 文件 | 职责 |
|------|------|
| `adapter.py` | 门面重导出模块 |
| `accounts.py` | Account 数据类 + 账号列表（758KB，含大量数据） |
| `util.py` | 延迟加载模块，__getattr__ 懒导入 Adapter |
| `mvp/chat.py` | 独立异步聊天烟雾测试 |
| `mvp/env.py` | 独立 MVP 凭据辅助函数 |
| `core/__init__.py` | core 包初始化 |
| `core/adaptercore.py` | QwenAdapter 实现，委托给 QwenClient |
| `core/auth.py` | AuthMixin -- 登录、cookie 刷新、指纹生成 |
| `core/bxumid.py` | bx-umidtoken 值验证辅助函数 |
| `core/cdn.py` | CDN 相关功能 |
| `core/chat_session.py` | ChatSession -- 聊天生命周期操作 |
| `core/client.py` | QwenClient -- mixin 组合入口，HTTP 请求逻辑 |
| `core/constants.py` | 平台常量定义 |
| `core/cookies.py` | Cookie 管理 |
| `core/crypto.py` | 加密和指纹生成 |
| `core/endpoints.py` | API 端点定义 |
| `core/errors.py` | 错误类型定义 |
| `core/files.py` | 文件处理 |
| `core/headers.py` | 请求头构建 |
| `core/logs.py` | LogsMixin -- 缓冲日志聚合 |
| `core/media.py` | MediaMixin -- 视频生成、TTS 语音合成 |
| `core/mimes.py` | MIME 类型处理 |
| `core/models.py` | 模型提取辅助函数 |
| `core/oss.py` | OSS 存储 |
| `core/password.py` | 密码哈希 |
| `core/payloads.py` | 请求体构建 |
| `core/persistence.py` | 持久化加载/保存 |
| `core/proxy.py` | ProxyState 代理状态管理 |
| `core/runtime.py` | 运行时兼容性垫片（独立适配器执行） |
| `core/settings.py` | 设置管理 |
| `core/shared.py` | 共享常量和辅助函数 |
| `core/sse.py` | SSE 流式解析 |
| `core/storage.py` | 存储管理 |
| `core/stream.py` | 流式处理 |
| `core/tts.py` | TTS 语音合成服务 |
| `core/upload.py` | UploadMixin -- 文件上传 (OSS STS PUT) |
| `core/video.py` | 视频生成服务 |

## 测试入口

- MVP 测试位于 `tests/src/platforms/qwen/test_qwen_mvp.py`。
- 协议测试位于 `tests/src/platforms/qwen/test_qwen37max_protocols.py`。
- 持久化测试位于 `tests/src/platforms/qwen/test_qwen_persistence.py`。

## 维护提示

- 修改前先对照 `docs-src/src/platforms/guide.md`。
- 如果平台依赖第三方 API，失败原因应记录到 `RECORD.md`。
