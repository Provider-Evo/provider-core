from __future__ import annotations

"""WebUI 中间件导出。"""

from .auth import auth_middleware
from .error_handler import error_middleware
from .static_nocache import static_nocache_middleware
from .stats import stats_middleware

__all__ = [
    "auth_middleware",
    "error_middleware",
    "stats_middleware",
    "static_nocache_middleware",
]
