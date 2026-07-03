# src/webui/routers/terminal.py

该模块负责终端 WebSocket 连接，提供本地终端和 SSH 远程终端会话。

## 路由

- `terminal_ws` -- WebSocket 端点 `/v1/webui/ws/terminal/{session_id}`，前端使用 xterm.js 对接。
- `terminal_sessions_api` -- REST 端点 `GET /v1/webui/terminal/sessions`，列出所有活跃终端会话。

## 协议

### 客户端 -> 服务器

| type | 说明 |
|------|------|
| `init` | 初始化终端会话，`kind` 为 `local` 或 `ssh`，附带 `cols`/`rows` 及 SSH 参数 |
| `input` | 用户键盘输入 |
| `resize` | 终端窗口尺寸变化 |
| `close_session` | 用户关闭标签页 |
| `clear` | 清除终端历史 |
| `restart` | 重启终端会话 |
| `ping` | 心跳 |

### 服务器 -> 客户端

| type | 说明 |
|------|------|
| `ready` | 终端就绪，返回 `session_id` |
| `mode` | 终端模式（`conpty` 或 `pipe`） |
| `output` | 终端输出数据 |
| `error` | 错误消息（如启动失败） |
| `exit` | 进程退出，返回退出码 |
| `session_closed` | 会话已销毁 |
| `existing_sessions` | 当前已有会话列表（用于前端恢复） |
| `history_cleared` | 历史已清除（响应 `clear` 消息） |
| `snapshot` | 终端快照（响应 `restart` 消息） |
| `metadata` | 子进程监控元数据（`has_running_subprocess`、`child_command_label`） |

## 会话生命周期

- **WS 连接** -- 若会话已存在则复用并投递离线缓冲；否则创建新会话。
- **WS 断开** -- 分离客户端，shell 进程保持运行（输出缓冲）。
- **close_session** -- 用户主动关闭，杀死进程并销毁会话。
- **服务启动** -- 从持久化存储恢复存活会话。

## 关键类

- `_TerminalSession` -- 服务端会话封装，管理终端进程和 WebSocket 客户端集合，支持多客户端广播。
- 依赖 `echotools.terminal`（`LocalTerminal` / `SSHTerminal` / `TerminalCallback`）。
- 依赖 `src.core.terminal_sessions.TerminalSessionStore` 做持久化。

## 错误处理

终端启动失败时（本地或 SSH），WebSocket 处理器直接向客户端发送 `{"type": "error", "message": "..."}` JSON 消息，而非静默失败。此前因 `_broadcast_error` 回调仅在 `attach_client` 时绑定，启动失败路径不会触发。
