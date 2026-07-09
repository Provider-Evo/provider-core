# src/webui/logs_ws.py

该模块提供 WebUI 日志广播器。页面连接 `/v1/webui/ws/logs` 后，可接收 hello、pong 以及后端日志事件。

## 核心组件

### `WebUILogBroker`

WebSocket 日志事件广播器，管理连接集合和内存日志缓冲。

- **内存缓冲**: `deque(maxlen=200)` 保留最近 200 条日志
- **连接管理**: `asyncio.Lock` 保护连接集合的并发访问
- **历史推送**: 新连接建立时推送缓冲中的历史日志

### `MODULE_COLORS`

模块颜色映射字典，将模块名映射到 hex 前景色。支持前缀匹配（如 `webui.routers.websocket` 匹配 `webui`）。

### `_resolve_module_color(module_name)`

按前缀匹配模块颜色。先精确匹配，再逐级按 `.` 分隔前缀匹配。

### `_make_log_id()`

生成唯一日志 ID，格式 `{毫秒时间戳}_{计数器}`。

## WebSocket 消息格式

### 日志事件 (实时推送 + 历史缓冲)

```json
{
  "type": "log",
  "id": "1720099200000_1",
  "timestamp": "2026-07-04T20:40:12",
  "level": "INFO",
  "module": "webui.routers",
  "message": "服务器启动成功",
  "moduleColor": "#79c0ff"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `type` | string | 固定 `"log"` |
| `id` | string | 唯一 ID，用于前端去重 |
| `timestamp` | string | ISO 8601 格式时间戳 |
| `level` | string | 完整级别名：`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`/`SUCCESS` |
| `module` | string | 模块名（如 `webui.routers`） |
| `message` | string | 日志消息文本（纯文本，无 ANSI 转义码） |
| `moduleColor` | string | 模块颜色 hex 值（如 `#79c0ff`），无匹配时为空字符串 |

### 连接握手

新连接建立时发送：
```json
{"type": "hello", "timestamp": 1720099200}
```

历史缓冲推送后发送：
```json
{"type": "history", "count": 200}
```

## 数据流

```
loguru logger.write()
  -> _loguru_sink(record)          [同步，loguru 线程]
    -> broadcast(payload)           [async，主事件循环]
      -> _buffer.append(payload)    [内存缓冲]
      -> socket.send_str(message)   [WebSocket 推送]
```

## 依赖

- `aiohttp.web` — WebSocket 连接管理
- `loguru` — 通过 `setup_loguru_sink()` 注册 sink
- `asyncio` — 事件循环调度

## 约束

- 日志缓冲最大 200 条，超出时从头部丢弃
- WebSocket 连接异常时自动从集合中移除
- `_loguru_sink` 是同步函数，通过 `run_coroutine_threadsafe` 调度到事件循环
