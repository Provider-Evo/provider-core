"""WebUI 自动更新控制 API 路由。"""
from __future__ import annotations

import json
from typing import Any, Dict

import aiohttp.web

from src.core.config import get_config, reload_config
from src.logger import get_logger

logger = get_logger(__name__)


def _get_autoupdate_config() -> Dict[str, Any]:
    """获取当前 autoupdate 配置。"""
    cfg = get_config()
    au = cfg.autoupdate
    return {
        "enabled": au.enabled,
        "branch": au.branch,
        "interval": au.interval,
    }


async def autoupdate_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/admin/autoupdate — 获取自动更新配置。"""
    try:
        data = _get_autoupdate_config()
        return aiohttp.web.json_response({"success": True, "data": data})
    except Exception as e:
        logger.error("获取自动更新配置失败: %s", e)
        return aiohttp.web.json_response(
            {"success": False, "error": str(e)}, status=500
        )


async def autoupdate_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/admin/autoupdate — 更新自动更新配置。"""
    try:
        body = await request.json()
        # 直接修改 config.toml 文件
        from pathlib import Path
        import tomlkit

        config_path = Path.cwd() / "config.toml"
        if not config_path.exists():
            return aiohttp.web.json_response(
                {"success": False, "error": "config.toml 不存在"}, status=404
            )

        with open(str(config_path), "r", encoding="utf-8") as f:
            doc = tomlkit.load(f)

        # 确保 [autoupdate] 段存在
        if "autoupdate" not in doc:
            doc["autoupdate"] = tomlkit.table()

        if "enabled" in body:
            doc["autoupdate"]["enabled"] = bool(body["enabled"])
        if "branch" in body:
            doc["autoupdate"]["branch"] = str(body["branch"])
        if "interval" in body:
            doc["autoupdate"]["interval"] = int(body["interval"])

        with open(str(config_path), "w", encoding="utf-8") as f:
            tomlkit.dump(doc, f)

        # 触发热重载
        await reload_config()

        data = _get_autoupdate_config()
        return aiohttp.web.json_response({"success": True, "data": data})
    except Exception as e:
        logger.error("更新自动更新配置失败: %s", e)
        return aiohttp.web.json_response(
            {"success": False, "error": str(e)}, status=500
        )


async def autoupdate_check(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/autoupdate/check — 触发一次立即检查。"""
    try:
        from pathlib import Path
        from src.core.autoupdate import AutoUpdater, get_updater

        cfg = get_config()
        updater = AutoUpdater(
            root=Path(__file__).resolve().parent.parent.parent.parent,
            branch=cfg.autoupdate.branch,
            interval=cfg.autoupdate.interval,
        )
        await updater._check_and_update()
        return aiohttp.web.json_response({"success": True, "message": "检查完成"})
    except Exception as e:
        logger.error("自动更新检查失败: %s", e)
        return aiohttp.web.json_response(
            {"success": False, "error": str(e)}, status=500
        )
