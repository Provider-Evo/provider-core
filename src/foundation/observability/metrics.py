
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
