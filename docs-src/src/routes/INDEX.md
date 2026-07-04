# src/routes 索引

路由层负责对外协议兼容，包括 OpenAI、Anthropic 与静态页面入口。

## 目录结构

```
src/routes/
├── __init__.py
├── main/               # 主路由：健康检查、模型列表、状态、能力矩阵、函数调用
│   ├── __init__.py
│   ├── routes.py       # 聚合器
│   ├── health.py
│   ├── models.py
│   ├── static.py
│   └── function_call.py
├── openai/             # OpenAI 兼容路由
│   ├── __init__.py
│   ├── routes.py       # 聚合器
│   ├── helpers.py      # 共享工具函数、常量、ID 生成器
│   ├── chat.py         # Chat Completions 端点（流式 + 非流式）
│   ├── media.py        # 媒体端点：图片、音频、视频、embeddings
│   └── stubs.py        # 存根/未实现处理器
└── anthropic/          # Anthropic 兼容路由
    ├── __init__.py
    └── messages.py     # Messages 端点（流式 + 非流式）
```

## 路由注册

`src/core/server/app.py` 中通过以下方式注册路由：

```python
from src.routes.anthropic import setup_routes as setup_anth
from src.routes.openai import setup_routes as setup_oai
from src.routes.main import setup_routes as setup_main

setup_main(app)   # 健康检查、模型、状态、能力矩阵、函数调用
setup_oai(app)    # OpenAI 兼容端点
setup_anth(app)   # Anthropic 兼容端点
```
