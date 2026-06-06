from __future__ import annotations

import json
import time
from typing import Any, Awaitable, Callable, Optional

import aiohttp.web
from aiohttp.web_app import AppKey

from src.core.config import get_config
from src.core.errors import AuthError
from src.logger import get_logger

__all__ = ["create_app", "json_response", "REGISTRY_KEY", "SESSION_KEY"]
logger = get_logger(__name__)

_Handler = Callable[
    [aiohttp.web.Request],
    Awaitable[aiohttp.web.StreamResponse],
]

# AppKey 类型定义，避免 NotAppKeyWarning
REGISTRY_KEY: AppKey[Any] = AppKey("registry")
SESSION_KEY: AppKey[Any] = AppKey("session")


def json_response(
    data: Any,
    status: int = 200,
    headers: Optional[dict] = None,
) -> aiohttp.web.Response:
    """构造一个 JSON HTTP 响应。

    Args:
        data: 将被序列化为 JSON 的响应数据。
        status: HTTP 状态码，默认为 200。
        headers: 可选的额外响应头字典。

    Returns:
        aiohttp.web.Response: 编码为 UTF-8 的 JSON 响应。
    """
    body = json.dumps(data, ensure_ascii=False)
    resp_headers = {"Content-Type": "application/json"}
    if headers:
        resp_headers.update(headers)
    return aiohttp.web.Response(
        body=body.encode("utf-8"),
        status=status,
        headers=resp_headers,
    )


@aiohttp.web.middleware
async def _cors_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    if request.method == "OPTIONS":
        return aiohttp.web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": (
                    "GET, POST, PUT, DELETE, OPTIONS, PATCH"
                ),
                "Access-Control-Allow-Headers": (
                    "Content-Type, Authorization, X-API-Key, "
                    "Anthropic-Version, x-api-key"
                ),
                "Access-Control-Max-Age": "86400",
            },
        )
    resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    )
    resp.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, X-API-Key, "
        "Anthropic-Version, x-api-key"
    )
    return resp


@aiohttp.web.middleware
async def _auth_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    # /login 必须无条件放行（登录入口）
    # /static/ 也必须放行（登录页与主页的 CSS/JS 依赖）
    # / 、/health 、/v1/models 均要求 pv2_session Cookie 或 Bearer/X-API-Key
    # 任一凭证有效才放行；浏览器无凭证 302 到 /login，API 客户端 JSON 401
    skip = {"/login"}
    if request.path in skip or request.method == "OPTIONS":
        return await handler(request)
    if request.path.startswith("/static/"):
        return await handler(request)

    cfg = get_config()
    if not cfg.auth.enabled:
        return await handler(request)

    group_id = request.headers.get("X-Group-Id", "")
    if group_id:
        group_id = group_id.strip()
        group_list = cfg.auth.group_list_set
        group_list_type = cfg.auth.group_list_type.lower().strip()

        if group_list_type == "blacklist" and group_id in group_list:
            return json_response(
                {
                    "error": {
                        "message": "Group is blocked",
                        "type": "authentication_error",
                        "code": "invalid_group",
                    }
                },
                status=401,
            )
        if group_list_type == "whitelist" and group_id not in group_list:
            return json_response(
                {
                    "error": {
                        "message": "Group is not allowed",
                        "type": "authentication_error",
                        "code": "invalid_group",
                    }
                },
                status=401,
            )

    if not cfg.auth.keys:
        return await handler(request)

    auth_header = request.headers.get("Authorization", "")
    api_key_header = request.headers.get("X-API-Key", "")

    token = ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif api_key_header:
        token = api_key_header.strip()
    else:
        # 浏览器访问：接受 pv2_session cookie 作为等价凭证
        cookie_token = request.cookies.get("pv2_session", "").strip()
        if cookie_token:
            token = cookie_token

    if token not in cfg.auth.keys:
        # 浏览器导航 -> 跳转登录页；API 客户端 -> 维持 JSON 401 协议
        accept = request.headers.get("Accept", "")
        if "text/html" in accept:
            raise aiohttp.web.HTTPFound("/login")
        return json_response(
            {
                "error": {
                    "message": "Invalid or missing API key",
                    "type": "authentication_error",
                    "code": "invalid_api_key",
                }
            },
            status=401,
        )
    return await handler(request)


@aiohttp.web.middleware
async def _custom_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    """自定义路由中间件——提供代码注入点。

    在请求处理前后提供钩子，方便注入自定义逻辑：
    - 请求日志、限流、IP 过滤
    - 动态修改请求头、参数
    - 按平台/路径执行不同策略
    - 响应后处理、统计收集
    """
    # ===== 请求前钩子：在此处添加自定义代码 =====
    # 示例：记录请求信息
    # logger.debug("[custom] %s %s from %s", request.method, request.path, request.remote)

    # 示例：按路径执行自定义逻辑
    # if request.path.startswith("/v1/chat"):
    #     body = await request.json()
    #     # 修改请求参数...

    # 示例：提前返回（短路）
    # if request.path == "/blocked":
    #     return json_response({"error": "blocked"}, status=403)
    # ===== 请求前钩子结束 =====

    response = await handler(request)

    # ===== 请求后钩子：在此处添加自定义代码 =====
    # 示例：记录响应状态
    # logger.debug("[custom] %s -> %d", request.path, response.status)

    # 示例：修改响应头
    # response.headers["X-Custom-Header"] = "value"
    # ===== 请求后钩子结束 =====

    return response


@aiohttp.web.middleware
async def _error_middleware(
    request: aiohttp.web.Request,
    handler: _Handler,
) -> aiohttp.web.StreamResponse:
    try:
        return await handler(request)
    except aiohttp.web.HTTPException:
        raise
    except AuthError as e:
        return json_response(
            {"error": {"message": str(e), "type": "authentication_error"}},
            status=401,
        )
    except Exception as e:
        logger.error(
            "未捕获异常: %s %s -> %s", request.method, request.path, e
        )
        return json_response(
            {"error": {"message": str(e), "type": "server_error"}},
            status=500,
        )


async def create_app(registry: Any, session: Any) -> aiohttp.web.Application:
    """创建并配置 aiohttp Web 应用，挂载所有路由和中间件。

    Args:
        registry: 服务注册表实例，存入应用上下文。
        session: 会话管理实例，存入应用上下文。

    Returns:
        aiohttp.web.Application: 配置完成的 Web 应用。
    """
    from src.routes.anthropic import setup_routes as setup_anth
    from src.routes.openai import setup_routes as setup_oai
    from src.routes.static import setup_routes as setup_static
    from src.webui.routes import setup_routes as setup_webui
    from src.webui.middleware.static_nocache import static_nocache_middleware

    app = aiohttp.web.Application(
        middlewares=[_cors_middleware, _auth_middleware, _custom_middleware, static_nocache_middleware, _error_middleware],
        client_max_size=100 * 1024 * 1024,  # 100MB
    )

    app[REGISTRY_KEY] = registry
    app[SESSION_KEY] = session

    setup_static(app)
    setup_oai(app)
    setup_anth(app)
    setup_webui(app)

    async def _on_startup(application: aiohttp.web.Application) -> None:
        logger.info("aiohttp.web 应用已启动")
        # 将 loguru 日志连接到 WebUI WebSocket（在事件循环启动后）
        try:
            from src.webui.logs_ws import log_broker, setup_loguru_sink
            import asyncio
            loop = asyncio.get_running_loop()
            log_broker.set_loop(loop)
            setup_loguru_sink()
        except Exception:
            pass

    async def _on_cleanup(application: aiohttp.web.Application) -> None:
        logger.info("aiohttp.web 应用正在清理")

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app
