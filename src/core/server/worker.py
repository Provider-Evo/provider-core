from __future__ import annotations

"""Worker 进程：asyncio 事件循环、HTTP 服务与后台任务。"""

import asyncio
import io
import logging as _logging
import os
import signal
import sys
from typing import List, Optional

import aiohttp
import aiohttp.web

from src.core.config import get_config, get_config_manager
from src.core.dispatch.registry import Registry
from src.core.observability import get_observability_services
from src.core.server import AutoUpdater, ensure_port_available
from src.core.server.app_host import AppHost
from src.core.server.infra.connector import make_connector
from src.core.server.infra.reload import (
    HotReloadService,
    bind_worker_shutdown,
    consume_restart_flag,
)
from src.core.server.infra.shutdown import request_shutdown
from src.paths import resolve_project_root
from src.logger import get_logger, shutdown_logging

__all__ = [
    "RESTART_EXIT_CODE",
    "finalize_exit",
    "is_idle",
    "run_worker",
]

RESTART_EXIT_CODE = 42

_SHUTDOWN_STEP_TIMEOUT = 5.0

_ROOT = resolve_project_root()

logger = get_logger(__name__)

_active_main_loop: Optional[asyncio.AbstractEventLoop] = None
_active_stop_event: Optional[asyncio.Event] = None


def is_idle() -> bool:
    """检测当前是否在 Python IDLE 环境中运行。

    通过检查标准输出类型来判断：IDLE 将 sys.stdout 替换为自定义对象，
    而非标准的 ``TextIOWrapper``。此方法比检查 ``__main__`` 属性更可靠。

    Returns:
        在 IDLE 中运行时返回 True。
    """
    return not isinstance(sys.stdout, io.TextIOWrapper)


def _print_interrupt_exit_notice() -> None:
    """在日志系统不可用或正在退出时，用最小输出提示 Ctrl+C 退出。"""
    print("\n收到 Ctrl+C，中断退出。", flush=True)


def finalize_exit(exit_code: int = 0) -> None:
    """关闭日志并强制退出，避免 threading shutdown 阶段被 KeyboardInterrupt 打断。"""
    try:
        shutdown_logging()
    except KeyboardInterrupt:
        _print_interrupt_exit_notice()
    except Exception as exc:
        logger.debug("关停时关闭日志系统异常: %s", exc, exc_info=True)
    os._exit(exit_code)


def _mark_shutdown_and_interrupt(_signum: int, _frame: object) -> None:
    """收到中断信号时标记关停，并通知主事件循环退出。"""
    request_shutdown("signal")
    loop = _active_main_loop
    stop_event = _active_stop_event
    if loop is None or loop.is_closed() or stop_event is None:
        return
    try:
        loop.call_soon_threadsafe(stop_event.set)
    except RuntimeError:
        return


def _setup_signal_handlers(stop_event: asyncio.Event) -> None:
    """配置进程退出信号处理器。

    Windows 不支持 ``loop.add_signal_handler``，使用 ``signal.signal`` 代替。

    Args:
        stop_event: 用于通知主流程退出的异步事件。
    """
    global _active_stop_event
    _active_stop_event = stop_event
    signal.signal(signal.SIGINT, _mark_shutdown_and_interrupt)
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM,):
            loop.add_signal_handler(sig, stop_event.set)


async def _create_background_tasks(
    cfg: object,
    registry: Registry,
    session: aiohttp.ClientSession,
    app_host: AppHost,
    stop_event: asyncio.Event,
) -> tuple[list[asyncio.Task], HotReloadService | None]:
    """创建并启动后台异步任务（单 FileWatcher 多订阅）。"""
    is_idle_env = is_idle()
    hot_reload = HotReloadService(
        _ROOT,
        registry,
        session,
        app_host,
        get_config_manager(),
        dry_run=is_idle_env,
    )

    async def _hot_reload_task() -> None:
        await hot_reload.start()
        await stop_event.wait()
        await hot_reload.stop()

    async def _autoupdate_task() -> None:
        updater = AutoUpdater(
            root=_ROOT,
            branch=cfg.autoupdate.branch,
            interval=cfg.autoupdate.interval,
        )
        await updater.run()

    tasks: list[asyncio.Task] = [
        asyncio.ensure_future(_hot_reload_task()),
    ]

    if cfg.autoupdate.enabled and not is_idle_env:
        tasks.append(asyncio.ensure_future(_autoupdate_task()))

    return tasks, hot_reload


async def _await_shutdown_step(
    awaitable: object,
    *,
    timeout: float,
    step_name: str,
) -> object | None:
    """为关停步骤设置硬超时，避免单个组件阻塞 Ctrl+C 退出。"""
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("%s 超时，继续执行后续关停步骤", step_name)
        return None
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("%s 失败，继续执行后续关停步骤: %s", step_name, exc)
        return None


async def _shutdown(
    tasks: List[asyncio.Task],
    registry: Registry,
    session: aiohttp.ClientSession,
    app_host: AppHost,
    hot_reload_service: HotReloadService | None = None,
    *,
    reload_callback: object | None = None,
) -> None:
    """优雅关闭所有后台任务和资源。"""
    logger.info("取消后台任务...")
    for task in tasks:
        task.cancel()
    await _await_shutdown_step(
        asyncio.gather(*tasks, return_exceptions=True),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="取消后台任务",
    )

    if hot_reload_service is not None:
        await hot_reload_service.stop()

    if reload_callback is not None:
        try:
            get_config_manager().unregister_reload_callback(reload_callback)
        except Exception as exc:
            logger.warning("注销配置热重载回调失败: %s", exc, exc_info=True)

    try:
        sockets = await get_observability_services().close_log_sockets()
    except Exception as exc:
        logger.warning("收集日志 WebSocket 失败: %s", exc, exc_info=True)
        sockets = []
    for ws in sockets:
        try:
            await asyncio.wait_for(ws.close(), timeout=1.0)
        except Exception as exc:
            logger.debug("关闭日志 WebSocket 失败: %s", exc)

    logger.info("正在关闭注册表...")
    await _await_shutdown_step(
        registry.close(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="关闭注册表",
    )

    logger.info("正在关闭 HTTP Session...")
    await _await_shutdown_step(
        session.close(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="关闭 HTTP Session",
    )

    logger.info("正在停止 Web 服务器...")
    await _await_shutdown_step(
        app_host.shutdown(),
        timeout=_SHUTDOWN_STEP_TIMEOUT,
        step_name="停止 Web 服务器",
    )

    logger.info("Provider-V2 已完全退出")


async def _run() -> int:
    """Worker 的异步主流程——启动所有组件，等待退出信号，优雅关闭。"""
    from src.bootstrap.webui_bindings import register_webui_bindings

    register_webui_bindings()

    cfg = get_config()
    host = cfg.server.host
    port = cfg.server.port

    connector = make_connector()
    session = aiohttp.ClientSession(connector=connector)

    registry = Registry()
    await registry.init(session)
    get_config_manager().bind_runtime(registry, session)

    from src.core.server.infra.reload.internal.runtime_state import set_worker_start_time

    set_worker_start_time()

    access_log = (
        _logging.getLogger("aiohttp.access") if cfg.debug.access_log else None
    )

    app_host = AppHost(
        host,
        port,
        registry,
        session,
        access_log=access_log,
    )

    async def _reload_app_after_config(changed_scopes: object = ()) -> None:
        from src.core.config.reload_policy import scope_needs_app_reload

        scopes = changed_scopes if isinstance(changed_scopes, (list, tuple)) else ()
        if scopes and not scope_needs_app_reload(scopes):
            return
        try:
            await app_host.reload_app()
        except Exception as exc:
            logger.warning("配置热重载后应用重建失败: %s", exc)

    get_config_manager().register_reload_callback(_reload_app_after_config)

    max_port_retries = 8
    port_retry_delay = 1.0

    for port_attempt in range(max_port_retries):
        port_result = ensure_port_available(port, cfg.server.startup_force_kill_port)
        if port_result.occupied and not port_result.released:
            if port_attempt < max_port_retries - 1:
                logger.warning(
                    "端口 %d 被占用 (PIDs: %s)，%s，等待 %.1f 秒后重试 (%d/%d)...",
                    port,
                    port_result.pids,
                    "已尝试强制终止" if cfg.server.startup_force_kill_port else "未强制终止",
                    port_retry_delay,
                    port_attempt + 1,
                    max_port_retries,
                )
                await asyncio.sleep(port_retry_delay)
                port_retry_delay = min(port_retry_delay * 1.5, 8.0)
                continue
            logger.error(
                "端口 %d 被占用 (PIDs: %s)，重试 %d 次后仍无法释放，退出",
                port,
                port_result.pids,
                max_port_retries,
            )
            await session.close()
            await registry.close()
            raise SystemExit(1)

        try:
            await app_host.start()
            break
        except OSError as exc:
            await app_host.shutdown()
            if port_attempt < max_port_retries - 1:
                logger.warning(
                    "端口 %d 绑定失败 (%s)，等待 %.1f 秒后重试 (%d/%d)...",
                    port,
                    exc,
                    port_retry_delay,
                    port_attempt + 1,
                    max_port_retries,
                )
                await asyncio.sleep(port_retry_delay)
                port_retry_delay = min(port_retry_delay * 1.5, 8.0)
            else:
                logger.error(
                    "端口 %d 绑定失败，重试 %d 次后仍无法绑定，退出: %s",
                    port,
                    max_port_retries,
                    exc,
                )
                await session.close()
                await registry.close()
                raise SystemExit(1)
    else:
        await session.close()
        await registry.close()
        raise SystemExit(1)

    logger.info("Worker 已启动: http://%s:%d", host, port)

    global _active_main_loop
    _active_main_loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    bind_worker_shutdown(stop_event)
    _setup_signal_handlers(stop_event)
    tasks, hot_reload_service = await _create_background_tasks(
        cfg,
        registry,
        session,
        app_host,
        stop_event,
    )

    try:
        while not stop_event.is_set():
            await asyncio.sleep(0.5)
    except (KeyboardInterrupt, SystemExit):
        request_shutdown("keyboard_interrupt")
        logger.info("收到键盘中断，正在退出...")
    finally:
        try:
            await _shutdown(
                tasks,
                registry,
                session,
                app_host,
                hot_reload_service,
                reload_callback=_reload_app_after_config,
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            _print_interrupt_exit_notice()
        except Exception as exc:
            logger.warning("关停过程异常，继续退出: %s", exc)

    return RESTART_EXIT_CODE if consume_restart_flag() else 0


def run_worker() -> None:
    """Worker 进程入口——配置事件循环策略并启动异步主流程。"""
    if sys.platform == "win32":
        if sys.version_info < (3, 12):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    else:
        try:
            import uvloop  # type: ignore[import]

            if sys.version_info >= (3, 14):
                uvloop.install()
            else:
                asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
            logger.debug("uvloop 已启用")
        except (ImportError, OSError) as exc:
            logger.debug("uvloop 初始化失败（%s），使用默认事件循环", exc)

    exit_code = 0
    global _active_main_loop
    try:
        exit_code = asyncio.run(_run())
    except KeyboardInterrupt:
        request_shutdown("keyboard_interrupt")
        logger.info("Worker 已退出")
    except SystemExit as exc:
        if isinstance(exc.code, int):
            exit_code = exc.code
        elif exc.code:
            exit_code = 1
    finally:
        _active_main_loop = None
        finalize_exit(exit_code)
