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
  - 初始化全部子系统
  - 永久运行直到收到退出信号或触发重启

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
from typing import IO, List

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


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _is_idle() -> bool:
    """检测当前是否在 Python IDLE 环境中运行。

    通过检查标准输出类型来判断：IDLE 将 sys.stdout 替换为自定义对象，
    而非标准的 ``TextIOWrapper``。此方法比检查 ``__main__`` 属性更可靠。

    Returns:
        在 IDLE 中运行时返回 True。
    """
    import io
    return not isinstance(sys.stdout, io.TextIOWrapper)


def _read_color_config() -> bool:
    """从 config.toml 读取 debug.color 配置项。

    在 Python 3.11+ 使用标准库 tomllib；低版本尝试第三方 tomli；
    均不可用或文件不存在时默认返回 True（启用颜色）。

    Returns:
        color 配置值，默认 True。
    """
    cfg_path = _ROOT / "config.toml"
    if not cfg_path.exists():
        return True

    if sys.version_info >= (3, 11):
        import tomllib
        try:
            with open(cfg_path, "rb") as fh:
                raw = tomllib.load(fh)
            return bool(raw.get("debug", {}).get("color", True))
        except Exception:
            return True

    try:
        import tomli  # type: ignore[import]
        with open(cfg_path, "rb") as fh:
            raw = tomli.load(fh)
        return bool(raw.get("debug", {}).get("color", True))
    except ImportError:
        logger.debug("tomli 未安装，跳过 color 配置读取，默认启用颜色")
        return True
    except Exception:
        return True


def _make_connector() -> aiohttp.TCPConnector:
    """创建忽略 SSL 证书验证的 TCP 连接器。

    Returns:
        配置好的 TCPConnector 实例。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return aiohttp.TCPConnector(ssl=ctx, limit=200, force_close=False)


# ---------------------------------------------------------------------------
# Worker：异步主流程
# ---------------------------------------------------------------------------


async def _run() -> None:
    """Worker 的异步主流程——启动所有组件，等待退出信号，优雅关闭。"""
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

    # 检查并释放端口占用
    port_result = ensure_port_available(port, cfg.server.startup_force_kill_port)
    if port_result.occupied and not port_result.released:
        if cfg.server.startup_force_kill_port:
            logger.error(
                "端口 %d 被占用 (PIDs: %s)，已尝试强制终止但未能释放",
                port,
                port_result.pids,
            )
        else:
            logger.error(
                "端口 %d 被占用 (PIDs: %s)，startup_force_kill_port=false 未强制释放",
                port,
                port_result.pids,
            )

    runner = aiohttp.web.AppRunner(app, access_log=_access_log)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host, port)
    await site.start()

    logger.info("Provider-V2 已启动: http://%s:%d", host, port)

    # ------------------------------------------------------------------
    # 信号处理
    # ------------------------------------------------------------------

    stop_event = asyncio.Event()

    def _on_signal() -> None:
        logger.info("收到退出信号，准备优雅退出...")
        stop_event.set()

    loop = asyncio.get_event_loop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)
    else:
        logger.debug("Windows 平台：信号处理器通过 KeyboardInterrupt 捕获")

    # ------------------------------------------------------------------
    # 后台任务
    # ------------------------------------------------------------------

    is_idle_env = _is_idle()

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

    tasks: List[asyncio.Future] = [
        asyncio.ensure_future(_config_watcher_task()),
    ]

    if not is_idle_env:
        tasks.append(asyncio.ensure_future(_file_watcher_task()))

    if cfg.autoupdate.enabled and not is_idle_env:
        tasks.append(asyncio.ensure_future(_autoupdate_task()))

    # ------------------------------------------------------------------
    # 等待退出信号
    # ------------------------------------------------------------------

    try:
        if sys.platform == "win32":
            while not stop_event.is_set():
                await asyncio.sleep(0.5)
        else:
            await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("收到键盘中断，正在退出...")
    finally:
        logger.info("取消后台任务...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("正在关闭注册表...")
        await registry.close()

        logger.info("正在关闭 HTTP Session...")
        await session.close()

        logger.info("正在停止 Web 服务器...")
        await runner.cleanup()

        logger.info("Provider-V2 已完全退出")


async def _run_idle_watcher() -> None:
    """IDLE 环境下的文件监视器——只提示变更，不触发重启。"""
    watcher = FileWatcher(_ROOT)
    mtimes: dict = watcher._scan()
    logger.info("IDLE 文件监视已启动，文件变更时将提示手动重启")

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
        except Exception as exc:
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
        except ImportError:
            logger.debug("uvloop 未安装，使用默认事件循环")
        except Exception as exc:
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
        except Exception:
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
    - 若在 ``_RAPID_RESTART_THRESHOLD`` 秒内连续快速重启超过
      ``_MAX_RAPID_RESTARTS`` 次，Runner 放弃重启并退出。
    - Worker 以其他退出码退出时，Runner 直接退出（不重启）。
    - Runner 收到 Ctrl+C 时，立即终止 Worker 并退出。
    """
    color_enabled = _read_color_config()
    worker_env = _build_worker_env(color_enabled)

    python = sys.executable
    args = [python, "-u", str(_ROOT / "main.py")]

    rapid_restart_count = 0
    last_start_time: float = 0.0

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
                    "Worker 在 %.1f 秒内连续快速重启 %d 次，Runner 放弃重启并退出",
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
            logger.error("无法启动 Worker 进程: %s", exc)
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
            while True:
                ret = proc.poll()
                if ret is not None:
                    exit_code = ret
                    break
                time.sleep(0.3)
        except KeyboardInterrupt:
            logger.info("Runner 收到 Ctrl+C，正在终止 Worker (PID=%d)...", proc.pid)
            proc.kill()
            proc.wait()
            reader_thread.join(timeout=2.0)
            logger.info("Worker 已终止，Runner 退出")
            return

        reader_thread.join(timeout=2.0)
        logger.info("Worker 进程退出，退出码: %d (PID=%d)", exit_code, proc.pid)

        # ------------------------------------------------------------------
        # 根据退出码决策
        # ------------------------------------------------------------------
        if exit_code == _RESTART_EXIT_CODE:
            logger.info(
                "触发自动重启（退出码 %d），冷却 %.1f 秒后重启...",
                _RESTART_EXIT_CODE,
                _RESTART_COOLDOWN,
            )
            time.sleep(_RESTART_COOLDOWN)
        else:
            logger.info("Worker 正常退出（退出码 %d），Runner 退出", exit_code)
            break


# ---------------------------------------------------------------------------
# 程序入口
# ---------------------------------------------------------------------------


def main() -> None:
    """程序主入口——根据运行环境选择合适的启动模式。

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
