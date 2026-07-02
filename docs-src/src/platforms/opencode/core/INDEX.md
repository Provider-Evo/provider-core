# src/platforms/opencode/core

该目录为 `src/platforms/opencode/core` 的镜像文档目录。

## 文件说明

| 文件 | 说明 |
|------|------|
| `__init__.py` | core 包初始化 |
| `adaptercore.py` | OpencodeAdapter 实现，proxy-pool 架构，ModelsCache 自动模型获取 |
| `client.py` | OpencodeClient HTTP 客户端，proxy-pool 架构，SSE 流式，重试逻辑 |
| `constants.py` | 常量定义，含 PROXY_REFRESH_INTERVAL、FILTER_PAID_MODELS 全局控制 |
| `headers.py` | 请求头构建模块 |
| `payloads.py` | 请求体构建模块 |
| `proxypool.py` | 代理池获取器，从 proxy.scdn.io 抓取免费代理（JSON API + HTML 表格 + 文本端点） |
| `proxyscore.py` | ProxyPoolSelector 贝叶斯评分选择器（不确定性奖励 + 延迟惩罚 + 时间衰减） |
| `sse.py` | SSE 流式解析，reasoning 字段映射为 thinking |
