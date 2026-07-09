# yandextranslate 平台

Yandex Translate 平台适配器，提供 Yandex 翻译服务接口。

## 目录结构

```
yandextranslate/
├── __init__.py      # 导出 Adapter, YandexTranslateAdapter
├── adapter.py       # 平台适配器实现
├── accounts.py      # 账号管理
├── util.py          # 工具函数
└── core/            # 核心功能模块
```

## 核心类

### YandexTranslateAdapter

继承自基础适配器，实现 Yandex Translate API 的具体逻辑。

## 依赖关系

- 继承自 `src.platforms.base.Adapter`
- 依赖 `src.core.config` 获取配置信息
- 依赖 `src.core.errors` 进行错误处理

## 注意事项

- 需要有效的 Yandex API 密钥
- 支持多种语言之间的翻译
- 遵循 Yandex API 调用限制