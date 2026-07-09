# deepl 平台

DeepL 平台适配器，提供 DeepL 翻译服务接口。

## 目录结构

```
deepl/
├── __init__.py      # 导出 Adapter, DeepLAdapter
├── adapter.py       # 平台适配器实现
├── accounts.py      # 账号管理
├── util.py          # 工具函数
└── core/            # 核心功能模块
```

## 核心类

### DeepLAdapter

继承自基础适配器，实现 DeepL API 的具体逻辑。

## 依赖关系

- 继承自 `src.platforms.base.Adapter`
- 依赖 `src.core.config` 获取配置信息
- 依赖 `src.core.errors` 进行错误处理

## 注意事项

- 需要有效的 DeepL API 密钥
- 支持多种语言之间的翻译
- 遵循 DeepL API 调用限制