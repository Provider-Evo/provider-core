# utils 模块

工具函数模块，提供文件操作、ID 生成、IO 工具、重试机制和调度器等功能。

## 目录结构

```
utils/
├── __init__.py      # 模块初始化
├── files.py         # 文件工具（重导出 echotools.files）
├── ids.py           # ID 生成工具
├── io_utils.py      # IO 工具函数
├── retry.py         # 重试机制
└── scheduler.py     # 调度器
```

## 核心功能

### 文件工具 (files.py)

重导出 `echotools.files.file_util` 模块，提供文件操作工具函数。

### ID 生成工具 (ids.py)

提供唯一 ID 生成函数。

### IO 工具函数 (io_utils.py)

提供 IO 操作相关的工具函数。

### 重试机制 (retry.py)

提供重试逻辑实现，支持自动重试失败的操作。

### 调度器 (scheduler.py)

提供任务调度功能。

## 依赖关系

- 依赖 `echotools.files` 提供文件操作工具
- 被其他模块使用提供通用工具函数

## 注意事项

- 文件工具函数通过重导出方式提供，保持与 echotools 的兼容性
- 调度器支持定时任务和周期任务
- 重试机制支持可配置的重试策略