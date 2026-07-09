# src/webui/templates/scripts_actions.py

该模块放摘要导出、复制、刷新、WebSocket 连接等动作逻辑。

v2.2.153 起 renderConfig 添加 typeof 防护，适配懒加载场景下模块可能尚未加载的情况。

## 重启服务流程

### 状态机

重启使用六状态状态机：`idle -> requesting -> restarting -> checking -> success | failed`

### 流程

1. 用户点击"重启服务"按钮
2. 弹出确认对话框
3. 确认后显示全屏覆盖层，状态设为 `requesting`
4. POST `/v1/admin/reload`（5s 超时竞速——服务器会终止，超时视为正常）
5. 状态转为 `restarting`，进度条从 0 递增到 90%
6. 3 秒后开始健康检查：每 2 秒轮询 GET `/health`
7. 成功时进度到 100%，状态 `success`，1.5 秒后刷新页面
8. 失败时（60 次尝试）状态 `failed`，显示"刷新页面"和"重新检查"按钮

### 配置常量

| 常量 | 值 | 说明 |
|------|-----|------|
| `INITIAL_DELAY` | 3000ms | 发送重启请求后等待健康检查的延迟 |
| `CHECK_INTERVAL` | 2000ms | 健康检查间隔 |
| `CHECK_TIMEOUT` | 3000ms | 单次健康检查超时 |
| `MAX_ATTEMPTS` | 60 | 最大检查次数 |
| `PROGRESS_INTERVAL` | 200ms | 进度条更新频率 |
| `SUCCESS_REDIRECT_DELAY` | 1500ms | 成功后延迟刷新 |

### 函数

- `reloadServer()` — 入口，显示确认对话框后触发重启
- `_restartTrigger()` — 显示覆盖层，发送重启请求，启动进度条和健康检查
- `_restartSetState(status)` — 更新覆盖层图标、标题、描述、按钮可见性
- `_restartStartHealthCheck()` — 健康检查轮询循环
- `retryHealthCheck()` — 重新开始健康检查（失败时的重试按钮）
