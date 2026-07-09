# src/webui/routers/pages.py

该模块负责 WebUI 的 HTML 页面响应，对外导出三个处理器：

- `webui_page`：管理台主页（`GET /`），返回 `static/index.html`。
- `login_page`：登录页（`*  /login`）。
  - `GET` 渲染一个自包含表单（内联 CSS，支持 light/dark 主题），不依赖任何被鉴权拦截的静态资源。
  - `POST` 校验表单 `token` 字段是否命中 `[auth].keys`，命中则下发 `pv2_session` HttpOnly Cookie（`SameSite=Lax`，30 天有效期）并 302 回 `/`；否则 401 重渲染表单并显示错误提示。
  - 已持有有效 Cookie 的浏览器访问 `/login` 会直接 302 回 `/`，避免重复登录。
- `logout_page`：登出（`GET /logout`），清除 `pv2_session` Cookie 并跳回 `/login`。

登录流程与 `_auth_middleware` 配合：中间件在缺少 Bearer / `X-API-Key` 时接受 `pv2_session` Cookie 作为等价凭证，因此浏览器通过表单登录后可正常访问被鉴权保护的路由与静态资源。
