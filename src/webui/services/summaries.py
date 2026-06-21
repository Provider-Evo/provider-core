from __future__ import annotations

"""WebUI 摘要服务。"""

from typing import Any, Dict

from src.core.dispatch.runtime_view import build_runtime_summary
from src.webui.config_schema import SummaryExportPayload

__all__ = ["build_summary_payload", "build_export_payload"]


async def build_summary_payload(registry: Any) -> Dict[str, Any]:
    """构建 WebUI 摘要字典。"""
    return await build_runtime_summary(registry)


async def build_export_payload(registry: Any) -> Dict[str, Any]:
    """构建可导出的安全摘要。"""
    summary = await build_runtime_summary(registry)
    payload = SummaryExportPayload(
        service=summary.get("service", "Provider-V2"),
        version=summary.get("config", {}).get("server", {}).get("version", ""),
        timestamp=summary.get("timestamp", 0),
        counts=summary.get("counts", {}),
        config=summary.get("config", {}),
        platforms=summary.get("platforms", {}),
        models=summary.get("models", []),
    )
    return payload.to_dict()
