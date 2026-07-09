from __future__ import annotations

"""AItianhu2 平台核心模块。"""

from .client import Aitianhu2Client
from .adaptercore import Adapter, Aitianhu2Adapter

__all__ = ["Adapter", "Aitianhu2Adapter", "Aitianhu2Client"]
