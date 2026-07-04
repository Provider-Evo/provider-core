# protocols 模块

函数调用协议实现包，提供多种函数调用协议。

## 目录结构

```
protocols/
├── __init__.py      # 模块初始化，重导出 echotools.fncall.protocols
├── antml.py         # ANXML 协议
├── bracket.py       # 括号协议
├── custom.py        # 自定义协议
├── dsml.py          # DSML 协议
├── nous.py          # NOUS 协议
├── original.py      # 原始协议
└── xml.py           # XML 协议
```

## 支持的协议

### ANXML 协议 (antml.py)

使用 ANXML 格式的函数调用协议。

### 括号协议 (bracket.py)

使用括号格式的函数调用协议。

### 自定义协议 (custom.py)

自定义函数调用协议，支持用户自定义格式。

### DSML 协议 (dsml.py)

使用 DSML 格式的函数调用协议。

### NOUS 协议 (nous.py)

使用 NOUS 格式的函数调用协议。

### 原始协议 (original.py)

原始函数调用协议格式。

### XML 协议 (xml.py)

使用 XML 格式的函数调用协议。

## 依赖关系

- 重导出 `echotools.fncall.protocols` 模块
- 被 `src.core.fncall.registry` 模块使用

## 注意事项

- 每种协议实现不同的函数调用格式
- 协议通过注册表管理
- 默认协议为 XML 协议