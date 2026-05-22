#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

"""Provider-V2 主入口——Runner-Worker 双进程架构。

Runner 进程：
  - 守护 Worker 子进程
  - 监控退出码，处理自动重启(码42)
  - 信号传递 Ctrl+C 给 Worker

Worker 进程：
  - asyncio 事件循环
  - 初始化全部子系统
  - 永久运行
"""

import asyncio
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import aiohttp
import aiohttp.web

_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.core.config import get_config, start_config_watcher
from src.core.server import create_app
from src.logger import get_logger

logger = get_logger(__name__)

_RESTART_EXIT_CODE = 42


def _make_connector() -> aiohttp.TCPConnector:
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return aiohttp.TCPConnector(ssl=ctx, limit=200, force_close=False)


async def _run() -> None:
    cfg = get_config()
    host = cfg.server.host
    port = cfg.server.port

    connector = _make_connector()
    session = aiohttp.ClientSession(connector=connector)
    app = await create_app(session)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host, port)
    await site.start()

    logger.info("Provider-V2 已启动: http://%s:%d", host, port)

    stop_event = asyncio.Event()

    async def _config_watcher_task() -> None:
        await start_config_watcher(interval=2.0)

    def _on_signal() -> None:
        logger.info("收到退出信号，准备优雅退出...")
        stop_event.set()

    loop = asyncio.get_event_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)

    is_idle_env = _is_idle()
    tasks = [asyncio.ensure_future(_config_watcher_task())]

    try:
        if sys.platform == "win32":
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
        else:
            await stop_event.wait()
    except KeyboardInterrupt:
        logger.info("收到键盘中断")
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("正在关闭 HTTP Session...")
        await session.close()
        logger.info("正在停止 Web 服务器...")
        await runner.cleanup()
        logger.info("Provider-V2 已完全退出")


def _run_worker() -> None:
    """Worker 进程入口。"""
    if sys.platform == "win32" and sys.version_info < (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    elif sys.platform != "win32":
        try:
            import uvloop
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        except Exception:
            logger.debug("uvloop 不可用，使用默认事件循环")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Worker 已退出")


def _run_runner() -> None:
    """Runner 进程入口——守护 Worker 子进程，处理自动重启。"""
    restart_count = 0
    max_restarts = 50
    last_restart_time = time.time()

    while restart_count < max_restarts:
        if time.time() - last_restart_time > 5:
            restart_count = 0
        last_restart_time = time.time()
        restart_count += 1
        logger.info("启动 Worker 进程 [第 %d 次]", restart_count)

        env = os.environ.copy()
        env["WORKER_PROCESS"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["CLICOLOR_FORCE"] = "1"

        python = sys.executable
        args = [python, "-u", str(_ROOT / "main.py")]

        proc = subprocess.Popen(
            args, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        )

        import threading
        def _pipe_output() -> None:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                try:
                    sys.stdout.write(line.decode("utf-8", errors="replace"))
                    sys.stdout.flush()
                except Exception:
                    pass

        threading.Thread(target=_pipe_output, daemon=True).start()

        try:
            while True:
                ret = proc.poll()
                if ret is not None:
                    exit_code = ret
                    break
                time.sleep(0.5)
        except KeyboardInterrupt:
            logger.info("Runner 收到 Ctrl+C，正在终止 Worker...")
            proc.kill()
            proc.wait()
            logger.info("Worker 已终止，Runner 退出")
            return

        logger.info("Worker 进程退出，退出码: %d", exit_code)

        if exit_code == _RESTART_EXIT_CODE:
            logger.info("触发自动重启 (退出码 %d)", _RESTART_EXIT_CODE)
            time.sleep(1.0)
            continue
        else:
            logger.info("Worker 非重启退出 (退出码 %d)，Runner 退出", exit_code)
            break

    if restart_count >= max_restarts:
        logger.error("Worker 重启次数过多 (>%d)，Runner 退出", max_restarts)


def _is_idle() -> bool:
    """检测是否在 IDLE 中运行。"""
    import __main__
    return hasattr(__main__, "run")


def main() -> None:
    is_worker = os.environ.get("WORKER_PROCESS") == "1"

    if _is_idle() and not is_worker:
        print("IDLE 环境下，自动重启不可用。")

        async def _run_with_idle():
            task = asyncio.ensure_future(_run())
            try:
                await task
            except asyncio.CancelledError:
                raise

        if sys.platform == "win32" and sys.version_info < (3, 8):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        try:
            asyncio.run(_run_with_idle())
        except KeyboardInterrupt:
            logger.info("已退出")
    elif is_worker:
        _run_worker()
    else:
        _run_runner()


if __name__ == "__main__":
    main()
