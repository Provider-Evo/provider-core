# src/core/dispatch 索引

调度模块负责请求路由和候选者选择。

## 文件列表

- `selector.py`：带有 SQLite 持久化的自适应选择器
- `__init__.py`：模块初始化（未修改）

## 核心组件

### Selector

继承自 `echotools.dispatch.selector.AdaptiveSelector`，提供：
- SQLite 持久化替代 JSON 文件
- JSON → SQLite 自动迁移
- 后台批量刷新机制
- 过期记录清理

## 依赖关系

- **上游依赖**：`echotools.dispatch.selector`
- **被依赖**：`src/core/dispatch/gateway.py`