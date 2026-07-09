"""WebUI 配置与视图模型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

__all__ = [
    "PortableWebUISettings",
    "WebUIServerConfig",
    "SummaryExportPayload",
]


@dataclass(frozen=True)
class PortableWebUISettings:
    """浏览器便携设置默认值。"""

    theme: str = "auto"
    refresh_interval: int = 0
    timeout_ms: int = 6000
    compact: str = "0"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass(frozen=True)
class WebUIServerConfig:
    """WebUI 服务配置。"""

    host: str
    port: int
    webui_path: str = "/"
    summary_path: str = "/v1/webui/summary"
    logs_ws_path: str = "/v1/webui/ws/logs"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


@dataclass(frozen=True)
class SummaryExportPayload:
    """导出摘要负载。"""

    service: str
    version: str
    timestamp: int
    counts: Dict[str, Any] = field(default_factory=dict)
    config: Dict[str, Any] = field(default_factory=dict)
    platforms: Dict[str, Any] = field(default_factory=dict)
    models: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return asdict(self)
