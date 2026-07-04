# src/core/server/watcher.py

文件变更监控器，负责热重载平台、检测核心变更触发重启、检测前端变更触发浏览器刷新。

## 监控范围

- `src/` 整个目录（递归）
- `config/main_config.toml`
- `main.py`

## 文件类型过滤

监控扩展名：`.py`, `.toml`, `.js`, `.css`, `.html`

## 变更分类

| 变更位置 | 行为 |
|---------|------|
| `main_config.toml` 或 `main.py` | 进程重启 (exit 42) |
| `src/core/` 或 `src/routes/` | 进程重启 (exit 42) |
| `src/platforms/<name>/` | 平台热重载 |
| `src/webui/static/` | 浏览器刷新 (WebSocket 广播 reload) |
| 其他 `src/` 下的文件 | 进程重启 (exit 42) |

## 前端热重载链路

1. `FileWatcher` 检测到 `src/webui/static/` 下文件变化
2. `_classify()` 判断 `needs_frontend_reload = True`
3. 通过 `log_broker.broadcast({"type": "reload"})` 广播
4. 前端 WebSocket 收到 reload 消息后执行 `location.reload()`
