# parsers 模块

函数调用解析器包，提供函数调用解析功能。

## 目录结构

```
parsers/
├── __init__.py      # 模块初始化，重导出 echotools.fncall.parsers
├── stream.py        # 流式解析器
└── xml_parser.py    # XML 解析器
```

## 核心功能

### 解析函数

- `parse_fncall()`: 解析函数调用
- `parse_fncall_xml()`: 解析 XML 格式的函数调用

### 流式解析器

- `FncallStreamParser`: 流式函数调用解析器，支持实时处理

## 依赖关系

- 重导出 `echotools.fncall.parsers` 模块
- 被路由模块和平台适配器使用

## 注意事项

- 流式解析器支持增量解析
- XML 解析器支持标准 XML 格式
- 解析器支持多种函数调用格式