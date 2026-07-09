# src/core/server/watcher.py

向后兼容别名：`FileWatcher = HotReloadService`。实现见 `src/core/server/reload/service.py`。

## 监控范围

- `src/`（递归）
- `plugins/`（递归，含 `_manifest.json`）
- `main.py`
- `config/main_config.toml`
- `config/webui_config.toml`（仅日志，不触发热重载）

## 文件类型过滤

`.py`、`.toml`、`.js`、`.css`、`.html`；`plugins/` 下另监视 `_manifest.json` / `_manifest.json.disabled`。

## 变更分类

详见 [reload/README.md](reload/README.md)。摘要：

| 变更位置 | 行为 |
|---------|------|
| `plugins/**/static/` | L0：`static_changed` 通知 |
| `plugins/**` platform 类型 | L2：插件重载，不重建 app |
| `plugins/**` fncall/webui/coplan | L2 + L3：插件重载后 `reload_app` |
| `src/platforms/<name>/` | L2：遗留平台路径 |
| `src/webui/static/` | L0：`static_changed` |
| `src/routes/`、部分 `src/core/` | L3：`AppHost.reload_app()` |
| `main.py`、reload 子系统自身 | L4：exit 42 |
