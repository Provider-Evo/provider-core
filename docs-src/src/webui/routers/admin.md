# src/webui/routers/admin.py

该模块负责 WebUI 管理端点，对外导出七个处理器：

- `reload_service`：`POST /v1/admin/reload` — 触发退出码 42 完全重启服务。先返回成功响应，再异步触发 `os._exit(42)`。
- `config_get`：`GET /v1/config` — 返回完整配置 JSON，直接读取 `config/main_config.toml`。
- `config_put`：`PUT /v1/config` — 写入配置并重新加载。
- `config_reload`：`POST /v1/config/reload` — 从文件重新加载配置，丢弃未保存更改。
- `persist_get`：`GET /v1/webui/persist/{filename}` — 读取 `persist/webui/json/` 目录下的 JSON/TOML 文件。`config.toml` 映射到 `config/webui_config.toml`。
- `persist_put`：`POST /v1/webui/persist/{filename}` — 写入 JSON/TOML 到 `persist/webui/json/` 目录。
- `bg_image_upload`：`POST /v1/webui/bg-image` — 上传终端背景图片到 `persist/webui/img/`。接收 multipart form data，文件大小限制 5MB，支持 PNG/JPEG/GIF/WEBP。返回 `{"url": "/v1/webui/bg-image/{filename}", "filename": "..."}`。
- `bg_image_get`：`GET /v1/webui/bg-image/{filename}` — 提供终端背景图片的静态文件服务。路径安全检查防止目录遍历。

## 持久化存储结构

`persist/webui/` 目录下的存储结构：
- `json/` — JSON/TOML 持久化文件（如 `terminals.json`、`local_store.json`、`stats.json`）
- `db/` — SQLite 数据库文件（如 `requests.db`）
- `img/` — 终端背景图片文件（`terminal-bg-{hash}.{ext}`）

## 终端背景图片

终端背景图片从早期的 base64 data URL 内联存储改为文件存储方案：
1. 前端通过 `POST /v1/webui/bg-image` 上传图片文件
2. 后端将文件保存到 `persist/webui/img/`，生成唯一文件名
3. 返回 URL 路径（如 `/v1/webui/bg-image/terminal-bg-abc123.png`）
4. 前端将 URL 路径存储到 `terminals.json` 的 `bgImage` 字段
5. 启动时检测到 `data:` 开头的旧格式会自动迁移到服务器文件

## 依赖

- `aiohttp.web` — HTTP 框架
- `tomllib` / `tomli` — TOML 解析（Python < 3.11 使用 `tomli`）
- `json` — JSON 读写
- `hashlib` — 文件哈希生成
