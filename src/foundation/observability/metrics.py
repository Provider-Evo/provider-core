"""
metrics 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.foundation.observability.metrics
- 文件名：metrics.py
- 父包：provider-core/src/foundation/observability

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

import time
from collections import deque
from typing import Any, Dict

__all__ = ["MetricsRegistry", "get_metrics_registry"]


class MetricsRegistry:
    """进程内 Prometheus 风格指标注册表。

    并发模型：
    - aiohttp 在单线程事件循环中运行协程；不跨线程的纯写函数（无 ``await``）
      视为协作式原子。
    - 因此 ``inc`` / ``set_gauge`` / ``observe`` / ``record_latency`` /
      ``increment_requests`` 不持锁，避免在热路径上阻塞事件循环。
    - 读侧（``get_stats`` / ``render``）先把 dict 快照到副本后再离线计算，
      避免读端长时间占用内部结构。
    """

    # 高频指标名（gateway 热路径直接调用专用方法，跳过 ``_key`` 拼接）
    METRIC_REQUESTS_TOTAL = "provider_gateway_requests_total"
    METRIC_SUCCESS_TOTAL = "provider_gateway_success_total"
    METRIC_FAILURE_TOTAL = "provider_gateway_failure_total"
    METRIC_FALLBACK_TOTAL = "provider_gateway_fallback_total"
    METRIC_LATENCY_MS = "provider_gateway_latency_ms"

    def __init__(self, max_latency_samples: int = 1000) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._hist_sum: Dict[str, float] = {}
        self._hist_count: Dict[str, float] = {}
        self._latency_samples: Dict[str, deque] = {}
        self._max_latency_samples = max_latency_samples
        self._throughput_start = time.monotonic()
        self._request_count = 0

    def inc(self, name: str, value: float = 1.0, labels: str = "") -> None:
        """递增 counter。"""
        key = self._key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value

    def set_gauge(self, name: str, value: float, labels: str = "") -> None:
        """设置 gauge 当前值。"""
        key = self._key(name, labels)
        self._gauges[key] = value

    def observe(self, name: str, value: float, labels: str = "") -> None:
        """记录 histogram 观测值。"""
        key = self._key(name, labels)
        self._hist_sum[key] = self._hist_sum.get(key, 0.0) + value
        self._hist_count[key] = self._hist_count.get(key, 0.0) + 1.0

    def record_latency(self, name: str, value: float, labels: str = "") -> None:
        """记录延迟样本，用于计算百分位数。"""
        key = self._key(name, labels)
        samples = self._latency_samples.get(key)
        if samples is None:
            samples = deque(maxlen=self._max_latency_samples)
            self._latency_samples[key] = samples
        samples.append(value)

    def increment_requests(self) -> None:
        """递增请求数（用于吞吐量计算）。"""
        self._request_count += 1

    def get_percentile(self, name: str, percentile: float, labels: str = "") -> float:
        """获取延迟百分位数。"""
        key = self._key(name, labels)
        samples = self._latency_samples.get(key)
        if not samples:
            return 0.0
        sorted_samples = sorted(samples)
        index = int(len(sorted_samples) * percentile / 100)
        index = min(index, len(sorted_samples) - 1)
        return sorted_samples[index]

    def get_throughput(self) -> float:
        """获取当前吞吐量（请求/秒）。"""
        elapsed = time.monotonic() - self._throughput_start
        if elapsed <= 0:
            return 0.0
        return self._request_count / elapsed

    def get_stats(self) -> Dict[str, Any]:
        """获取详细的统计信息。"""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "throughput_rps": self.get_throughput(),
            "total_requests": self._request_count,
            "latency_percentiles": {
                "p50": self.get_percentile("request_latency_ms", 50),
                "p95": self.get_percentile("request_latency_ms", 95),
                "p99": self.get_percentile("request_latency_ms", 99),
            },
        }

    # === 高频指标 fast path（gateway 热路径专用）==========================
    #
    # 跳过 ``_key`` 字符串拼接与通用 ``inc`` 的额外分派成本；直接在计数器
    # dict 上做 ``+=`` 等价操作。下列方法语义与 ``inc(name)`` 完全一致。

    def inc_requests(self) -> None:
        """``provider_gateway_requests_total`` 专用 fast path。"""
        self._counters[self.METRIC_REQUESTS_TOTAL] = (
            self._counters.get(self.METRIC_REQUESTS_TOTAL, 0.0) + 1.0
        )

    def inc_success(self) -> None:
        """``provider_gateway_success_total`` 专用 fast path。"""
        self._counters[self.METRIC_SUCCESS_TOTAL] = (
            self._counters.get(self.METRIC_SUCCESS_TOTAL, 0.0) + 1.0
        )

    def inc_failure(self) -> None:
        """``provider_gateway_failure_total`` 专用 fast path。"""
        self._counters[self.METRIC_FAILURE_TOTAL] = (
            self._counters.get(self.METRIC_FAILURE_TOTAL, 0.0) + 1.0
        )

    def inc_fallback(self) -> None:
        """``provider_gateway_fallback_total`` 专用 fast path。"""
        self._counters[self.METRIC_FALLBACK_TOTAL] = (
            self._counters.get(self.METRIC_FALLBACK_TOTAL, 0.0) + 1.0
        )

    def observe_latency_ms(self, value_ms: float) -> None:
        """``provider_gateway_latency_ms`` 专用 fast path。"""
        self._hist_sum[self.METRIC_LATENCY_MS] = (
            self._hist_sum.get(self.METRIC_LATENCY_MS, 0.0) + value_ms
        )
        self._hist_count[self.METRIC_LATENCY_MS] = (
            self._hist_count.get(self.METRIC_LATENCY_MS, 0.0) + 1.0
        )

    @staticmethod
    def _key(name: str, labels: str) -> str:
        if not labels:
            return name
        return "{}_{}".format(name, labels)

    def render(self) -> str:
        """渲染 Prometheus 文本 exposition 格式。"""
        counters_snapshot = dict(self._counters)
        gauges_snapshot = dict(self._gauges)
        hist_sum_snapshot = dict(self._hist_sum)
        hist_count_snapshot = dict(self._hist_count)

        lines = [
            "# HELP provider_up Provider process is up.",
            "# TYPE provider_up gauge",
            "provider_up 1",
        ]
        for key, val in sorted(counters_snapshot.items()):
            lines.append("# TYPE {} counter".format(key.split("{")[0]))
            lines.append("{} {}".format(key, val))
        for key, val in sorted(gauges_snapshot.items()):
            lines.append("# TYPE {} gauge".format(key.split("{")[0]))
            lines.append("{} {}".format(key, val))
        for key, total in sorted(hist_sum_snapshot.items()):
            count = hist_count_snapshot.get(key, 0.0)
            if count <= 0:
                continue
            base = key.split("{")[0]
            lines.append("# TYPE {} summary".format(base))
            lines.append("{}_sum {}".format(key, total))
            lines.append("{}_count {}".format(key, count))
        lines.append("# TYPE provider_throughput gauge")
        lines.append("provider_throughput {}".format(self.get_throughput()))
        lines.append("# TYPE provider_request_latency_p50 gauge")
        lines.append(
            "provider_request_latency_p50 {}".format(
                self.get_percentile("request_latency_ms", 50)
            )
        )
        lines.append("# TYPE provider_request_latency_p95 gauge")
        lines.append(
            "provider_request_latency_p95 {}".format(
                self.get_percentile("request_latency_ms", 95)
            )
        )
        lines.append("# TYPE provider_request_latency_p99 gauge")
        lines.append(
            "provider_request_latency_p99 {}".format(
                self.get_percentile("request_latency_ms", 99)
            )
        )
        lines.append("# TYPE provider_metrics_scrape_timestamp gauge")
        lines.append("provider_metrics_scrape_timestamp {}".format(int(time.time())))
        return "\n".join(lines) + "\n"


_registry: "MetricsRegistry | None" = None


def get_metrics_registry() -> MetricsRegistry:
    """返回进程级单例 MetricsRegistry（lazy init）。"""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


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
