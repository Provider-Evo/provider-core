# opencode 平台文档

## 目录职责

- `adapter.py`：平台门面导出。
- `util.py`：稳定导出与懒加载门面。
- `core/`：平台具体实现。

## 平台简介

opencode 平台适配 OpenCode.ai API，使用 proxy-pool 架构（无需 API Key），通过 proxy.scdn.io 免费代理池实现匿名访问。
核心特性包括 TAS 式 4 维代理评分选择器（ProxyPoolSelector）、代理池定时刷新（24 小时周期）、ModelsCache 自动模型获取、以及完善的重试逻辑（50 次重试、1 秒固定延迟、远程断开/负载截断时立即中止）。

## 文件结构

| 文件 | 职责 |
|------|------|
| `__init__.py` | 平台包初始化，导出 OpencodeAdapter / Adapter |
| `adapter.py` | 门面重导出模块 |
| `util.py` | 延迟加载模块，__getattr__ 懒导入 Adapter |
| `core/__init__.py` | core 包初始化 |
| `core/adaptercore.py` | OpencodeAdapter 实现，proxy-pool 架构，ModelsCache 自动模型获取 |
| `core/client.py` | OpencodeClient HTTP 客户端，proxy-pool 架构，SSE 流式，重试逻辑 |
| `core/constants.py` | 常量定义，含 PROXY_REFRESH_INTERVAL、FILTER_PAID_MODELS 全局控制 |
| `core/headers.py` | 请求头构建模块 |
| `core/payloads.py` | 请求体构建模块 |
| `core/proxypool.py` | 代理池获取器，从 proxy.scdn.io 抓取免费代理（JSON API + HTML 表格 + 文本端点） |
| `core/proxyscore.py` | ProxyPoolSelector TAS 式 4 维评分选择器（失败次数/最近成功/EMA 延迟/总调用数） |
| `core/sse.py` | SSE 流式解析，reasoning 字段映射为 thinking |

## 架构特点

- **无 API Key**：与其他平台不同，opencode 不需要 API Key，而是通过免费代理池匿名访问
- **ProxyPool + ProxyPoolSelector**：每个代理成为一个 Candidate，TAS 式选择器按 4 维评分选择最佳代理
- **持久化**：代理池和代理评分分别持久化到 `persist/opencode/proxy_pool.json` 和 `persist/opencode/proxy_score.json`
- **定时刷新**：代理池每 24 小时自动刷新一次
- **native_tools**：平台声明 `native_tools=True`，跳过 inject_fncall 直接传递 tools

## 维护提示

- 修改前先对照 `docs-src/src/platforms/guide.md`。
- 如果平台依赖第三方 API，失败原因应记录到 `RECORD.md`。
