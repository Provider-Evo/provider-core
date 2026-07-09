# src/webui/middleware 索引

该目录放 WebUI 独立应用中使用的中间件。

- [auth.py](auth.md) — WebUI 认证中间件，验证 webui_token Cookie
- [error_handler.py](error_handler.md) — 异常处理，返回结构化错误 JSON
- [static_nocache.py](static_nocache.md) — 静态资源缓存策略（public, max-age=3600）
