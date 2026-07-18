"""文件监视器 — 健康检查与性能监控混入。"""

from __future__ import annotations

import time

from src.foundation.logger import get_logger

__all__ = ["FileWatcherHealthMixin"]

logger = get_logger(__name__)


class FileWatcherHealthMixin:
    """健康检查、内存/CPU 监控能力混入。

    依赖宿主类提供: _health_check_interval, _last_health_check,
    _health_status, _memory_usage, _cpu_usage, _stats。
    """

    def get_health_status(self) -> dict:
        """返回健康状态信息。"""
        now = time.monotonic()
        if now - self._last_health_check > self._health_check_interval:
            self._perform_health_check()
            self._last_health_check = now

        return {
            "status": self._health_status,
            "memory_usage_mb": self._memory_usage[-1] if self._memory_usage else 0,
            "cpu_usage_percent": self._cpu_usage[-1] if self._cpu_usage else 0,
            "avg_memory_usage_mb": (
                sum(self._memory_usage) / len(self._memory_usage) if self._memory_usage else 0
            ),
            "avg_cpu_usage_percent": (
                sum(self._cpu_usage) / len(self._cpu_usage) if self._cpu_usage else 0
            ),
            "callbacks_succeeded": self._stats.callbacks_succeeded,
            "callbacks_failed": self._stats.callbacks_failed,
            "callbacks_timed_out": self._stats.callbacks_timed_out,
        }

    def _perform_health_check(self) -> None:
        """执行健康检查。"""
        try:
            import psutil

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent()
        except ImportError:
            return
        except Exception as exc:
            self._health_status = "unhealthy"
            logger.error("健康检查失败: %s", exc)
            return

        self._record_health_sample(memory_mb, cpu_percent)
        self._update_health_status(memory_mb)

    def _record_health_sample(self, memory_mb: float, cpu_percent: float) -> None:
        self._memory_usage.append(memory_mb)
        self._cpu_usage.append(cpu_percent)
        if len(self._memory_usage) > 100:
            self._memory_usage.pop(0)
            self._cpu_usage.pop(0)

    def _update_health_status(self, memory_mb: float) -> None:
        if memory_mb > 500:
            self._health_status = "warning"
            logger.warning("文件监视器内存使用过高: %.1f MB", memory_mb)
        elif self._stats.callbacks_failed > 10:
            self._health_status = "degraded"
            logger.warning("文件监视器回调失败次数过多: %d", self._stats.callbacks_failed)
        else:
            self._health_status = "healthy"
