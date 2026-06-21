from __future__ import annotations

"""服务器子系统——应用创建、HTTP 工具、代理管理、文件监视、自动更新。

本模块整合了原 ``src.core.server/`` 目录下所有子模块的功能：

- **autoupdate**：自动更新（重导出 echotools.AutoUpdater）
- **process**：端口管理（重导出 echotools.process.port）
- **proxy**：代理支持（封装 echotools.ProxyManager）
- **http**：HTTP 工具函数（fncall 清理、缓冲区刷新、JSON 解析）
- **server**：aiohttp 应用创建、中间件、AppKey
- **watcher**：文件监视器（热重载平台、检测核心变更触发重启）

向下兼容
--------
原有所有导入路径均受支持：

.. code-block:: python

    # 原路径（仍可用）
    from src.core.server.server import create_app
    from src.core.server.watcher import FileWatcher
    from src.core.server.proxy import activate, get_proxy_server
    from src.core.server.autoupdate import AutoUpdater

    # 新路径（推荐）
    from src.core.server import create_app, FileWatcher, activate, AutoUpdater
"""

import asyncio
import os
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple

import aiohttp.web
from aiohttp.web_app import AppKey

from echotools.lifecycle.updater import AutoUpdater
from echotools.lifecycle.updater import get_updater, set_updater
from echotools.logger.manager import get_logger
from echotools.process.port import *  # noqa: F401, F403
from echotools.proxy.manager import ProxyManager
from echotools.watcher.file_watcher import FileWatcher as _BaseWatcher
from echotools.web.utils import cors_middleware, error_middleware, json_response

from src.core.config import get_config
from src.core.errors import AuthError

__all__ = [
    # --- autoupdate ---
    "AutoUpdater",
    "get_updater",
    "set_updater",
    # --- http ---
    "clean_fncall",
    "safe_flush",
    "get_json",
    # --- proxy ---
    "activate",
    "deactivate",
    "is_active",
    "get_proxy_server",
    "get_proxy_dict",
    # --- server ---
    "create_app",
    "json_response",
    "REGISTRY_KEY",
    "SESSION_KEY",
    # --- watcher ---
    "FileWatcher",
]

logger = get_logger(__name__)


# ==============================================================================
# HTTP 工具函数
# ==============================================================================


def clean_fncall(content: str, platform_id: str = "", protocol_id: str = "") -> str:
    """清理函数调用标记（移除协议特有的触发标签）。

    Args:
        content: 待清理的内容字符串。
        platform_id: 平台标识（用于确定协议）。
        protocol_id: 协议标识（优先级高于 platform_id）。

    Returns:
        清理后的内容字符串。
    """
    from src.core.tools import get_protocol

    protocol = get_protocol(protocol_id=protocol_id, platform_id=platform_id)
    return protocol.clean_tags(content)


def safe_flush(
    buffer: str, platform_id: str = "", protocol_id: str = ""
) -> Tuple[str, str]:
    """安全刷新缓冲区——保留可能触发工具调用的后缀。

    扫描缓冲区末尾，若发现任何触发标签的前缀（但尚未完整出现），
    则保留该前缀在缓冲区，只刷新前面的完整部分。

    Args:
        buffer: 当前缓冲区内容。
        platform_id: 平台标识。
        protocol_id: 协议标识。

    Returns:
        (可刷新部分, 保留部分)：两段字符串拼接等于原 buffer。

    Examples:
        >>> safe_flush("hello <|fun", protocol_id="openai")
        ("hello ", "<|fun")  # 保留 "<|fun"，可能是 "<|function_call|>" 的前缀
    """
    from src.core.tools import get_protocol

    protocol = get_protocol(protocol_id=protocol_id, platform_id=platform_id)
    tags = protocol.get_trigger_tags()
    if not tags:
        return buffer, ""

    buf_len = len(buffer)
    max_keep = max(len(t) - 1 for t in tags)
    check_len = min(max_keep, buf_len)

    # 从最长后缀开始检查
    for length in range(check_len, 0, -1):
        suffix = buffer[buf_len - length :]
        # 若后缀是任一触发标签的严格前缀（不包括完整标签），则保留
        if any(tag.startswith(suffix) and suffix != tag for tag in tags):
            return buffer[: buf_len - length], buffer[buf_len - length :]

    # 若整个缓冲区长度小于最长标签，且整体是某标签的前缀，全部保留
    if buf_len <= max_keep:
        if any(tag.startswith(buffer) and buffer != tag for tag in tags):
            return "", buffer

    return buffer, ""


async def get_json(request: Any) -> Any:
    """安全读取请求的 JSON body，失败时返回 None。

    Args:
        request: aiohttp.web.Request 实例。

    Returns:
        解析后的 JSON 对象，解析失败时返回 None。
    """
    try:
        return await request.json()
    except Exception:
        return None


# ==============================================================================
# 代理管理（封装 echotools.ProxyManager）
# ==============================================================================

warnings.filterwarnings("ignore", message="Unclosed connection")
warnings.filterwarnings("ignore", module="aiohttp.connector")

_mgr = ProxyManager()


def _load_from_config() -> None:
    """从 config.toml 读取代理配置并应用到管理器。"""
    try:
        cfg = get_config().proxy
        _mgr.configure(
            proxy_server=cfg.proxy_server,
            enabled=cfg.proxy_enabled,
            url_patterns=cfg.proxy_url_patterns,
        )
    except Exception:
        pass


def activate() -> None:
    """激活代理（从配置加载并启用）。"""
    _load_from_config()
    _mgr.activate()


def deactivate() -> None:
    """停用代理。"""
    _mgr.deactivate()


def is_active() -> bool:
    """代理是否已激活。"""
    return _mgr.is_active()


def get_proxy_server() -> str:
    """获取当前代理服务器地址。

    Returns:
        代理服务器 URL，未配置时返回空字符串。
    """
    proxies = _mgr.get_proxy_dict()
    return proxies.get("http") or proxies.get("https") or ""


def get_proxy_dict() -> Dict[str, str]:
    """获取代理字典。

    Returns:
        ``{"http": "...", "https": "..."}`` 格式的代理配置。
    """
    return _mgr.get_proxy_dict()


def _init_proxy() -> None:
    """初始化代理支持（仅在 Worker 进程中激活）。"""
    _mgr.patch_requests()
    _mgr.patch_aiohttp()
    # 只在 Worker 进程中加载代理配置（Runner 不需要）
    if os.environ.get("WORKER_PROCESS") == "1":
        activate()


_init_proxy()


# ==============================================================================
# aiohttp 应用创建与中间件
# ==============================================================================

# AppKey 类型定义，避免 NotAppKeyWarning
REGISTRY_KEY: AppKey[Any] = AppKey("registry")
SESSION_KEY: AppKey[Any] = AppKey("session")


_cors = cors_middleware(
    allow_headers=(
        "Content-Type, Authorization, X-API-Key, "
        "Anthropic-Version, x-api-key"
    ),
)


@aiohttp.web.middleware
async def _auth_middleware(
    request: aiohttp.web.Request,
    handler: Any,
) -> aiohttp.web.StreamResponse:
    """认证中间件——检查 API Key / Session Cookie / Group 白名单/黑名单。

    放行规则：
    - ``/login`` 和 ``/static/`` 无条件放行
    - OPTIONS 请求无条件放行（CORS 预检）
    - 认证未启用时全部放行

    认证流程（auth.enabled=true 时）：
    1. 检查 Group 白名单/黑名单（``X-Group-Id`` 头）
    2. 检查 API Key（``Authorization: Bearer xxx`` 或 ``X-API-Key``）
       或 Session Cookie（``pv2_session``）
    3. 凭证无效时：
       - 浏览器（``Accept: text/html``）：302 重定向到 ``/login``
       - API 客户端：返回 JSON 401
    """
    skip = {"/login"}
    if request.path in skip or request.method == "OPTIONS":
        return await handler(request)
    if request.path.startswith("/static/"):
        return await handler(request)

    cfg = get_config()
    if not cfg.auth.enabled:
        return await handler(request)

    # --- Group 白名单/黑名单检查 ---
    group_id = request.headers.get("X-Group-Id", "").strip()
    if group_id:
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

    # --- API Key / Session Cookie 检查 ---
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
        # 浏览器导航 -> 302 跳转登录页；API 客户端 -> JSON 401
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


_error = error_middleware(error_map={AuthError: (401, "authentication_error")})


async def create_app(registry: Any, session: Any) -> aiohttp.web.Application:
    """创建并配置 aiohttp Web 应用，挂载所有路由和中间件。

    Args:
        registry: 服务注册表实例，存入应用上下文 ``app[REGISTRY_KEY]``。
        session: HTTP 会话实例，存入应用上下文 ``app[SESSION_KEY]``。

    Returns:
        配置完成的 aiohttp.web.Application 实例。

    中间件顺序（从外到内）：
        CORS → Auth → Stats → StaticNoCache → Error
    """
    from src.routes.anthropic import setup_routes as setup_anth
    from src.routes.openai import setup_routes as setup_oai
    from src.routes.static import setup_routes as setup_static
    from src.webui.middleware.static_nocache import static_nocache_middleware
    from src.webui.middleware.stats import stats_middleware
    from src.webui.routes import setup_routes as setup_webui

    app = aiohttp.web.Application(
        middlewares=[
            _cors,
            _auth_middleware,
            stats_middleware,
            static_nocache_middleware,
            _error,
        ],
        client_max_size=100 * 1024 * 1024,  # 100MB
    )

    app[REGISTRY_KEY] = registry
    app[SESSION_KEY] = session

    setup_static(app)
    setup_oai(app)
    setup_anth(app)
    setup_webui(app)

    async def _on_startup(application: aiohttp.web.Application) -> None:
        """应用启动钩子——加载持久化数据、启动后台任务。"""
        logger.debug("aiohttp.web 应用已启动")

        # 启动统计数据持久化（从磁盘加载 + 定期保存）
        try:
            from src.webui.services.stats import start_persist

            start_persist()
        except Exception:
            pass

        # 启动请求日志持久化
        try:
            from src.webui.services.request_log import start_request_persist

            start_request_persist()
        except Exception:
            pass

        # 将 loguru 日志连接到 WebUI WebSocket
        try:
            from src.webui.logs_ws import log_broker, setup_loguru_sink

            loop = asyncio.get_running_loop()
            log_broker.set_loop(loop)
            setup_loguru_sink()
        except Exception:
            pass

        # 恢复持久化的终端会话
        try:
            from src.core.terminal_sessions import get_terminal_store
            from src.webui.routers.terminal import recover_sessions

            store = get_terminal_store()
            await recover_sessions(store)
        except Exception:
            pass

    async def _on_cleanup(application: aiohttp.web.Application) -> None:
        """应用清理钩子——保存持久化数据、优雅关闭终端会话。"""
        logger.info("aiohttp.web 应用正在清理")

        # 最终保存统计数据
        try:
            from src.webui.services.stats import save_stats

            save_stats()
        except Exception:
            pass

        # 保存所有终端会话状态（用于崩溃恢复）
        try:
            from src.core.terminal_sessions import get_terminal_store
            from src.webui.routers.terminal import list_sessions

            store = get_terminal_store()
            for session_obj in list_sessions():
                if session_obj._terminal and session_obj.alive:
                    session_obj._terminal.save_state(store.persist_dir)
        except Exception:
            pass

    app.on_startup.append(_on_startup)
    app.on_cleanup.append(_on_cleanup)

    return app


# ==============================================================================
# 文件监视器（热重载平台 + 核心变更触发重启）
# ==============================================================================

_CORE_DIRS = {"core", "routes"}
_PLATFORM_DIR = "platforms"


def _classify(changed: Set[str]) -> Tuple[bool, Set[str]]:
    """分类变更文件为核心文件或平台文件。

    Args:
        changed: 变更文件的绝对路径集合。

    Returns:
        (needs_restart, platform_names):
            - needs_restart: 是否需要重启（核心文件变更）
            - platform_names: 变更的平台名称集合（可热重载）
    """
    needs_restart = False
    platform_names: Set[str] = set()

    for fp in changed:
        p = Path(fp)
        parts = p.parts

        # config.toml 或 main.py 变更 → 强制重启
        if p.name in ("config.toml", "main.py"):
            needs_restart = True
            continue

        # 定位 src/ 目录索引
        try:
            src_idx = parts.index("src")
        except ValueError:
            # 不在 src/ 下的文件 → 保守策略：重启
            needs_restart = True
            continue

        sub_parts = parts[src_idx + 1 :]
        if not sub_parts:
            needs_restart = True
            continue

        first = sub_parts[0]

        # core/ 或 routes/ 下的变更 → 重启
        if first in _CORE_DIRS or first == "__init__.py":
            needs_restart = True
        # platforms/<platform_name>/ 下的变更 → 热重载
        elif first == _PLATFORM_DIR and len(sub_parts) >= 2:
            platform_names.add(sub_parts[1])
        else:
            # 其他未知路径 → 保守策略：重启
            needs_restart = True

    return needs_restart, platform_names


def _trigger_restart(session: Any, registry: Any) -> None:
    """触发 Worker 进程重启（退出码 42）。

    Args:
        session: HTTP 会话对象（尝试优雅关闭）。
        registry: 注册表对象（尝试优雅关闭）。
    """
    logger.info("核心文件变更，准备触发重启...")
    for resource in (session, registry):
        if resource:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(resource.close())
            except Exception as exc:
                logger.warning("关闭资源失败: %s", exc)
    os._exit(42)


class FileWatcher:
    """文件变更监视器——复用 echotools.FileWatcher + 项目分类逻辑。

    监视逻辑：
    - 核心文件（``core/``、``routes/``、``config.toml``、``main.py``）变更
      → 退出码 42 重启
    - 平台文件（``src/platforms/<name>/``）变更
      → 热重载对应平台，刷新候选项
    """

    def __init__(self, root: Path) -> None:
        """初始化文件监视器。

        Args:
            root: 项目根目录路径。
        """
        self._root = root
        self._registry: Optional[Any] = None
        self._session: Optional[Any] = None

        # 构建监视路径列表
        paths = []
        src = root / "src"
        if src.is_dir():
            paths.append(src)
        for f in (root / "config.toml", root / "main.py"):
            if f.is_file():
                paths.append(f)

        self._watcher = _BaseWatcher(
            paths=paths,
            extensions={".py", ".toml"},
            interval=2.0,
        )

    async def _on_change(self, changed: Set[str]) -> None:
        """文件变更回调——分类处理重启或热重载。

        Args:
            changed: 变更文件的绝对路径集合。
        """
        logger.info("检测到文件变更: %s", [Path(f).name for f in changed])

        needs_restart, platform_names = _classify(changed)

        if needs_restart:
            # 核心文件变更 → 延迟 1 秒后重启（避免文件保存未完成）
            await asyncio.sleep(1.0)
            _trigger_restart(self._session, self._registry)
            return

        # 平台文件变更 → 热重载
        for name in platform_names:
            if self._registry and self._session:
                logger.info("热重载平台: %s", name)
                ok = await self._registry.reload_platform(name, self._session)
                if ok:
                    adapter = self._registry.adapters.get(name)
                    models = (
                        list(getattr(adapter, "supported_models", []))
                        if adapter
                        else []
                    )
                    for model in models:
                        try:
                            await self._registry.ensure_candidates(model, 1)
                        except Exception as exc:
                            logger.warning("候选项刷新失败: %s", exc)
                else:
                    logger.warning("平台 [%s] 热重载失败", name)

    async def start(self, registry: Any, session: Any) -> None:
        """启动文件监视器。

        Args:
            registry: 注册表对象（用于热重载平台）。
            session: HTTP 会话对象（用于热重载时的请求）。
        """
        self._registry = registry
        self._session = session
        await self._watcher.start(self._on_change)
        logger.info("文件监视已启动: %s", self._root)

    def stop(self) -> None:
        """停止文件监视器。"""
        self._watcher.stop()
        logger.info("文件监视已停止")
