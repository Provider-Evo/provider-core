# docs-src/ 文档索引

本项目文档目录，与 `src/` 代码结构一一对应，提供开发规范和架构说明。

## 目录结构

```
docs-src/
├── INDEX.md                  ← 本文件
├── core/                     ← 核心子系统文档
│   ├── ARCHITECTURE.md       ← 整体架构说明
│   ├── gateway.md            ← 请求分发网关
│   ├── proxy.md              ← 代理系统
│   ├── config.md             ← 配置系统
│   ├── registry.md           ← 平台注册表
│   ├── candidate.md          ← 候选项模型
│   ├── errors.md             ← 错误分类
│   ├── selector.md           ← 候选项选择器
│   └── server.md             ← HTTP 服务器
├── platforms/                ← 平台开发规范
│   ├── PLATFORM_GUIDE.md     ← 平台开发通用规范
│   ├── deepseek/core/        ← DeepSeek 平台说明
│   ├── ollama/core/          ← Ollama 平台说明
│   └── qwen/core/            ← Qwen 平台说明
└── routes/                   ← 路由文档
    ├── openai.md             ← OpenAI 兼容路由
    └── anthropic.md          ← Anthropic 兼容路由
```

## 快速入口

- **新平台开发** → 阅读 `platforms/PLATFORM_GUIDE.md`
- **架构概览** → 阅读 `core/ARCHITECTURE.md`
- **代理切换** → 阅读 `core/proxy.md`
- **Qwen 平台** → 阅读 `platforms/qwen/core/qwen.md`
- **DeepSeek 平台** → 阅读 `platforms/deepseek/core/deepseek.md`
- **Ollama 平台** → 阅读 `platforms/ollama/core/ollama.md`
