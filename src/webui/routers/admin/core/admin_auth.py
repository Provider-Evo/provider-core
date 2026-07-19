"""admin_auth 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 admin_auth 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import aiohttp.web

from src.webui.internal.core.auth import set_session_cookie, verify_session_cookie
from src.webui.internal.core.secure import token_manager

__all__ = ["auth_verify", "auth_update", "auth_regenerate"]


async def auth_verify(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：auth_verify。

    POST /v1/webui/auth/verify — verify token and set session cookie."""
    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    token = (body.get("token") or "").strip()
    if not token:
        return aiohttp.web.json_response({"error": "missing token"}, status=400)

    if token_manager.verify(token):
        resp = aiohttp.web.json_response({"valid": True})
        set_session_cookie(resp, token)
        return resp

    return aiohttp.web.json_response(
        {"valid": False, "error": "invalid token"}, status=401
    )


async def auth_update(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：auth_update。

    POST /v1/webui/auth/update — update token (requires current session)."""
    if not verify_session_cookie(request):
        return aiohttp.web.json_response({"error": "unauthorized"}, status=401)

    try:
        body = await request.json()
    except Exception:
        return aiohttp.web.json_response({"error": "invalid json"}, status=400)

    new_token = (body.get("token") or "").strip()
    if not new_token:
        return aiohttp.web.json_response({"error": "missing token"}, status=400)

    try:
        token_manager.update(new_token)
    except ValueError as exc:
        return aiohttp.web.json_response({"error": str(exc)}, status=400)

    resp = aiohttp.web.json_response({"valid": True, "token": new_token})
    set_session_cookie(resp, new_token)
    return resp


async def auth_regenerate(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：auth_regenerate。

    POST /v1/webui/auth/regenerate — generate a new random token."""
    if not verify_session_cookie(request):
        return aiohttp.web.json_response({"error": "unauthorized"}, status=401)

    new_token = token_manager.regenerate()
    resp = aiohttp.web.json_response({"valid": True, "token": new_token})
    set_session_cookie(resp, new_token)
    return resp
