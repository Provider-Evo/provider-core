"""
hook_registry 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.server.plugins.hook_reg
- 文件名：hook_registry.py
- 父包：provider-core/src/core/server/plugins

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

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

from src.foundation.logger import get_logger

__all__ = [
    "HOOK_SPECS",
    "HookRegistry",
    "HookResult",
    "get_hook_registry",
]

HOOK_SPECS: Dict[str, Dict[str, Any]] = {
    "auth.credentials.validate": {
        "description": "校验非 config.toml 的 API 令牌（如 Coplan sk-ent-* 虚拟密钥）",
        "context_keys": ["token"],
        "returns": "valid=True/False；不处理时返回 None",
    },
    "gateway.request.before": {
        "description": "网关分发前调用；可修改 context 或设置 aborted 中止请求",
        "context_keys": ["registry", "messages", "model", "stream", "platform", "tools", "api_token"],
        "returns": "dict 更新 context；aborted=True 时中止",
    },
    "gateway.request.after": {
        "description": "网关分发完成后调用",
        "context_keys": ["registry", "model", "stream", "platform", "candidate_count"],
        "returns": "dict（可选）",
    },
}

logger = get_logger(__name__)

_registry: Optional["HookRegistry"] = None


@dataclass
class HookResult:
    """Hook 执行结果。

    handler 可返回：
    - ``HookResult`` 实例（直接使用）
    - ``dict``（自动包装；包含 ``aborted``/``abort_reason`` 时中断管道）
    - ``None``（管道穿透，继续下一个 handler）
    """
    aborted: bool = False
    abort_reason: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def abort(cls, reason: str = "", **context_updates: Any) -> "HookResult":
        """创建中断结果的快捷方法。"""
        return cls(aborted=True, abort_reason=reason, context=dict(context_updates))

    @classmethod
    def next(cls, **context_updates: Any) -> "HookResult":
        """创建继续管道的结果（带可选 context 更新）。"""
        return cls(context=dict(context_updates))


@dataclass
class _HookHandler:
    plugin_id: str
    handler: Callable[..., Any]
    order: int


class HookRegistry:
    def __init__(self) -> None:
        self._handlers: Dict[str, List[_HookHandler]] = {}

    def clear(self) -> None:
        self._handlers.clear()

    def list_registered(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for hook_point, handlers in sorted(self._handlers.items()):
            for entry in handlers:
                out.append(
                    {
                        "hook_point": hook_point,
                        "plugin_id": entry.plugin_id,
                        "order": entry.order,
                    }
                )
        return out

    def rebuild_from_runtime(self, runtime: Any) -> None:
        """从 PluginRuntime 已加载组件重建 hook 索引。"""
        self.clear()
        for comp in runtime.get_components("hook"):
            plugin_id = str(comp.get("plugin_id", "")).strip()
            meta = comp.get("metadata") or {}
            hook_point = str(meta.get("hook_point", "")).strip()
            handler_name = str(meta.get("handler_name", "")).strip()
            order = int(meta.get("order", 0) or 0)
            if not plugin_id or not hook_point or not handler_name:
                continue
            record = runtime.loaded.get(plugin_id)
            if record is None:
                continue
            handler = getattr(record.plugin, handler_name, None)
            if not callable(handler):
                logger.warning(
                    "插件 %s hook %s 缺少处理器 %s",
                    plugin_id,
                    hook_point,
                    handler_name,
                )
                continue
            self._handlers.setdefault(hook_point, []).append(
                _HookHandler(plugin_id=plugin_id, handler=handler, order=order)
            )
        for handlers in self._handlers.values():
            handlers.sort(key=lambda item: (item.order, item.plugin_id))

    @staticmethod
    def _apply_hook_result(ret: HookResult, ctx: Dict[str, Any], result: HookResult) -> bool:
        """处理 HookResult 类型返回值；返回 True 表示需要中断管道。"""
        if ret.aborted:
            result.aborted = True
            result.abort_reason = ret.abort_reason
            result.context = ctx
            return True
        if ret.context:
            ctx.update(ret.context)
            result.context = ctx
        return False

    @staticmethod
    def _apply_dict_result(ret: Dict[str, Any], ctx: Dict[str, Any], result: HookResult) -> bool:
        """处理 dict 类型返回值（自动包装）；返回 True 表示需要中断管道。"""
        if ret.get("aborted"):
            result.aborted = True
            result.abort_reason = str(
                ret.get("abort_reason") or ret.get("reason") or ""
            )
            result.context = ctx
            return True
        updates = {
            key: value
            for key, value in ret.items()
            if key not in {"aborted", "abort_reason", "reason"}
        }
        if updates:
            ctx.update(updates)
            result.context = ctx
        return False

    async def invoke(self, hook_point: str, context: Dict[str, Any]) -> HookResult:
        """调用指定 hook_point 的所有 handler（管道模式）。

        管道语义：
        - handler 返回 ``HookResult``：直接使用其 aborted/context
        - handler 返回 ``dict``：自动包装；包含 ``aborted`` 时中断
        - handler 返回 ``None``：管道穿透，继续下一个
        """
        ctx = dict(context)
        result = HookResult(context=ctx)
        for entry in self._handlers.get(hook_point, []):
            try:
                ret = entry.handler(ctx)
                if inspect.isawaitable(ret):
                    ret = await ret
            except Exception as exc:
                logger.warning(
                    "Hook 执行失败 [%s] %s: %s",
                    entry.plugin_id,
                    hook_point,
                    exc,
                )
                continue

            # 管道穿透：None 继续下一个 handler
            if ret is None:
                continue

            # HookResult 实例：直接使用
            if isinstance(ret, HookResult):
                if self._apply_hook_result(ret, ctx, result):
                    return result
                continue

            # dict 返回：自动包装
            if not isinstance(ret, dict):
                continue
            if self._apply_dict_result(ret, ctx, result):
                return result
        return result


def get_hook_registry() -> HookRegistry:
    global _registry
    if _registry is None:
        _registry = HookRegistry()
    return _registry
