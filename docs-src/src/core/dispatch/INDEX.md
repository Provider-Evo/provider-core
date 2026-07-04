# src/core/dispatch 索引

调度模块负责请求路由和候选者选择。

## 文件列表

- `candidate.py`：候选项数据结构，定义平台能力和状态
- `selector.py`：带有 SQLite 持久化的自适应选择器
- `registry.py`：平台注册表，管理平台适配器和候选项
- `gateway.py`：核心请求分发逻辑
- `runtime_view.py`：运行时视图聚合工具
- `__init__.py`：模块初始化（未修改）

## 核心组件

### Candidate

候选项数据类，包含：
- 平台能力和状态布尔字段
- 上下文长度、模型列表等元数据
- ID 生成辅助函数

### Selector

继承自 `echotools.dispatch.selector.AdaptiveSelector`，提供：
- SQLite 持久化替代 JSON 文件
- JSON → SQLite 自动迁移
- 后台批量刷新机制
- 过期记录清理

### Registry

平台注册表，提供：
- 平台发现和注册
- 候选项收集和过滤
- 模型列表聚合
- 平台动态重载

### dispatch

核心分发函数，支持：
- 请求预处理（系统消息折叠）
- 候选项等待和选择
- 单发和竞速模式
- 错误处理和重试

### runtime_view

运行时视图工具，提供：
- 平台状态收集
- 模型列表聚合
- 配置摘要构建
- 完整运行时摘要

## 依赖关系

- **上游依赖**：`echotools.dispatch.selector`, `echotools.plugin.registry`
- **被依赖**：`src/routes/chat.py`, `src/webui/routers/summary.py`