# src/core/dispatch/selector.py

该模块实现带有 SQLite 持久化和过期候选者清理的自适应选择器。

## 概述

`Selector` 类继承自 `echotools.dispatch.selector.AdaptiveSelector`，用 SQLite 数据库替代默认的 JSON 文件持久化，消除数千个单独文件 I/O 操作的开销。

## 架构

```
Selector (selector.py)
  └── 继承 AdaptiveSelector (echotools)
      ├── SQLite 持久化 (gateway.db)
      ├── JSON → SQLite 迁移
      ├── 后台刷新线程 (5秒间隔)
      └── 过期记录清理 (默认30天)
```

## 核心功能

### 1. SQLite 持久化

- 数据库路径：`persist/dispatch/gateway.db`
- 表结构：`records` 表存储所有候选者记录
- 索引：`idx_group` (组名) 和 `idx_updated` (更新时间)

### 2. JSON 迁移

初始化时自动检测并迁移遗留的 JSON 文件：
- 支持两种格式：旧 EMA 格式和新摘要格式
- 迁移后自动删除遗留 JSON 文件

### 3. 后台刷新

- 每 5 秒将脏记录批量写入 SQLite
- 关闭时立即刷新所有待写记录
- 使用线程锁保证线程安全

### 4. 过期清理

- 默认保留期：30 天
- 仅清理从未成功调用过的记录
- 使用 SQL 批量删除，同步清理内存池

## 导出接口

- `Selector`：主选择器类
- `TASRecord`：候选者记录数据类（从 echotools 导入）

## 依赖关系

- **上游依赖**：`echotools.dispatch.selector.AdaptiveSelector`
- **被依赖**：`src/core/dispatch/gateway.py` 使用此类进行请求路由
- **标准库**：`sqlite3`, `threading`, `json`, `time`, `pathlib`

## 约束和注意事项

1. **线程安全**：所有数据库操作使用 `threading.Lock` 保护
2. **关闭顺序**：必须调用 `close()` 方法确保数据完整写入
3. **迁移逻辑**：仅在数据库为空时尝试迁移 JSON 文件
4. **清理策略**：仅清理 `n_calls = 0` 且 `n_fails > 0` 的记录

## 交互

- 与 `Gateway` 配合使用，提供候选者选择和评分
- 持久化状态存储在 `persist/dispatch/gateway.db`
- 通过后台线程定期刷新，减少 I/O 阻塞