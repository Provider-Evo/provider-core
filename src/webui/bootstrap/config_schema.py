"""config_schema 模块 — WebUI 层。

职责：
    作为 Provider-Evo 项目标准模块，提供 config_schema 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

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
    stream_idle_timeout_ms: int = 60000
    compact: str = "0"
    font_size_base: int = 14

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
