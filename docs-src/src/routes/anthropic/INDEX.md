# anthropic 路由模块

Anthropic 兼容路由包，提供 Anthropic Messages API 兼容接口。

## 目录结构

```
anthropic/
├── __init__.py      # 导出 setup_routes
└── messages.py      # Messages API 路由实现
```

## 核心功能

### setup_routes

```python
def setup_routes(app: aiohttp.web.Application) -> None:
```

为 aiohttp.web.Application 注册 Anthropic 兼容路由。

### Messages API

实现 Anthropic Messages API 的路由处理器，支持：
- 消息补全请求
- 流式响应（SSE）
- 工具调用（function calling）
- 多模态内容（文本、图像）

## 依赖关系

- 依赖 `src.core.server` 提供的 HTTP 工具函数
- 依赖 `src.core.errors` 进行错误处理
- 依赖 `src.core.tools` 进行内容规范化
- 依赖 `src.core.config.resolver` 进行模型解析

## 注意事项

- 路由路径遵循 Anthropic API 规范
- 错误响应格式与 Anthropic API 保持一致
- 流式响应使用 SSE（Server-Sent Events）格式