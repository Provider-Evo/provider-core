# shared 模块

共享工具模块，提供函数调用相关的通用工具函数。

## 目录结构

```
shared/
├── __init__.py      # 模块初始化，重导出 echotools.fncall.shared
├── coercion.py      # 参数类型强制转换
├── loop_detect.py   # 循环检测
├── normalization.py # 内容规范化
├── uuid7.py         # UUID 生成
└── xml_helpers.py   # XML 辅助工具
```

## 核心功能

### 内容规范化

- `normalize_content()`: 规范化内容格式

### 工具描述格式化

- `format_tool_descs()`: 格式化工具描述

### 循环检测

- `detect_tool_loop()`: 检测工具调用循环
- `LoopDetectionResult`: 循环检测结果

### 参数处理

- `_coerce_param_value()`: 参数值强制转换
- `_build_param_schema_index()`: 构建参数模式索引

### UUID 生成

- `_uuid7()`: 生成 UUID v7

## 依赖关系

- 重导出 `echotools.fncall.shared` 模块
- 被其他 fncall 模块使用

## 注意事项

- UUID v7 支持时间排序
- 循环检测防止无限递归
- 参数转换支持多种类型