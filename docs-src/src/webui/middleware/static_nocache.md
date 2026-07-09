# src/webui/middleware/static_nocache.py

该中间件为 WebUI 静态资源设置缓存策略。

当前策略：`Cache-Control: public, max-age=3600`（1 小时缓存），适用于 JS/CSS/HTML 等静态文件。

历史变更：
- v2.2.153：从 `no-cache` 改为 `public, max-age=3600`，配合懒加载减少重复请求
