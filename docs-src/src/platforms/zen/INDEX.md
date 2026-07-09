# zen 平台文档

## 目录职责

- `adapter.py`：平台门面导出。
- `util.py`：稳定导出与懒加载门面。
- `core/`：平台具体实现。

## 平台简介

zen 平台适配 OpenCode.ai API，使用 Bearer token 认证和 OpenAI 兼容的 SSE 流式接口。
核心特性包括 reasoning 字段自动映射为 thinking 输出、ModelsCache 自动模型获取（FILTER_PAID_MODELS 控制是否过滤付费模型）、以及完善的重试逻辑（401/403 失效 key、429 冷却、5xx 指数退避）。

## 文件结构

| 文件 | 职责 |
|------|------|
| `__init__.py` | 平台包初始化，导出 ZenAdapter |
| `adapter.py` | 门面重导出模块 |
| `util.py` | 延迟加载模块 |
| `core/__init__.py` | core 包初始化 |
| `core/adaptercore.py` | ZenAdapter 实现，含 ModelsCache 自动模型获取 |
| `core/client.py` | HTTP 客户端，Bearer 认证，SSE 流式，重试逻辑 |
| `core/constants.py` | 常量定义，含 FILTER_PAID_MODELS 全局控制 |
| `core/headers.py` | 请求头构建模块 |
| `core/payloads.py` | 请求体构建模块 |
| `core/sse.py` | SSE 流式解析，reasoning 字段映射为 thinking |

## 维护提示

- 修改前先对照 `docs-src/src/platforms/guide.md`。
- 如果平台依赖第三方 API，失败原因应记录到 `RECORD.md`。
