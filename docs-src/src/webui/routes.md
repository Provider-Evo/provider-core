# src/webui/routes.py

该模块统一注册 `/`（WebUI 页面）、`/static/`（静态资源）、`/prompts/`（Prompt 模板，根目录 `prompts/`）以及 `/v1/webui/summary`、`/v1/webui/export`、`/v1/webui/ws/logs`、`/v1/config`、`/v1/admin/reload`、`/v1/admin/autoupdate`、`/v1/webui/bg-image` 等接口。

`/prompts/` 通过 `resolve_project_root() / "prompts"` 挂载，供 TTS「恢复默认」等前端功能读取 `tts_default.prompt`。
