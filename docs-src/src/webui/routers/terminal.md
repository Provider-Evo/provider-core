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
| `input` | 用户键盘输入（含鼠标协议二进制数据，用于 TUI 应用） |
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
- **服务启动** -- 从持久化存储恢复存活会话，标记为不可交互（只读历史）。

## 会话恢复

服务器重启后，通过 PID 检测存活进程并恢复会话元数据。由于 PTY 句柄（Windows ConPTY、Unix pty fd）在重启后丢失，恢复的会话标记为 `reattachable=False`，只能显示持久化的离线输出历史（只读模式）。Tab 标题自动添加 `[历史]` 标记。

PID 复用防护：若会话 `created_at` 距今超过 24 小时，视为 PID 可能已被复用，标记为已死亡。

跨平台兼容性：
- Windows ConPTY / pipe：句柄丢失，无法重附，降级为只读历史
- Linux/macOS pty：fd 丢失，无法重附，降级为只读历史

## 前端终端主题

xterm.js 终端支持两种背景模式，通过右键上下文菜单切换：

- **"Provider 主题"**（默认）：跟随 provider-v2 全局亮/暗主题系统（CSS 变量 `data-theme`）。亮色主题使用白色背景 + 深色前景，暗色主题使用深蓝背景 + 浅色前景。完整 16 色 ANSI 调色板均与全局主题对齐。
- **"经典黑色"**：固定使用 `#1e1e1e` 深色背景 + VS Code 风格 16 色调色板，模拟传统终端体验。

背景模式设置持久化保存在 `persist/webui/terminals.json` 的 `bgMode` 字段中，重启后自动恢复。全局主题切换时，Provider 主题模式下的终端会自动更新颜色。

## 鼠标事件支持

终端支持 TUI 应用（htop、vim、mc 等）的鼠标交互。xterm.js 通过 `onBinary` 回调将鼠标协议二进制数据透传到后端 PTY，由 ConPTY/pipe 直接传递给前台进程。

## 关键类

- `_TerminalSession` -- 服务端会话封装，管理终端进程和 WebSocket 客户端集合，支持多客户端广播。
- 依赖 `echotools.terminal`（`LocalTerminal` / `SSHTerminal` / `TerminalCallback`）。
- 依赖 `src.core.terminal_sessions.TerminalSessionStore` 做持久化。

## 错误处理

终端启动失败时（本地或 SSH），WebSocket 处理器直接向客户端发送 `{"type": "error", "message": "..."}` JSON 消息，而非静默失败。此前因 `_broadcast_error` 回调仅在 `attach_client` 时绑定，启动失败路径不会触发。

## 前端交互

### 终端标签重命名

终端标签支持重命名功能，通过右键上下文菜单触发。重命名使用自定义输入对话框（`showInputDialog`）替代原生 `prompt()` 对话框，提供更好的用户体验和视觉一致性。

**实现细节：**
- 函数 `_promptRename(tabId)` 调用 `showInputDialog` 组件
- 对话框标题："重命名终端标签"
- 默认值：当前标签名称
- 支持 Enter 键确认，Escape 键取消
- 重命名后自动更新标签显示

### 终端重启确认

终端重启操作使用自定义确认对话框（`showConfirmDialog`）替代原生 `confirm()` 对话框，提供更好的用户体验和视觉一致性。

**实现细节：**
- 函数 `_restartTerminal(tabId)` 调用 `showConfirmDialog` 组件
- 对话框标题："重启终端"
- 确认按钮文本："重启"
- 取消按钮文本："取消"
- 确认后发送重启命令并清空终端显示
