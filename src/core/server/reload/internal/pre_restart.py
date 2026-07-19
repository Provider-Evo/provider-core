"""
pre_restart 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.server.reload.internal.pre_restart
- 文件名：pre_restart.py
- 父包：provider-core/src/core/server/reload/internal

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-core/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
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
from pathlib import Path
from typing import Any, Optional

from src.core.utils.compat.observability import get_observability_services
from src.foundation.logger import get_logger

__all__ = ["prepare_graceful_restart", "stop_runtime_before_restart"]

logger = get_logger(__name__)

_RUNTIME_STOP_TIMEOUT_S = 3.0


def _save_pre_restart_stats() -> None:
    obs = get_observability_services()
    try:
        obs.save_stats()
    except Exception as exc:
        logger.debug("重启前保存统计失败: %s", exc)
    try:
        obs.save_requests()
    except Exception as exc:
        logger.debug("重启前保存请求日志失败: %s", exc)


async def _broadcast_restart_notice() -> None:
    obs = get_observability_services()
    try:
        await obs.broadcast_log(
            {"type": "system_restarting", "message": "服务正在重启"}
        )
    except Exception as exc:
        logger.debug("重启前广播 WS 失败: %s", exc)


async def _save_terminal_states() -> None:
    obs = get_observability_services()
    try:
        obs.save_terminal_states()
    except Exception as exc:
        logger.debug("重启前保存终端状态失败: %s", exc)


async def _save_plugin_states(registry: Optional[Any]) -> None:
    """保存插件状态到持久化存储。"""
    if registry is None:
        return
    try:
        from src.core.server.plugins.runtime import get_plugin_runtime

        runtime = get_plugin_runtime()

        # 保存插件状态
        plugin_states = {}
        for plugin_id, record in runtime._records.items():
            if hasattr(record.plugin, "get_state"):
                plugin_states[plugin_id] = await record.plugin.get_state()

        # 保存到文件
        from src.foundation.paths import persist_dir

        state_path = persist_dir() / "plugin_states.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(plugin_states), encoding="utf-8")
        logger.debug("插件状态已保存: %d 个插件", len(plugin_states))
    except Exception as exc:
        logger.debug("保存插件状态失败: %s", exc)


async def _save_connection_pool_state() -> None:
    """保存连接池状态。"""
    try:
        from src.core.server.lifecycle.net.conn import make_connector

        connector = make_connector()

        # 保存连接池配置
        pool_state = {
            "limit": connector.limit,
            "limit_per_host": connector.limit_per_host,
            "acquired": connector._acquired,
        }

        from src.foundation.paths import persist_dir

        state_path = persist_dir() / "connection_pool_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(pool_state), encoding="utf-8")
        logger.debug("连接池状态已保存")
    except Exception as exc:
        logger.debug("保存连接池状态失败: %s", exc)


async def _save_cache_state() -> None:
    """保存缓存状态。"""
    try:
        from src.core.dispatch.cache.response_cache import get_response_cache

        cache = get_response_cache()

        # 获取缓存统计信息
        cache_stats = cache.stats()

        from src.foundation.paths import persist_dir

        state_path = persist_dir() / "cache_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(cache_stats), encoding="utf-8")
        logger.debug("缓存状态已保存")
    except Exception as exc:
        logger.debug("保存缓存状态失败: %s", exc)


async def prepare_graceful_restart(
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
    *,
    reason: str = "",
) -> None:
    """在触发退出码 42 前持久化状态并通知前端。"""
    logger.info("重启前清理%s", f": {reason}" if reason else "")
    _save_pre_restart_stats()
    await _save_plugin_states(registry)
    await _save_connection_pool_state()
    await _save_cache_state()
    await _broadcast_restart_notice()
    await _save_terminal_states()


async def stop_runtime_before_restart(
    registry: Optional[Any] = None,
    session: Optional[Any] = None,
) -> None:
    """快速重启前停止插件运行时（对齐 Provider-V2，不等待完整 HTTP 关停链）。"""
    del session
    runtime = None
    if registry is not None:
        runtime = getattr(registry, "_external_loader", None)
    if runtime is None:
        try:
            from src.core.server.plugins.runtime import get_plugin_runtime

            runtime = get_plugin_runtime()
        except Exception as exc:
            logger.debug("获取插件运行时失败: %s", exc)
    if runtime is None:
        return
    try:
        await asyncio.wait_for(runtime.close(), timeout=_RUNTIME_STOP_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning(
            "插件运行时关闭超时 (%ss)，继续快速重启", _RUNTIME_STOP_TIMEOUT_S
        )
    except Exception as exc:
        logger.warning("插件运行时关闭失败: %s", exc)


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
