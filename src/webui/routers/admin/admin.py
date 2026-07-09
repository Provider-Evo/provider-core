from __future__ import annotations

"""WebUI 管理端点：服务重载、配置读写。"""

import aiohttp.web

from src.foundation.paths import config_dir, persist_dir

__all__ = ["reload_service", "persist_get", "persist_put", "bg_image_upload", "bg_image_get"]


async def reload_service(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/reload — 优雅重启（清理运行时后 exit 42）。"""
    import asyncio

    from src.core.server.lifecycle.app import REGISTRY_KEY, SESSION_KEY

    registry = request.app.get(REGISTRY_KEY)
    session = request.app.get(SESSION_KEY)

    response = aiohttp.web.json_response(
        {"status": "ok", "message": "服务正在重启 (exit code 42)"},
    )

    async def _trigger_restart() -> None:
        await asyncio.sleep(0.5)
        from src.core.server.infra.reload.restart import request_process_restart

        await request_process_restart(
            registry=registry,
            session=session,
            reason="admin reload",
        )

    asyncio.ensure_future(_trigger_restart())
    return response


async def persist_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：persist_get。

GET /v1/webui/persist/{filename} — read a JSON/TOML file from config/ or persist/webui/json/."""
    import json

    filename = request.match_info["filename"]
    if ".." in filename or "/" in filename or "\\" in filename:
        return aiohttp.web.json_response({"error": "invalid filename"}, status=400)
    # config.toml 映射到 config/webui_config.toml
    if filename == "config.toml":
        filepath = config_dir() / "webui_config.toml"
    else:
        filepath = persist_dir("webui", "json") / filename
    try:
        if filename.endswith(".toml"):
            import tomllib
            with open(filepath, "rb") as f:
                data = tomllib.load(f)
        else:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        return aiohttp.web.json_response(data)
    except FileNotFoundError:
        return aiohttp.web.json_response(None)
    except Exception as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


def _persist_filepath(filename: str) -> Path:
    from pathlib import Path
    if filename == "config.toml":
        cfg_dir = config_dir()
        cfg_dir.mkdir(parents=True, exist_ok=True)
        return cfg_dir / "webui_config.toml"
    json_dir = persist_dir("webui", "json")
    json_dir.mkdir(parents=True, exist_ok=True)
    return json_dir / filename


def _write_toml_fallback(filepath: Path, body: dict) -> None:
    lines = []
    for k, v in body.items():
        if isinstance(v, bool):
            lines.append(f"{k} = {'true' if v else 'false'}")
        elif isinstance(v, int):
            lines.append(f"{k} = {v}")
        elif isinstance(v, float):
            lines.append(f"{k} = {v}")
        else:
            escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{k} = "{escaped}"')
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _write_persist_body(filepath: Path, filename: str, body: dict) -> None:
    import json
    if filename.endswith(".toml"):
        try:
            import tomlkit
            with open(filepath, "w", encoding="utf-8") as f:
                tomlkit.dump(body, f)
        except ImportError:
            _write_toml_fallback(filepath, body)
        return
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=2)


async def persist_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：persist_put。POST /v1/webui/persist/{filename} — 写入 JSON/TOML。"""
    filename = request.match_info["filename"]
    if ".." in filename or "/" in filename or "\\" in filename:
        return aiohttp.web.json_response({"error": "invalid filename"}, status=400)
    filepath = _persist_filepath(filename)
    try:
        body = await request.json()
        _write_persist_body(filepath, filename, body)
        return aiohttp.web.json_response({"status": "ok"})
    except Exception as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


async def bg_image_upload(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：bg_image_upload。

POST /v1/webui/bg-image — upload a terminal background image to persist/webui/img/."""
    import hashlib

    reader = await request.multipart()
    field = await reader.next()
    if field is None or field.name != "file":
        return aiohttp.web.json_response({"error": "missing file field"}, status=400)

    img_dir = persist_dir("webui", "img")
    img_dir.mkdir(parents=True, exist_ok=True)

    data = await field.read()
    if len(data) > 5 * 1024 * 1024:
        return aiohttp.web.json_response({"error": "file too large (max 5MB)"}, status=400)

    content_type = field.headers.get("Content-Type", "image/png")
    ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif", "image/webp": ".webp"}
    ext = ext_map.get(content_type, ".png")
    file_hash = hashlib.md5(data).hexdigest()[:12]
    filename = f"terminal-bg-{file_hash}{ext}"
    filepath = img_dir / filename

    filepath.write_bytes(data)
    url = f"/v1/webui/bg-image/{filename}"
    return aiohttp.web.json_response({"url": url, "filename": filename})


async def bg_image_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """中文说明：bg_image_get。

GET /v1/webui/bg-image/{filename} — serve a terminal background image."""
    filename = request.match_info["filename"]
    if ".." in filename or "/" in filename or "\\" in filename:
        return aiohttp.web.json_response({"error": "invalid filename"}, status=400)

    img_dir = persist_dir("webui", "img")
    filepath = img_dir / filename

    if not filepath.exists():
        return aiohttp.web.json_response({"error": "not found"}, status=404)

    return aiohttp.web.FileResponse(filepath)
