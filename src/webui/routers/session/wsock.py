"""websocket 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 websocket 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

import asyncio
import time

import aiohttp.web

from src.webui.internal.core.logs_ws import log_broker

__all__ = ["logs_ws"]


async def logs_ws(request: aiohttp.web.Request) -> aiohttp.web.WebSocketResponse:
    """提供轻量日志推送 WebSocket。"""
    socket = aiohttp.web.WebSocketResponse(heartbeat=20.0)
    await socket.prepare(request)
    await log_broker.register(socket)
    try:
        await socket.send_json({"type": "hello", "timestamp": int(time.time())})
        # 发送历史日志缓冲
        count = await log_broker.send_history(socket)
        if count > 0:
            await socket.send_json({"type": "history", "count": count})
        while True:
            message = await socket.receive()
            if message.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                break
            if message.type == aiohttp.WSMsgType.TEXT and message.data == "ping":
                await socket.send_json({"type": "pong", "timestamp": int(time.time())})
    except asyncio.CancelledError:
        pass
    finally:
        await log_broker.unregister(socket)
    return socket
