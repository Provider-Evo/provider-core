# server 模块

服务器子系统，提供应用创建、HTTP 工具、代理管理、文件监控和自动更新功能。

## 目录结构

```
server/
├── __init__.py      # 模块初始化，重导出子模块
├── app.py           # 应用创建和配置
├── http_utils.py    # HTTP 工具函数
├── middleware.py     # 中间件
├── proxy.py         # 代理管理
└── watcher.py       # 文件监控
```

## 核心功能

### 应用创建 (app.py)

- `create_app()`: 创建 aiohttp.web.Application 实例
- `REGISTRY_KEY`: 应用注册表键
- `SESSION_KEY`: 会话键

### HTTP 工具 (http_utils.py)

- `clean_fncall()`: 清理函数调用响应
- `get_json()`: 从请求中提取 JSON 数据
- `safe_flush()`: 安全刷新响应

### 代理管理 (proxy.py)

- `activate()`: 激活代理
- `deactivate()`: 停用代理
- `is_active()`: 检查代理状态
- `get_proxy_server()`: 获取代理服务器
- `get_proxy_dict()`: 获取代理字典

### 文件监控 (watcher.py)

- `FileWatcher`: 文件变化监控类

### 自动更新 (重导出)

- `AutoUpdater`: 自动更新器
- `get_updater()`: 获取更新器实例
- `set_updater()`: 设置更新器实例

## 依赖关系

- 依赖 `echotools` 提供的生命周期和进程管理工具
- 依赖 `aiohttp.web` 提供 Web 框架
- 被路由模块和 WebUI 模块使用

## 注意事项

- 文件监控支持热重载功能
- 代理管理支持 HTTP/HTTPS 代理
- 自动更新功能需要网络连接