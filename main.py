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
import ssl
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import aiohttp
import aiohttp.web

# 确保 src 在模块搜索路径中
_ROOT = Path(__file__).parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.core.config import get_config, start_config_watcher
from src.core.registry import Registry
from src.core.server import create_app
from src.core.watcher import FileWatcher
from src.logger import get_logger

# 导入 proxy 触发 patch
import src.core.proxy  # noqa: F401

logger = get_logger(__name__)

# Exit code that triggers auto-restart
_RESTART_EXIT_CODE = 42


def _make_connector() -> aiohttp.TCPConnector:
    """创建忽略 SSL 验证的 TCP 连接器。

    Returns:
        TCPConnector 实例。
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return aiohttp.TCPConnector(ssl=ctx, limit=200, force_close=False)


async def _run() -> None:
    """异步主流程——启动所有组件，监听信号，优雅退出。"""
    cfg = get_config()
    host = cfg.server.host
    port = cfg.server.port

    connector = _make_connector()
    session = aiohttp.ClientSession(connector=connector)

    registry = Registry()
    await registry.init(session)

    app = await create_app(registry, session)
    runner = aiohttp.web.AppRunner(app)
    await runner.setup()
    site = aiohttp.web.TCPSite(runner, host, port)
    await site.start()

    logger.info("Provider-V2 已启动: http://%s:%d", host, port)

    # 启动后台任务
    stop_event = asyncio.Event()

    async def _config_watcher_task() -> None:
        await start_config_watcher(interval=2.0)

    async def _file_watcher_task() -> None:
        watcher = FileWatcher(_ROOT)
        await watcher.start(registry, session)

    def _on_signal() -> None:
        logger.info("收到退出信号，准备优雅退出...")
        stop_event.set()

    loop = asyncio.get_event_loop()

    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _on_signal)
    else:
        # Windows 下不支持 add_signal_handler，后续通过 KeyboardInterrupt + 轮询退出
        logger.debug("Windows 平台跳过信号处理器注册")

    # IDLE 下不启动 FileWatcher（由 _run_idle_watcher 替代）
    is_idle_env = _is_idle()
    tasks = [
        asyncio.ensure_future(_config_watcher_task()),
    ]
    if not is_idle_env:
        tasks.append(asyncio.ensure_future(_file_watcher_task()))

    try:
        if sys.platform == "win32":
            # Windows 下轮询等待
            while not stop_event.is_set():
                await asyncio.sleep(1.0)
        else:
            await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("收到键盘中断，正在退出...")
    finally:
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
    """IDLE 环境下的文件监视器，只打印提示不重启。"""
    from src.core.watcher import FileWatcher

    watcher = FileWatcher(_ROOT)
    watcher._registry = None
    watcher._session = None
    watcher._mtimes = watcher._scan()
    logger.info("IDLE 文件监视已启动，文件变更时将提示手动重启")

    while True:
        await asyncio.sleep(2.0)
        try:
            current = watcher._scan()
            changed = {fp for fp, mt in current.items()
                       if fp not in watcher._mtimes or watcher._mtimes[fp] != mt}
            watcher._mtimes = current

            if changed:
                logger.info("检测到文件变更: %s", [Path(f).name for f in changed])
                print("\n*** 检测到文件变更，请手动重启服务 (python main.py) ***\n")
        except Exception as e:
            logger.warning("文件监视检查失败: %s", e)


def _run_worker() -> None:
    """Worker 进程入口。"""
    if sys.platform == "win32" and sys.version_info < (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    elif sys.platform != "win32":
        try:
            import uvloop  # type: ignore[import]

            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        except Exception:
            logger.debug("uvloop 不可用，继续使用默认事件循环")

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Worker 已退出")


def _run_runner() -> None:
    """Runner 进程入口——守护 Worker 子进程，处理自动重启。"""
    restart_count = 0
    max_restarts = 50  # 防止无限重启循环
    last_restart_time = time.time()

    while restart_count < max_restarts:
        # 如果距上次重启不到 5 秒，重置计数器（防止短时间内频繁重启）
        if time.time() - last_restart_time > 5:
            restart_count = 0
        last_restart_time = time.time()

        restart_count += 1
        logger.info("启动 Worker 进程 [第 %d 次]", restart_count)

        env = os.environ.copy()
        env["WORKER_PROCESS"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["CLICOLOR_FORCE"] = "1"  # Worker 通过管道输出，强制保留颜色代码

        python = sys.executable
        args = [python, "-u", str(_ROOT / "main.py")]

        # 使用 PIPE 读取子进程输出，二进制模式避免编码问题
        proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )

        # 后台线程读取子进程输出并打印
        import threading

        def _pipe_output() -> None:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                try:
                    text = line.decode("utf-8", errors="replace")
                    sys.stdout.write(text)
                    sys.stdout.flush()
                except Exception:
                    pass

        threading.Thread(target=_pipe_output, daemon=True).start()

        # 轮询等待子进程退出，让 Ctrl+C 能立即响应
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
            # 短暂延迟，避免频繁重启
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
    """程序入口——跨平台兼容的事件循环启动。"""
    is_worker = os.environ.get("WORKER_PROCESS") == "1"

    # IDLE 下直接运行 Worker（单进程，print 正常输出）
    if _is_idle() and not is_worker:
        print("IDLE 环境下，直接运行 Worker 模式。")
        os.environ["NO_COLOR"] = "1"  # IDLE 不支持 ANSI 颜色
        _run_worker()
    elif is_worker:
        _run_worker()
    else:
        _run_runner()


if __name__ == "__main__":
    main()
