# fncall 模块

函数调用协议包，提供函数调用解析、注入和协议管理功能。

## 目录结构

```
fncall/
├── __init__.py      # 模块初始化，重导出 echotools.fncall
├── base.py          # 基础类和接口
├── registry.py      # 协议注册表
├── parsers/         # 解析器模块
├── prompt/          # 提示词处理
├── protocols/       # 协议实现
└── shared/          # 共享工具
```

## 核心功能

### 函数调用解析

- `parse_fncall()`: 解析函数调用
- `parse_fncall_xml()`: 解析 XML 格式的函数调用
- `inject_fncall()`: 注入函数调用

### 流式解析

- `FncallStreamParser`: 流式函数调用解析器

### 工具描述

- `format_tool_descs()`: 格式化工具描述
- `normalize_content()`: 规范化内容

### 循环检测

- `detect_tool_loop()`: 检测工具调用循环
- `LoopDetectionResult`: 循环检测结果

### 协议管理

- `ToolProtocol`: 工具协议接口
- `get_protocol()`: 获取协议
- `get_protocol_by_id()`: 根据 ID 获取协议
- `register_protocol()`: 注册协议
- `list_protocols()`: 列出所有协议

## 依赖关系

- 重导出 `echotools.fncall` 模块
- 被路由模块和平台适配器使用

## 注意事项

- 协议支持多种格式（XML、JSON 等）
- 流式解析支持实时处理
- 循环检测防止无限递归