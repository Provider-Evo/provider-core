# src/core/dispatch/gateway.py

该模块实现核心请求分发逻辑，负责选择候选项并执行请求。

## 概述

`dispatch` 函数是请求分发的核心入口，根据配置选择候选项并执行请求。支持单发和竞速两种模式。

## 导出接口

- `dispatch`：核心分发函数（异步生成器）

## 核心功能

### 1. 请求预处理

- **系统消息折叠**：无 tools 时，将 system 消息折叠到第一条 user 消息
- **thinking 禁用**：有 tools 时自动禁用 thinking 模式

### 2. 候选项等待与筛选

`_wait_for_candidates` 函数等待候选项就绪：
- 最大等待 15 秒
- 每 0.5 秒检查一次
- 支持按平台过滤

随后按 prompt 粗估 token 做**上下文筛选**；若消息含 `image_url` 则做 **vision 能力筛选**（未知能力视为满足）。

### 3. 竞速决策

根据配置决定并发模式：
- `concurrent_enabled`：是否启用并发
- `group_list`：竞速白名单
- `concurrent_count`：最大并发数

### 4. 请求执行

- **单发模式**：调用 `_single` 执行单个候选项
- **竞速模式**：调用 `_race` 并发执行多个候选项

## 函数签名

```python
async def dispatch(
    registry: Any,
    messages: List[Dict],
    model: str,
    stream: bool,
    *,
    tools: Optional[List[Dict]] = None,
    thinking: bool = False,
    search: bool = False,
    temperature: Optional[float] = None,
    top_p: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop: Optional[List[str]] = None,
    upload_files: Optional[List[Any]] = None,
    platform: str = "",
    **kw: Any,
) -> AsyncGenerator[Union[str, Dict[str, Any]], None]
```

## 依赖关系

- **上游依赖**：`src/core/dispatch/candidate.py`, `src/core/config`, `src/core/errors`
- **被依赖**：`src/webui/routers/chat.py`, `src/routes/` 下的 API 路由
- **标准库**：`asyncio`, `time`, `typing`

## 约束和注意事项

1. **竞速超时**：竞速队列消费最大等待 120 秒
2. **候选项数量**：至少需要 1 个候选项，否则抛出 `NoCandidateError`
3. **协议注入**：延迟到候选项选择后按平台解析协议
4. **错误处理**：捕获候选项错误后自动重试下一个

## 交互

- 与 `Registry` 配合获取候选项
- 与 `Selector` 配合进行候选项选择
- 与平台适配器配合执行实际请求