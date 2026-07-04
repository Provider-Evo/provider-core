# main 路由模块

主路由包，提供健康检查、模型列表、状态、能力矩阵、函数调用等基础接口。

## 目录结构

```
main/
├── __init__.py      # 导出 setup_routes
├── routes.py        # 路由注册主文件
├── health.py        # 健康检查接口
├── models.py        # 模型列表接口
├── function_call.py # 函数调用接口
└── static.py        # 静态文件服务
```

## 核心功能

### setup_routes

```python
def setup_routes(app: aiohttp.web.Application) -> None:
```

为 aiohttp.web.Application 注册所有主路由。

### 健康检查

- `GET /health` - 服务健康状态检查
- 返回服务运行状态、版本信息等

### 模型列表

- `GET /v1/models` - 获取支持的模型列表
- 返回所有可用模型及其能力信息

### 函数调用

- `POST /v1/functions` - 函数调用接口
- 支持自定义函数注册和调用

### 静态文件

- 提供 WebUI 静态文件服务
- 支持前端资源加载

## 依赖关系

- 依赖 `src.core.server` 提供的 HTTP 工具函数
- 依赖 `src.core.config` 获取配置信息
- 依赖 `src.core.dispatch` 进行模型调度

## 注意事项

- 路由路径遵循 RESTful 设计规范
- 健康检查接口用于负载均衡器和监控系统
- 模型列表接口返回的信息用于客户端自动发现