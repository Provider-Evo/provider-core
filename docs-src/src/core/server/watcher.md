# src/core/server/watcher.py

文件变更监控器，负责热重载平台、检测核心变更触发重启、检测前端变更输出日志提示。

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
| `src/webui/static/` | 日志提示用户手动刷新浏览器 |
| 其他 `src/` 下的文件 | 进程重启 (exit 42) |

## 前端文件变更处理

检测到 `src/webui/static/` 下文件变化时，仅输出日志提示用户手动刷新浏览器，不自动广播 reload 消息。
