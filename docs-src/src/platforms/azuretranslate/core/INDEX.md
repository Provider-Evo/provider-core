# azuretranslate/core 模块

Azure Translate 平台的核心实现，包含适配器核心逻辑和客户端。

## 目录结构

```
core/
├── __init__.py      # 模块初始化
├── adaptercore.py   # 适配器核心实现
├── client.py        # Azure Translate API 客户端
└── constants.py     # 常量定义
```

## 核心类

### AzureTranslateAdapter (adaptercore.py)

继承自 `PlatformAdapter`，实现 Azure Translate API 的具体逻辑。

**主要方法：**
- `name`: 返回平台标识 "azuretranslate"
- `supported_models`: 返回支持的模型列表
- `default_capabilities`: 返回默认能力字典
- `init()`: 初始化适配器，创建客户端实例
- `candidates()`: 返回当前可用候选项
- `ensure_candidates()`: 确保候选项数量
- `complete()`: 执行翻译补全
- `close()`: 关闭适配器，释放资源

**翻译映射：**
- system 消息 = 源语言代码（如 "en", "zh-Hans", "ja"）
- user 消息 = 待翻译文本
- assistant 响应 = 翻译后的文本

## 依赖关系

- 继承自 `src.platforms.base.PlatformAdapter`
- 依赖 `src.core.dispatch.candidate.Candidate`
- 依赖 `src.logger` 进行日志记录

## 注意事项

- 客户端在 `init()` 方法中延迟初始化
- 支持异步流式响应
- 遵循 Azure API 调用限制