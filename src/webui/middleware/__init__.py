from __future__ import annotations

"""WebUI 中间件导出。"""

from .error_handler import error_middleware
from .static_nocache import static_nocache_middleware

__all__ = ["error_middleware", "static_nocache_middleware"]
