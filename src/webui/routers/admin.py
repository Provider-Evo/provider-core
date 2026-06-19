from __future__ import annotations

"""WebUI 管理端点：服务重载、配置读写。"""

import aiohttp.web

__all__ = ["reload_service", "config_get", "config_put", "config_reload", "persist_get", "persist_put"]


async def reload_service(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/admin/reload — 触发退出码 42 完全重启服务。"""
    import os
    import asyncio

    # 先返回成功响应，再触发重启（避免响应未完成就退出）
    response = aiohttp.web.json_response(
        {"status": "ok", "message": "服务正在重启 (exit code 42)"},
    )

    # 异步触发退出码 42（Runner 进程会自动重启 Worker）
    async def _trigger_restart():
        await asyncio.sleep(0.5)  # 等待响应发送完成
        os._exit(42)

    asyncio.ensure_future(_trigger_restart())
    return response


async def config_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/config — 返回完整配置 JSON（直接读取 config.toml）。"""
    from pathlib import Path

    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # Python < 3.11

    config_path = Path(__file__).resolve().parent.parent.parent.parent / "config.toml"
    try:
        with open(config_path, "rb") as f:
            data = tomllib.load(f)
        return aiohttp.web.json_response(data)
    except FileNotFoundError:
        return aiohttp.web.json_response({"error": "config.toml not found"}, status=404)
    except Exception as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)


async def config_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """PUT /v1/config — 写入配置并重新加载。"""
    from src.core.config import write_config

    try:
        payload = await request.json()
    except Exception:
        return aiohttp.web.json_response(
            {"error": "invalid JSON body"},
            status=400,
        )

    ok = await write_config(payload)
    if ok:
        return aiohttp.web.json_response(
            {"status": "ok", "message": "Config saved and reloaded"},
        )
    return aiohttp.web.json_response(
        {"error": "write failed"},
        status=500,
    )


async def config_reload(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/config/reload — 从文件重新加载配置，丢弃未保存更改。"""
    from src.core.config import reload_config

    ok = await reload_config()
    if ok:
        return aiohttp.web.json_response(
            {"status": "ok", "message": "Config reloaded from file"},
        )
    return aiohttp.web.json_response(
        {"error": "reload failed"},
        status=500,
    )


async def persist_get(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """GET /v1/webui/persist/{filename} — read a JSON/TOML file from persist/webui/."""
    import json
    from pathlib import Path

    filename = request.match_info["filename"]
    if ".." in filename or "/" in filename or "\\" in filename:
        return aiohttp.web.json_response({"error": "invalid filename"}, status=400)
    persist_dir = Path(__file__).resolve().parent.parent.parent.parent / "persist" / "webui"
    filepath = persist_dir / filename
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


async def persist_put(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """POST /v1/webui/persist/{filename} — write JSON/TOML to persist/webui/."""
    import json
    from pathlib import Path

    filename = request.match_info["filename"]
    if ".." in filename or "/" in filename or "\\" in filename:
        return aiohttp.web.json_response({"error": "invalid filename"}, status=400)
    persist_dir = Path(__file__).resolve().parent.parent.parent.parent / "persist" / "webui"
    persist_dir.mkdir(parents=True, exist_ok=True)
    filepath = persist_dir / filename
    try:
        body = await request.json()
        if filename.endswith(".toml"):
            try:
                import tomlkit
                with open(filepath, "w", encoding="utf-8") as f:
                    tomlkit.dump(body, f)
            except ImportError:
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
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(body, f, ensure_ascii=False, indent=2)
        return aiohttp.web.json_response({"status": "ok"})
    except Exception as e:
        return aiohttp.web.json_response({"error": str(e)}, status=500)
