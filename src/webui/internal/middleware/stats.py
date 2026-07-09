from __future__ import annotations

"""请求统计中间件 — 使用 echotools 通用实现。"""

from echotools.web.middleware import create_stats_middleware
from src.webui.services.stats import get_stats
from src.webui.services.request_log import request_broker

__all__ = ["stats_middleware"]

# 创建中间件实例（依赖注入）
stats_middleware = create_stats_middleware(get_stats(), request_broker)
