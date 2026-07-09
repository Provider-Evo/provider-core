#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""Provider-V2 主入口——Runner-Worker 双进程架构。

Runner 进程：
  - 守护 Worker 子进程
  - 监控退出码，处理自动重启（码 42）
  - 传递 Ctrl+C 给 Worker，Runner 本身不重启

Worker 进程：
  - asyncio 事件循环
  - 初始化全��子系统
  - 永久运行直到收到��出信号或触发重启

IDLE 环境：
  - 检测到 IDLE 时直接以单进程 Worker 模式运行
  - 文件监视器只提示，不触发重启
"""

import asyncio
import os
import signal
import ssl
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import IO, List, Optional

import aiohttp
import aiohttp.web

# ---------------------------------------------------------------------------
# 确保项目根目录在模块搜索路径中
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.resolve()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ---------------------------------------------------------------------------
# 导入
# ---------------------------------------------------------------------------

from src.core.config import get_config, get_config_manager
from src.core.dispatch.registry import Registry
from src.core.server import (
    AutoUpdater,
    ensure_port_available,
)
from src.core.server.app_host import AppHost
from src.core.server.infra.reload import (
    HotReloadService,
    bind_worker_shutdown,
    consume_restart_flag,
)

# 导入 server 模块触发 proxy monkey-patch（_init_proxy 在模块级自动执行）
import src.core.server  # noqa: F401

from src.logger import get_logger, shutdown_logging
from src.core.server.infra.shutdown import request_shutdown

logger = get_logger(__name__)

# Worker 进程通过此退出码通知 Runner 执行重启
_RESTART_EXIT_CODE = 42

# Runner 允许的最大连续快速重启次数
_MAX_RAPID_RESTARTS = 10

# 两次重启之间的最小间隔（秒）；低于此值视为"快速重启"
_RAPID_RESTART_THRESHOLD = 5.0

# 触发重启后的短暂冷却时间（秒）
_RESTART_COOLDOWN = 1.0

# Worker 错误重启等待时间（秒）
_ERROR_RESTART_DELAY = 10.0

# Worker 错误重启默认最大次数
_DEFAULT_MAX_ERROR_RESTARTS = 3

# 关停步骤默认超时（秒）
_SHUTDOWN_STEP_TIMEOUT = 5.0

# 全局引用：供信号处理器在事件循环线程外触发关停
_active_main_loop: Optional[asyncio.AbstractEventLoop] = None
_active_stop_event: Optional[asyncio.Event] = None


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _is_idle() -> bool:
    """检测当前是否在 Python IDLE 环境中运���。

    通过检查标准输出类型来判断：IDLE 将 sys.stdout 替换为自定义对象，
    而非标准的 ``TextIOWrapper``。此方法比检查 ``__main__`` 属性更可靠。

    Returns:
        �� IDLE 中运行时返回 True。
    """
    import io
    return not isinstance(sys.stdout, io.TextIOWrapper)


def _read_color_config() -> bool:
    """��� config/main_config.toml 读取 debug.color 配置项��

    在 Python 3.11+ 使用标准库 tomllib；低版本尝试第三方 tomli；
    均不可用或文件不存在时默认返回 True（启用颜色）。

    Returns:
        color 配置值��默认 True。
    """
    cfg_path = _ROOT / "config" / "main_config.toml"
    if not cfg_path.exists():
        return True

    if sys.version_info >= (3, 11):
        import tomllib
        try:
            with open(cfg_path, "rb") as fh:
                raw = tomllib.load(fh)
            return bool(raw.get("debug", {}).get("color", True))
        except (tomllib.TOMLDecodeError, OSError):
            return True

    try:
        import tomli  # type: ignore[import]
        with open(cfg_path, "rb") as fh:
            raw = tomli.load(fh)
        return bool(raw.get("debug", {}).get("color", True))
    except ImportError:
        logger.debug("tomli 未安装，跳过 color 配置读取，默认启用��色")
        return True
    except (Exception,):  # tomli.TOMLDecodeError or OSError
        return True


def _make_connector() -> aiohttp.TCPConnector:
    """创建忽略 SSL 证书验证的 TCP 连接器（从配置读取连接池参数）。

    Returns:
        配置���的 TCPConnector 实例。
    """
    from src.core.server.infra.connector import make_connector
    return make_connector()


# ---------------------------------------------------------------------------
# Worker：异步主流程
# ---------------------------------------------------------------------------


def _print_interrupt_exit_notice() -> None:
    """在日志系统不可用或正在退出时，用最小输出提示 Ctrl+C 退出。"""
    print("\n收到 Ctrl+C，中断退出。", flush=True)


def _finalize_exit(exit_code: int = 0) -> None:
    """关闭日志并强制退出，避免 threading shutdown 阶段被 KeyboardInterrupt 打断。"""
    try:
        shutdown_logging()
    except KeyboardInterrupt:
        _print_interrupt_exit_notice()
    except Exception:
        pass
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
    is_idle_env = _is_idle()
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
        except Exception:
            pass

    # 主动关闭所有 WebSocket 连接，避免 ProactorEventLoop 下 transport 未正确关闭
    from src.webui.core.logs_ws import log_broker
    async with log_broker._lock:
        sockets = list(log_broker._sockets)
        log_broker._sockets.clear()
    for ws in sockets:
        try:
            await asyncio.wait_for(ws.close(), timeout=1.0)
        except Exception:
            pass

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
    """Worker 的异步主流程——启动所有��件，等待退出信号，优雅关闭。"""
    cfg = get_config()
    host = cfg.server.host
    port = cfg.server.port

    connector = _make_connector()
    session = aiohttp.ClientSession(connector=connector)

    registry = Registry()
    await registry.init(session)
    get_config_manager().bind_runtime(registry, session)

    from src.core.server.infra.reload.internal.runtime_state import set_worker_start_time
    set_worker_start_time()


    import logging as _logging
    _access_log = (
        _logging.getLogger("aiohttp.access") if cfg.debug.access_log else None
    )

    app_host = AppHost(
        host,
        port,
        registry,
        session,
        access_log=_access_log,
    )

    async def _reload_app_after_config(changed_scopes: object = ()) -> None:
        from src.core.config.reload_policy import scope_needs_app_reload
        scopes = changed_scopes if isinstance(changed_scopes, (list, tuple)) else ()
        if scopes and not scope_needs_app_reload(scopes):
            return
        try:
            await app_host.reload_app()
        except Exception as exc:
            logger.warning('配置热重载后应用重建失败: %s', exc)

    get_config_manager().register_reload_callback(_reload_app_after_config)

    # 检查并绑定端口（带重试）
    # Windows 上 kill 进程后 TCP ��接字可能仍在 TIME_WAIT，
    # netstat 看不到进程但 bind 仍会失败，因此将 ensure_port_available
    # 和 site.start() 合并在同一个重试循环中。
    max_port_retries = 8
    port_retry_delay = 1.0

    for port_attempt in range(max_port_retries):
        port_result = ensure_port_available(port, cfg.server.startup_force_kill_port)
        if port_result.occupied and not port_result.released:
            # 端口被占用且无法释放
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
            else:
                logger.error(
                    "端口 %d 被占用 (PIDs: %s)，重试 %d 次后仍无法释放，退出",
                    port, port_result.pids, max_port_retries,
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
                    port, exc, port_retry_delay,
                    port_attempt + 1, max_port_retries,
                )
                await asyncio.sleep(port_retry_delay)
                port_retry_delay = min(port_retry_delay * 1.5, 8.0)
            else:
                logger.error(
                    "端口 %d 绑定失败��重试 %d 次后仍无法绑定，退出: %s",
                    port, max_port_retries, exc,
                )
                await session.close()
                await registry.close()
                raise SystemExit(1)
    else:
        # 循环正常结���但未 break（不应到达此处）
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
        cfg, registry, session, app_host, stop_event,
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

    return _RESTART_EXIT_CODE if consume_restart_flag() else 0


# ---------------------------------------------------------------------------
# Worker 进程入口
# ---------------------------------------------------------------------------


def _run_worker() -> None:
    """Worker 进程入口——配置事件循环策略并启动异步主流程。"""
    if sys.platform == "win32":
        if sys.version_info < (3, 12):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # Python 3.12+ on Windows: 默认 ProactorEventLoop 已足够
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
        _finalize_exit(exit_code)


# ---------------------------------------------------------------------------
# Runner 进程入口
# ---------------------------------------------------------------------------


def _pipe_reader(stream: IO[bytes]) -> None:
    """在后台线程中持续读取子进程输出并写入当前进程的 stdout。

    以二进制模式读取，decode 时使用 errors="replace" 容错，
    避免子进程输出非 UTF-8 字节时崩溃。

    Args:
        stream: 子进程的 stdout 字节流（``subprocess.PIPE``）。
    """
    while True:
        line = stream.readline()
        if not line:
            break
        try:
            sys.stdout.write(line.decode("utf-8", errors="replace"))
            sys.stdout.flush()
        except (OSError, ValueError):
            pass


def _build_worker_env(color_enabled: bool) -> dict:
    """构建 Worker 子进程的环境变量字典。

    Args:
        color_enabled: 是否启用 ANSI 颜色输出。

    Returns:
        环境变量字典（基于当前进程环境的副本）。
    """
    env = os.environ.copy()
    env["WORKER_PROCESS"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    if color_enabled:
        env["CLICOLOR_FORCE"] = "1"
        env.pop("NO_COLOR", None)
    else:
        env.pop("CLICOLOR_FORCE", None)
        env["NO_COLOR"] = "1"

    return env


def _run_runner() -> None:
    """Runner 进程入口——守护 Worker 子进程，处理自动重启。

    重启策略：
    - Worker 以退出码 42 退出时触发重启，冷却 1 秒后再启动新 Worker。
    - 若在 ``_RAPID_RESTART_THRESHOLD`` 秒内连续快��重启超过
      ``_MAX_RAPID_RESTARTS`` 次，Runner 放弃重启并退出。
    - Worker 以其他退出码退出时（错误退出），等待 10 秒后重启，
      但最多重启 ``max_restarts`` 次（默认 3 次）。
    - Runner 收到 Ctrl+C 时，立即终止 Worker 并退出。
    """
    color_enabled = _read_color_config()
    worker_env = _build_worker_env(color_enabled)

    python = sys.executable
    args = [python, "-u", str(_ROOT / "main.py")]

    # 读取 max_restarts 配置项
    max_error_restarts = _DEFAULT_MAX_ERROR_RESTARTS
    try:
        from src.core.config import get_config
        cfg = get_config()
        max_error_restarts = getattr(cfg.server, "max_restarts", _DEFAULT_MAX_ERROR_RESTARTS)
    except Exception:
        pass

    rapid_restart_count = 0
    error_restart_count = 0
    last_start_time: float = 0.0

    proc: Optional[subprocess.Popen] = None
    reader_thread: Optional[threading.Thread] = None

    while True:
        # ------------------------------------------------------------------
        # 快速重启保护
        # ------------------------------------------------------------------
        now = time.time()
        elapsed = now - last_start_time

        if elapsed < _RAPID_RESTART_THRESHOLD:
            rapid_restart_count += 1
            if rapid_restart_count > _MAX_RAPID_RESTARTS:
                logger.error(
                    "Worker 在 %.1f 秒内连续快速重启 %d 次，Runner 放���重启并退出",
                    _RAPID_RESTART_THRESHOLD,
                    rapid_restart_count,
                )
                break
            logger.warning(
                "快速重启检测：第 %d 次（上限 %d 次）",
                rapid_restart_count,
                _MAX_RAPID_RESTARTS,
            )
        else:
            rapid_restart_count = 0

        last_start_time = time.time()

        logger.debug("启动 Worker 子进程...")

        # ------------------------------------------------------------------
        # 启动 Worker 子进程
        # ------------------------------------------------------------------
        try:
            proc = subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=worker_env,
            )
        except OSError as exc:
            logger.error("无法��动 Worker 进程: %s", exc)
            break

        assert proc.stdout is not None, "proc.stdout 不应为 None（已指定 PIPE）"

        reader_thread = threading.Thread(
            target=_pipe_reader,
            args=(proc.stdout,),
            daemon=True,
            name=f"pipe-reader-{proc.pid}",
        )
        reader_thread.start()

        # ------------------------------------------------------------------
        # 等待 Worker 退出
        # ------------------------------------------------------------------
        exit_code: int
        try:
            exit_code = proc.wait()
        except KeyboardInterrupt:
            logger.info("Runner 收到 Ctrl+C，正在终止 Worker (PID=%d)...", proc.pid)
            proc.terminate()
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if reader_thread is not None:
                reader_thread.join(timeout=2.0)
            logger.info("Worker 已终止，Runner 退出")
            _finalize_exit(0)

        if reader_thread is not None:
            reader_thread.join(timeout=2.0)

        # ------------------------------------------------------------------
        # 根据退出码决策
        # ------------------------------------------------------------------
        if exit_code == _RESTART_EXIT_CODE:
            # 热重载请求：冷却 1 秒后重启
            logger.info(
                "触发自动重启（退出码 %d），冷却 %.1f 秒后重启...",
                exit_code,
                _RESTART_COOLDOWN,
            )
            time.sleep(_RESTART_COOLDOWN)
        elif exit_code != 0:
            # 错误退出：等待 10 秒后重启，但限制最大重启次数
            error_restart_count += 1
            if error_restart_count > max_error_restarts:
                logger.error(
                    "Worker 因错误退出 %d 次（最大 %d 次），Runner 放弃���启并退出",
                    error_restart_count - 1,
                    max_error_restarts,
                )
                break
            logger.warning(
                "Worker 因错误退出（退出码 %d），等待 %.1f 秒后重启（第 %d/%d 次）...",
                exit_code,
                _ERROR_RESTART_DELAY,
                error_restart_count,
                max_error_restarts,
            )
            time.sleep(_ERROR_RESTART_DELAY)
        else:
            logger.info("Worker 正常退出（退出码 %d），Runner 退出", exit_code)
            break

    # 清理
    if proc is not None and proc.poll() is None:
        proc.kill()
        proc.wait()
    if reader_thread is not None:
        reader_thread.join(timeout=2.0)
    _finalize_exit(0)


# ---------------------------------------------------------------------------
# 程序入口
# ---------------------------------------------------------------------------


def main() -> None:
    """程序主入口——根据��行环境选择合适的启动模式。

    启动模式优先级：
    1. ``WORKER_PROCESS=1`` 环境变量：以 Worker 模式运行（由 Runner 启动）
    2. IDLE 环境：直接以 Worker 模式运行（单进程，禁用颜色）
    3. 其他：以 Runner 模式运行，由 Runner 守护 Worker 子进程
    """
    is_worker = os.environ.get("WORKER_PROCESS") == "1"

    if is_worker:
        _run_worker()
    elif _is_idle():
        print("IDLE 环境：直接以 Worker 模式运行（单进程）。", flush=True)
        os.environ["NO_COLOR"] = "1"
        os.environ.pop("CLICOLOR_FORCE", None)
        _run_worker()
    else:
        _run_runner()


if __name__ == "__main__":
    main()
