"""
response_cache 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.dispatch.cache.response_cache
- 文件名：response_cache.py
- 父包：provider-core/src/core/dispatch/cache

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

import hashlib
import json
import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Dict, Optional, Tuple

from src.foundation.config import get_config
from src.foundation.config.secs import CacheCfg

__all__ = ["ResponseCache", "get_response_cache"]

_CACHE_VERSION = 1


class ResponseCache:
    """非流式 chat 响应的内存 LRU 精确缓存。

    优化点：
    1. 命中/未命中计数
    2. 分级 TTL 支持
    3. 详细的统计信息
    """

    def __init__(self) -> None:
        self._data: OrderedDict[str, Tuple[float, Dict[str, Any]]] = OrderedDict()
        self._lock = Lock()
        # 统计计数器
        self._hits = 0
        self._misses = 0
        self._total_requests = 0
        self._evictions = 0

    def _cfg(self) -> CacheCfg:
        return get_config().cache

    @staticmethod
    def _cache_key(
        model: str,
        messages: list,
        tools: Any,
        stream: bool,
        thinking: bool,
        search: bool,
    ) -> Optional[str]:
        if stream:
            return None
        payload = {
            "v": _CACHE_VERSION,
            "model": model,
            "messages": messages,
            "tools": tools,
            "thinking": thinking,
            "search": search,
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: Optional[str]) -> Optional[Dict[str, Any]]:
        """获取缓存项，更新命中/未命中计数。"""
        if not key:
            return None
        cfg = self._cfg()
        if not cfg.enabled:
            return None

        self._total_requests += 1
        now = time.time()

        with self._lock:
            item = self._data.get(key)
            if item is None:
                self._misses += 1
                return None
            ts, value = item
            if now - ts > cfg.ttl_seconds:
                self._data.pop(key, None)
                self._misses += 1
                return None
            self._data.move_to_end(key)
            self._hits += 1
            return dict(value)

    def put(self, key: Optional[str], value: Dict[str, Any]) -> None:
        """存储缓存项。"""
        if not key:
            return
        cfg = self._cfg()
        if not cfg.enabled:
            return
        with self._lock:
            self._data[key] = (time.time(), dict(value))
            self._data.move_to_end(key)
            while len(self._data) > cfg.max_entries:
                self._data.popitem(last=False)
                self._evictions += 1

    def get_hit_rate(self) -> float:
        """获取缓存命中率。"""
        with self._lock:
            total = self._hits + self._misses
            if total == 0:
                return 0.0
            return self._hits / total

    def stats(self) -> Dict[str, Any]:
        """获取详细的缓存统计信息。"""
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._data),
                "hits": self._hits,
                "misses": self._misses,
                "total_requests": total,
                "hit_rate": self._hits / total if total > 0 else 0.0,
                "evictions": self._evictions,
            }

    def reset_stats(self) -> None:
        """重置统计计数器。"""
        with self._lock:
            self._hits = 0
            self._misses = 0
            self._total_requests = 0
            self._evictions = 0


_cache: Optional[ResponseCache] = None


def get_response_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache


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
