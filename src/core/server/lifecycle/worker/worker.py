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

from src.core.dispatch.engine.registry import Registry
from src.core.server import ensure_port_available
from src.core.server.lifecycle.app.app_host import AppHost
from src.core.server.lifecycle.asyncio.looppol import configure_event_loop_policy
from src.core.server.lifecycle.asyncio.win_asyncio import apply_windows_asyncio_patches
from src.core.server.lifecycle.net.conn import make_connector
from src.core.server.lifecycle.stop import request_shutdown
from src.core.server.lifecycle.worker.worker_stop import shutdown_worker
from src.core.server.lifecycle.worker.worker_tasks import (
    abort_default_executor,
    create_background_tasks,
)
from src.core.server.reload import (
    HotReloadService,
    bind_worker_shutdown,
    consume_restart_flag,
)
from src.foundation.config import get_config, get_config_manager
from src.foundation.logger import get_logger, shutdown_logging
from src.foundation.paths import resolve_project_root

__all__ = [
    "RESTART_EXIT_CODE",
    "finalize_exit",
    "is_idle",
    "run_worker",
]

RESTART_EXIT_CODE = 42

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


async def _init_registry_and_app_host(
    cfg: object,
) -> "tuple[aiohttp.ClientSession, Registry, AppHost, object]":
    """创建 HTTP Session、注册表与 AppHost，并绑定配置热重载回调。"""
    connector = make_connector()
    connect_timeout = (
        cfg.http_pool.connect_timeout
        if hasattr(cfg.http_pool, "connect_timeout")
        else 30
    )
    session = aiohttp.ClientSession(
        connector=connector,
        timeout=aiohttp.ClientTimeout(total=None, connect=connect_timeout),
    )

    registry = Registry()
    try:
        await registry.init(session)
    except Exception as exc:
        # 插件加载失败不得终止网关
        logger.error("注册表初始化异常（网关继续启动）: %s", exc)
    get_config_manager().bind_runtime(registry, session)

    from src.core.server.reload.internal.runtime_state import set_worker_start_time

    set_worker_start_time()

    access_log = _logging.getLogger("aiohttp.access") if cfg.debug.access_log else None
    app_host = AppHost(
        cfg.server.host,
        cfg.server.port,
        registry,
        session,
        access_log=access_log,
    )
    registry.set_app_host(app_host)

    async def _reload_app_after_config(changed_scopes: object = ()) -> None:
        from src.foundation.config.reload_policy import scope_needs_app_reload

        scopes = changed_scopes if isinstance(changed_scopes, (list, tuple)) else ()
        if scopes and not scope_needs_app_reload(scopes):
            return
        try:
            await app_host.reload_app()
        except Exception as exc:
            logger.warning("配置热重载后应用重建失败: %s", exc)

    get_config_manager().register_reload_callback(_reload_app_after_config)
    return session, registry, app_host, _reload_app_after_config


async def _handle_port_occupied(
    port: int,
    force_kill: bool,
    attempt: int,
    max_retries: int,
    delay: float,
    session: aiohttp.ClientSession,
    registry: Registry,
) -> bool:
    """处理端口被占用；返回 True 表示应继续重试，False/异常表示放弃。"""
    port_result = ensure_port_available(port, force_kill)
    if not (port_result.occupied and not port_result.released):
        return True
    if attempt < max_retries - 1:
        logger.warning(
            "端口 %d 被占用 (PIDs: %s)，%s，等待 %.1f 秒后重试 (%d/%d)...",
            port,
            port_result.pids,
            "已尝试强制终止" if force_kill else "未强制终止",
            delay,
            attempt + 1,
            max_retries,
        )
        await asyncio.sleep(delay)
        return False
    logger.error(
        "端口 %d 被占用 (PIDs: %s)，重试 %d 次后仍无法释放，退出",
        port,
        port_result.pids,
        max_retries,
    )
    await session.close()
    await registry.close()
    raise SystemExit(1)


async def _try_start_app_host(
    app_host: AppHost,
    port: int,
    attempt: int,
    max_retries: int,
    delay: float,
    session: aiohttp.ClientSession,
    registry: Registry,
) -> bool:
    """尝试启动 AppHost；绑定失败时按重试次数决定是否放弃。"""
    try:
        await app_host.start()
        return True
    except OSError as exc:
        await app_host.shutdown()
        if attempt < max_retries - 1:
            logger.warning(
                "端口 %d 绑定失败 (%s)，等待 %.1f 秒后重试 (%d/%d)...",
                port,
                exc,
                delay,
                attempt + 1,
                max_retries,
            )
            await asyncio.sleep(delay)
            return False
        logger.error(
            "端口 %d 绑定失败，重试 %d 次后仍无法绑定，退出: %s", port, max_retries, exc
        )
        await session.close()
        await registry.close()
        raise SystemExit(1)


async def _bind_port_with_retry(
    cfg: object,
    app_host: AppHost,
    session: aiohttp.ClientSession,
    registry: Registry,
) -> None:
    """带重试的端口绑定；重试耗尽后关闭 session/registry 并退出进程。"""
    port = cfg.server.port
    force_kill = cfg.server.startup_force_kill_port
    max_port_retries = 8
    port_retry_delay = 1.0

    for port_attempt in range(max_port_retries):
        port_free = await _handle_port_occupied(
            port,
            force_kill,
            port_attempt,
            max_port_retries,
            port_retry_delay,
            session,
            registry,
        )
        if not port_free:
            port_retry_delay = min(port_retry_delay * 1.5, 8.0)
            continue

        started = await _try_start_app_host(
            app_host,
            port,
            port_attempt,
            max_port_retries,
            port_retry_delay,
            session,
            registry,
        )
        if started:
            return
        port_retry_delay = min(port_retry_delay * 1.5, 8.0)

    await session.close()
    await registry.close()
    raise SystemExit(1)


def _log_plugin_load_summary() -> None:
    from src.core.server.plugins.runtime import get_plugin_runtime

    plugin_summary = get_plugin_runtime().get_plugin_summary()
    logger.info(
        "插件汇总: loaded=%d failed=%d inactive=%d",
        plugin_summary["loaded"],
        plugin_summary["failed"],
        plugin_summary["inactive"],
    )
    if plugin_summary["failed"] > 0:
        failure_reasons = get_plugin_runtime().get_plugin_load_failure_reasons()
        for pid, reason in failure_reasons.items():
            logger.error("  失败插件 [%s]: %s", pid, reason)


async def _wait_and_shutdown(
    tasks: List[asyncio.Task],
    registry: Registry,
    session: aiohttp.ClientSession,
    app_host: AppHost,
    hot_reload_service: object,
    reload_app_after_config: object,
) -> None:
    """等待退出信号并驱动优雅关停。"""
    stop_event = (
        bind_worker_shutdown.__self__ if False else None
    )  # 占位，避免误用；实际 stop_event 由调用方持有

    try:
        while not _active_stop_event.is_set():
            await asyncio.sleep(0.5)
    except (KeyboardInterrupt, SystemExit):
        request_shutdown("keyboard_interrupt")
        logger.info("收到键盘中断，正在退出...")
    finally:
        try:
            await shutdown_worker(
                tasks,
                registry,
                session,
                app_host,
                hot_reload_service,
                reload_callback=reload_app_after_config,
                config_manager=get_config_manager(),
            )
        except (KeyboardInterrupt, asyncio.CancelledError):
            _print_interrupt_exit_notice()
        except Exception as exc:
            logger.warning("关停过程异常，继续退出: %s", exc)


async def _run() -> int:
    """Worker 的异步主流程——启动所有组件，等待退出信号，优雅关闭。

    Returns:
        进程退出码；42 表示请求 Runner 热重启。
    """
    from src.bootstrap.webui_bindings import register_webui_bindings

    register_webui_bindings()

    cfg = get_config()
    session, registry, app_host, reload_app_after_config = (
        await _init_registry_and_app_host(cfg)
    )
    await _bind_port_with_retry(cfg, app_host, session, registry)

    logger.info("Worker 已启动: http://%s:%d", cfg.server.host, cfg.server.port)
    _log_plugin_load_summary()

    global _active_main_loop
    _active_main_loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    bind_worker_shutdown(stop_event)
    _setup_signal_handlers(stop_event)
    tasks, hot_reload_service = await create_background_tasks(
        cfg,
        registry,
        session,
        app_host,
        stop_event,
        _ROOT,
        get_config_manager(),
    )

    await _wait_and_shutdown(
        tasks, registry, session, app_host, hot_reload_service, reload_app_after_config
    )

    return RESTART_EXIT_CODE if consume_restart_flag() else 0


def run_worker() -> None:
    """Worker 进程入口——配置事件循环策略并启动异步主流程。"""
    apply_windows_asyncio_patches()
    configure_event_loop_policy()

    exit_code = 1
    global _active_main_loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        exit_code = loop.run_until_complete(_run())
    except KeyboardInterrupt:
        request_shutdown("keyboard_interrupt")
        logger.info("Worker 已退出")
        exit_code = 0
    except SystemExit as exc:
        if isinstance(exc.code, int):
            exit_code = exc.code
        elif exc.code:
            exit_code = 1
    except Exception as exc:
        logger.error("Worker 异常退出: %s", exc, exc_info=True)
        exit_code = 1
    finally:
        _active_main_loop = None
        abort_default_executor(loop)
        try:
            loop.close()
        except Exception as exc:
            logger.debug("关闭事件循环失败: %s", exc)
        finalize_exit(exit_code)
