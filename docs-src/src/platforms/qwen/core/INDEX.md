# src/platforms/qwen/core

该目录为 `src/platforms/qwen/core` 的镜像文档目录。

## 文件说明

| 文件 | 说明 |
|------|------|
| `__init__.py` | core 包初始化 |
| `adaptercore.py` | QwenAdapter 实现，委托给 QwenClient |
| `auth.py` | AuthMixin -- 登录、cookie 刷新、指纹生成 |
| `bxumid.py` | bx-umidtoken 值验证辅助函数 |
| `cdn.py` | CDN 相关功能 |
| `chat_session.py` | ChatSession -- 聊天生命周期操作 |
| `client.py` | QwenClient -- mixin 组合入口，HTTP 请求逻辑 |
| `constants.py` | 平台常量定义 |
| `cookies.py` | Cookie 管理 |
| `crypto.py` | 加密和指纹生成 |
| `endpoints.py` | API 端点定义 |
| `errors.py` | 错误类型定义 |
| `files.py` | 文件处理 |
| `headers.py` | 请求头构建 |
| `logs.py` | LogsMixin -- 缓冲日志聚合 |
| `media.py` | MediaMixin -- 视频生成、TTS 语音合成 |
| `mimes.py` | MIME 类型处理 |
| `models.py` | 模型提取辅助函数 |
| `oss.py` | OSS 存储 |
| `password.py` | 密码哈希 |
| `payloads.py` | 请求体构建 |
| `persistence.py` | 持久化加载/保存 |
| `proxy.py` | ProxyState 代理状态管理 |
| `runtime.py` | 运行时兼容性垫片（独立适配器执行） |
| `settings.py` | 设置管理 |
| `shared.py` | 共享常量和辅助函数 |
| `sse.py` | SSE 流式解析 |
| `storage.py` | 存储管理 |
| `stream.py` | 流式处理 |
| `tts.py` | TTS 语音合成服务 |
| `upload.py` | UploadMixin -- 文件上传 (OSS STS PUT) |
| `video.py` | 视频生成服务 |
