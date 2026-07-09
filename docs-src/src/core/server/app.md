# src/core/server/app.py

该模块负责创建和配置 aiohttp Web 应用程序。

## 概述

`create_app` 函数是应用程序的入口点，配置路由、中间件和生命周期钩子。

## 导出接口

- `create_app`：创建和配置 aiohttp Web 应用程序
- `REGISTRY_KEY`：注册表 AppKey
- `SESSION_KEY`：会话 AppKey

## 核心功能

### 1. 应用程序创建

`create_app` 函数：
- 创建 `aiohttp.web.Application` 实例
- 存储注册表和会话到 `app[REGISTRY_KEY]` 和 `app[SESSION_KEY]`
- 配置中间件链

### 2. 中间件配置

中间件顺序（从外到内）：
1. CORS 中间件
2. 认证中间件
3. 统计中间件
4. 静态文件无缓存中间件
5. 错误处理中间件

### 3. 路由设置

设置以下路由：
- Anthropic API 路由
- OpenAI API 路由
- 主路由
- WebUI 路由

## 函数签名

```python
async def create_app(registry: Any, session: Any) -> aiohttp.web.Application
```

## 依赖关系

- **上游依赖**：`aiohttp.web`, `echotools.logger.manager`
- **被依赖**：`src/core/server/__init__.py`
- **内部依赖**：`src/core/server/middleware.py`, `src/routes/`, `src/webui/`

## 约束和注意事项

1. **中间件顺序**：必须按照指定顺序配置中间件
2. **AppKey 类型**：使用 `AppKey` 避免 `NotAppKeyWarning`
3. **异步初始化**：所有路由设置必须在异步上下文中完成

## 交互

- 与路由模块配合设置 API 端点
- 与中间件配合处理请求
- 与注册表配合提供服务发现