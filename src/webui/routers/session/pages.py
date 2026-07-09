from __future__ import annotations

"""WebUI 页面路由。"""

from pathlib import Path

import aiohttp.web

from src.core.config import get_config
from src.webui.internal.core.auth import (
    COOKIE_NAME,
    clear_session_cookie,
    set_session_cookie,
    verify_session_cookie,
)
from src.webui.internal.core.security import token_manager

__all__ = ["webui_page", "login_page", "logout_page"]

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

_LOGIN_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Provider-V2 · 登录</title>
<style>
  :root { color-scheme: light dark;
    --bg:#0d1420; --panel:#172131; --text:#edf3ff; --muted:#9eabc2;
    --accent:#8aa4ff; --border:#2b3a52; --err:#ff7b7b; }
  @media (prefers-color-scheme: light) { :root {
    --bg:#f3f6fb; --panel:#ffffff; --text:#162033; --muted:#5d6980;
    --accent:#4263eb; --border:#d7deec; --err:#d94848; } }
  * { box-sizing: border-box; }
  body { margin:0; min-height:100vh; display:flex; align-items:center;
         justify-content:center; font-family:-apple-system,Segoe UI,Arial,sans-serif;
         background:var(--bg); color:var(--text); }
  .card { width:min(420px,92vw); background:var(--panel); border:1px solid var(--border);
          border-radius:16px; padding:28px; box-shadow:0 12px 32px rgba(0,0,0,.25); }
  h1 { margin:0 0 6px; font-size:22px; }
  p  { margin:0 0 18px; color:var(--muted); font-size:13px; line-height:1.55; }
  label { display:block; font-size:12px; color:var(--muted); margin-bottom:6px; }
  input { width:100%; padding:11px 12px; border:1px solid var(--border);
          border-radius:10px; background:transparent; color:var(--text);
          font-size:14px; outline:none; font-family:ui-monospace,Menlo,monospace; }
  input:focus { border-color:var(--accent); }
  button { margin-top:14px; width:100%; padding:11px; border:0; border-radius:10px;
           background:var(--accent); color:#fff; font-size:14px; font-weight:600;
           cursor:pointer; }
  button:hover { filter:brightness(1.1); }
  .err { margin-top:12px; padding:9px 11px; border-radius:8px;
         background:rgba(255,120,120,.12); color:var(--err); font-size:13px; }
  .hint { margin-top:14px; font-size:12px; color:var(--muted); line-height:1.55; }
</style>
</head>
<body>
  <form class="card" method="post" action="/login">
    <h1>Provider-V2</h1>
    <p>请输入 WebUI 访问令牌以继续。该令牌与 API 密钥（apikey）相互独立，仅用于管理界面认证。</p>
    <label for="token">WebUI Token</label>
    <input id="token" name="token" type="password" autocomplete="current-password"
           placeholder="输入启动日志中显示的令牌" required autofocus>
    {error_block}
    <button type="submit">登录</button>
    <div class="hint">令牌存储在浏览器 HttpOnly Cookie 中，不会上传到任何第三方。</div>
  </form>
</body>
</html>
"""


async def webui_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """管理台页面。"""
    response = aiohttp.web.FileResponse(STATIC_DIR / "index.html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


async def login_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """登录页：GET 返回表单，POST 校验 webui_token 后下发 pv2_session Cookie。"""
    cfg = get_config()
    enabled = cfg.auth.enabled

    if request.method == "GET":
        # 已登录的浏览器访问 /login 直接回到主页
        if enabled and verify_session_cookie(request):
            raise aiohttp.web.HTTPFound("/")
        html = _LOGIN_HTML.replace("{error_block}", "")
        return aiohttp.web.Response(text=html, content_type="text/html")

    # POST
    form = await request.post()
    token = (form.get("token") or "").strip()
    next_url = request.query.get("next", "/") or "/"
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = "/"

    if not enabled or token_manager.verify(token):
        resp = aiohttp.web.HTTPFound(next_url)
        set_session_cookie(resp, token)
        return resp

    err_html = '<div class="err">令牌无效，请检查后重试</div>'
    html = _LOGIN_HTML.replace("{error_block}", err_html)
    return aiohttp.web.Response(text=html, content_type="text/html", status=401)


async def logout_page(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """登出：清除 pv2_session Cookie 并回到登录页。"""
    resp = aiohttp.web.HTTPFound("/login")
    clear_session_cookie(resp)
    return resp
