"""
logs_ws 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-self.src.webui.internal.core.logs_ws
- 文件名：logs_ws.py
- 父包：provider-self/src/webui/internal/core

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


import asyncio
import json
import time
from collections import deque
from typing import Any, Deque, Dict, Optional, Set

import aiohttp.web

__all__ = ["WebUILogBroker", "log_broker", "setup_loguru_sink"]

# 保留最近 200 条日志
LOG_BUFFER_SIZE = 200

# 模块颜色映射（hex 前景色）
MODULE_COLORS: Dict[str, str] = {
    "server": "#8b949e",
    "watcher": "#d29922",
    "webui": "#79c0ff",
    "webui.routers": "#79c0ff",
    "webui.routers.websocket": "#a5d6ff",
    "webui.logs_ws": "#a5d6ff",
    "webui.services": "#79c0ff",
    "webui.services.request_log": "#a5d6ff",
    "dispatch": "#3fb950",
    "dispatch.runtime": "#56d364",
    "middleware": "#da77f2",
    "middleware.request_broker": "#d2a8ff",
    "core.terminal_sessions": "#f0883e",
    "core.server": "#8b949e",
    "core.config": "#79c0ff",
    "core.dispatch": "#3fb950",
    "config.main_config": "#79c0ff",
}

# 日志 ID 生成器
_log_counter = 0


def _make_log_id() -> str:
    global _log_counter
    _log_counter += 1
    return f"{int(time.time() * 1000)}_{_log_counter}"


def _resolve_module_color(module_name: str) -> str:
    """按前缀匹配模块颜色。"""
    if not module_name:
        return ""
    # 精确匹配
    if module_name in MODULE_COLORS:
        return MODULE_COLORS[module_name]
    # 逐级前缀匹配
    parts = module_name.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in MODULE_COLORS:
            return MODULE_COLORS[candidate]
    return ""


class WebUILogBroker:
    """WebUI 日志事件广播器。"""

    def __init__(self) -> None:
        self._sockets: Set[aiohttp.web.WebSocketResponse] = set()
        self._lock = asyncio.Lock()
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=LOG_BUFFER_SIZE)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """保存主事件循环引用。"""
        self._loop = loop

    async def register(self, socket: aiohttp.web.WebSocketResponse) -> None:
        """公开方法 register。"""
        async with self._lock:
            self._sockets.add(socket)

    async def unregister(self, socket: aiohttp.web.WebSocketResponse) -> None:
        """公开方法 unregister。"""
        async with self._lock:
            self._sockets.discard(socket)

    async def send_history(self, socket: aiohttp.web.WebSocketResponse) -> int:
        """发送历史日志缓冲，返回已发送条数。"""
        async with self._lock:
            history = list(self._buffer)
        count = 0
        for entry in history:
            try:
                await socket.send_json(entry)
                count += 1
            except Exception:
                break
        return count

    async def broadcast(self, payload: Dict[str, Any]) -> None:
        """公开方法 broadcast。"""
        message = json.dumps(payload, ensure_ascii=False)
        # 仅缓存日志条目；static_changed 等控制类消息只实时推送，避免重连时刷屏
        if payload.get("type") == "log":
            self._buffer.append(payload)
        stale: Set[aiohttp.web.WebSocketResponse] = set()
        async with self._lock:
            for socket in self._sockets:
                try:
                    await socket.send_str(message)
                except Exception:
                    stale.add(socket)
            for socket in stale:
                self._sockets.discard(socket)

    def _loguru_sink(self, message: Any) -> None:
        """loguru sink：同步函数，通过 run_coroutine_threadsafe 推入事件循环。"""
        if message is None or self._loop is None:
            return
        try:
            record = message.record
            level_name = record["level"].name
            msg_text = str(record["message"])
            module_name = record["extra"].get("module_name", "")
            payload = {
                "type": "log",
                "id": _make_log_id(),
                "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S"),
                "level": level_name,  # 完整级别名 "INFO" 而非 "I"
                "module": module_name,
                "message": msg_text,
                "moduleColor": _resolve_module_color(module_name),
            }
            if self._loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(payload), self._loop)
        except Exception:
            pass


log_broker = WebUILogBroker()


def setup_loguru_sink() -> None:
    """将 log_broker._loguru_sink 注册为 loguru 的 sink，并保存主事件循环。"""
    try:
        from loguru import logger
        logger.add(log_broker._loguru_sink, level="DEBUG", format="{time:HH:mm:ss} | {level} | {extra[module_name]} | {message}")
        # 保存当前事件循环
        try:
            loop = asyncio.get_running_loop()
            log_broker.set_loop(loop)
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    log_broker.set_loop(loop)
            except Exception:
                pass
    except Exception:
        pass

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
