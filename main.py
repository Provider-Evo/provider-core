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

from src.core.config import get_config, start_config_watcher
from src.core.dispatch.registry import Registry
from src.core.server import (   # server 已合并为单文件，所有符号从此处导入
    AutoUpdater,
    FileWatcher,
    create_app,
    ensure_port_available,
)

# 导入 server 模块触发 proxy monkey-patch（_init_proxy 在模块级自动执行）
import src.core.server  # noqa: F401

from src.logger import get_logger

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
    from src.core.server.connector import make_connector
    return make_connector()


# ---------------------------------------------------------------------------
# Worker：异步主流程
# ---------------------------------------------------------------------------


def _setup_signal_handlers(stop_event: asyncio.Event) -> None:
    """配置进程退出信号处理器（仅 Unix 平台）。

    在 Windows 上不注册信号处理器，通过 KeyboardInterrupt 捕获退出。

    Args:
        stop_event: 用于通知主流程退出的异步事件。
    """

    def _on_signal() -> None:
        logger.info("收到退出信号，准备优雅退出...")
        stop_event.set()

    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)
    else:
        logger.debug("Windows 平台��信号处理器通过 KeyboardInterrupt 捕获")


async def _create_background_tasks(
    cfg: object,
    registry: Registry,
    session: aiohttp.ClientSession,
) -> List[asyncio.Task]:
    """创建并启动后台异步任务。

    Args:
        cfg: 全局配置对象。
        registry: 路由注册表。
        session: aiohttp 客户端会话。

    Returns:
        已启动的后台任务列表。
    """

    async def _config_watcher_task() -> None:
        await start_config_watcher(interval=2.0)

    async def _file_watcher_task() -> None:
        watcher = FileWatcher(_ROOT)
        await watcher.start(registry, session)

    async def _autoupdate_task() -> None:
        updater = AutoUpdater(
            root=_ROOT,
            branch=cfg.autoupdate.branch,
            interval=cfg.autoupdate.interval,
        )
        await updater.run()

    tasks: List[asyncio.Task] = [
        asyncio.ensure_future(_config_watcher_task()),
    ]

    is_idle_env = _is_idle()
    if not is_idle_env:
        tasks.append(asyncio.ensure_future(_file_watcher_task()))
    if cfg.autoupdate.enabled and not is_idle_env:
        tasks.append(asyncio.ensure_future(_autoupdate_task()))

    return tasks


async def _shutdown(
    tasks: List[asyncio.Task],
    registry: Registry,
    session: aiohttp.ClientSession,
    runner: aiohttp.web.AppRunner,
) -> None:
    """优雅关闭所有后台任务和资源。

    Args:
        tasks: 需要取消的后台任务列表。
        registry: 路由注册表。
        session: aiohttp 客户端会话。
        runner: aiohttp 应用运行器。
    """
    logger.info("取消后台任务...")
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    # 主动关闭所有 WebSocket 连接，避免 ProactorEventLoop 下 transport 未正确关闭
    from src.webui.logs_ws import log_broker
    async with log_broker._lock:
        sockets = list(log_broker._sockets)
        log_broker._sockets.clear()
    for ws in sockets:
        try:
            await ws.close()
        except Exception:
            pass

    logger.info("正在关闭注册表...")
    await registry.close()

    logger.info("正在关闭 HTTP Session...")
    await session.close()

    logger.info("正在停止 Web 服务器...")
    if runner is not None:
        await runner.cleanup()

    logger.info("Provider-V2 已完全退出")


async def _run() -> None:
    """Worker 的异步主流程——启动所有��件，等待退出信号，优雅关闭。"""
    cfg = get_config()
    host = cfg.server.host
    port = cfg.server.port

    connector = _make_connector()
    session = aiohttp.ClientSession(connector=connector)

    registry = Registry()
    await registry.init(session)

    app = await create_app(registry, session)

    import logging as _logging
    _access_log = (
        _logging.getLogger("aiohttp.access") if cfg.debug.access_log else None
    )

    # 检查并绑定端口（带重试）
    # Windows 上 kill 进程后 TCP ��接字可能仍在 TIME_WAIT，
    # netstat 看不到进程但 bind 仍会失败，因此将 ensure_port_available
    # 和 site.start() 合并在同一个重试循环中。
    max_port_retries = 8
    port_retry_delay = 1.0
    runner: Optional[aiohttp.web.AppRunner] = None

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

        # 端口可用（或已释放），尝试绑定
        runner = aiohttp.web.AppRunner(app, access_log=_access_log)
        await runner.setup()
        site = aiohttp.web.TCPSite(runner, host, port)
        try:
            await site.start()
            break  # 绑定成功
        except OSError as exc:
            # ensure_port_available 报告空闲但实际 bind 失败（TIME_WAIT）
            await runner.cleanup()
            runner = None
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

    stop_event = asyncio.Event()
    _setup_signal_handlers(stop_event)
    tasks = await _create_background_tasks(cfg, registry, session)

    try:
        if sys.platform == "win32":
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        else:
            await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("收到键盘中断��正在退出...")
    finally:
        await _shutdown(tasks, registry, session, runner)


async def _run_idle_watcher() -> None:
    """IDLE 环境下的文件监视器——只提示变更，不触发重启。"""
    watcher = FileWatcher(_ROOT)
    mtimes: dict = watcher._scan()
    logger.info("IDLE 文件监��已启动，文件变更时将提示手动重启")

    while True:
        await asyncio.sleep(2.0)
        try:
            current = watcher._scan()
            changed = {
                fp
                for fp, mt in current.items()
                if fp not in mtimes or mtimes[fp] != mt
            }
            mtimes = current

            if changed:
                names = [Path(fp).name for fp in changed]
                logger.info("检测到文件变更: %s", names)
                print(
                    f"\n*** 检测到文件变更 {names}，"
                    "请手动重启服务 (python main.py) ***\n",
                    flush=True,
                )
        except (OSError, ValueError) as exc:
            logger.warning("文件监视检查失败: %s", exc)


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

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Worker 已退出")


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
            return

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
