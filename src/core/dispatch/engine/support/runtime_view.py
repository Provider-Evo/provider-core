"""
runtime_view 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.dispatch.engine.runtime_view
- 文件名：runtime_view.py
- 父包：provider-core/src/core/dispatch/engine

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


import time
from typing import Any, Dict, List

from src.foundation.config import get_config

__all__ = [
    "collect_platform_status",
    "collect_model_entries",
    "build_config_summary",
    "build_runtime_summary",
]


async def collect_platform_status(registry: Any) -> Dict[str, Dict[str, Any]]:
    """收集平台状态摘要。

    Args:
        registry: 平台注册表。

    Returns:
        以平台名为键的平台状态字典。
    """
    result: Dict[str, Dict[str, Any]] = {}
    for name, adapter in registry.adapters.items():
        try:
            candidates = await adapter.candidates()
            result[name] = {
                "candidates": len(candidates),
                "available": len(
                    [candidate for candidate in candidates if candidate.available and not candidate.busy]
                ),
                "models": len(adapter.supported_models),
                "context_length": getattr(adapter, "context_length", None),
            }
        except Exception as exc:
            result[name] = {"error": str(exc)}
    return result


async def collect_model_entries(registry: Any) -> List[Dict[str, Any]]:
    """收集模型列表。

    Args:
        registry: 平台注册表。

    Returns:
        模型字典列表。
    """
    return await registry.all_models()


def _config_server_section(config: Any) -> Dict[str, Any]:
    return {
        "version": config.server.version,
        "host": config.server.host,
        "port": config.server.port,
        "debug": config.server.debug,
        "startup_force_kill_port": config.server.startup_force_kill_port,
    }


def _config_auth_gateway_proxy(config: Any) -> Dict[str, Any]:
    return {
        "auth": {
            "enabled": config.auth.enabled,
            "keys_count": len(config.auth.keys),
            "group_list_type": config.auth.group_list_type,
            "group_count": len(config.auth.group_list),
        },
        "gateway": {
            "concurrent_enabled": config.gateway.concurrent_enabled,
            "concurrent_count": config.gateway.concurrent_count,
            "min_tokens": config.gateway.min_tokens,
            "group_list_type": config.gateway.group_list_type,
            "group_count": len(config.gateway.group_list),
        },
        "proxy": {
            "proxy_enabled": config.proxy.proxy_enabled,
            "proxy_server": config.proxy.proxy_server,
            "proxy_rules": len(config.proxy.proxy_urls),
        },
    }


def build_config_summary() -> Dict[str, Any]:
    """构建安全配置摘要。"""
    config = get_config()
    summary = {"server": _config_server_section(config)}
    summary.update(_config_auth_gateway_proxy(config))
    summary.update({
        "adapter_proxy": {
            "enable_adapters": list(config.adapter_proxy.enable_adapters),
            "group_list_type": config.adapter_proxy.group_list_type,
        },
        # 向后兼容
        "platforms_proxy": {
            "enabled_platforms": list(config.platforms_proxy.enabled_platforms),
            "group_list_type": config.platforms_proxy.group_list_type,
        },
        "platforms": {
            "list_type": config.platforms_cfg.platform_list_type,
            "count": len(config.platforms_cfg.platform_list),
        },
        "debug": {
            "level": config.debug.level,
            "color": config.debug.color,
            "access_log": config.debug.access_log,
        },
        "fncall": {
            "protocol": config.fncall.protocol,
            "record_prompt": config.fncall.record_prompt,
            "print_prompt": config.fncall.print_prompt,
        },
        "autoupdate": {
            "enabled": config.autoupdate.enabled,
            "branch": config.autoupdate.branch,
            "interval": config.autoupdate.interval,
            "diff_update": config.autoupdate.diff_update,
            "mirrors": list(config.autoupdate.mirrors),
        },
    })
    return summary


async def build_runtime_summary(registry: Any) -> Dict[str, Any]:
    """构建 WebUI 摘要载荷。

    Args:
        registry: 平台注册表。

    Returns:
        WebUI 所需的只读汇总字典。
    """
    platforms = await collect_platform_status(registry)
    models = await collect_model_entries(registry)
    return {
        "service": "Provider-V2",
        "timestamp": int(time.time()),
        "config": build_config_summary(),
        "platforms": platforms,
        "models": models,
        "capabilities": {
            name: adapter.default_capabilities
            for name, adapter in registry.adapters.items()
        },
        "counts": {
            "platforms": len(platforms),
            "models": len(models),
            "available_platforms": len(
                [name for name, info in platforms.items() if info.get("available", 0) > 0]
            ),
        },
    }

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
