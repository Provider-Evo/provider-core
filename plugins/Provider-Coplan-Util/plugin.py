"""Provider-Coplan-Util 插件入口。"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp.web
from provider_sdk import ProviderPlugin, Route

from provider_coplan_util.auth import SessionStore, verify_admin_credentials
from provider_coplan_util.brand import BRAND_NAME, BRAND_TITLE, KEY_PREFIX
from provider_coplan_util.config import load_coplan_config
from provider_coplan_util.content import build_public_payload
from provider_coplan_util.standalone import CoplanStandaloneServer
from provider_coplan_util.loader import load_strategy_groups
from provider_coplan_util.spec import SPEC_VERSION, ROUTING_STRATEGIES, alias_count, route_count
from provider_coplan_util.store import StrategyStore
from provider_coplan_util.templates import DEFAULT_PLANS, MARKET_TEMPLATES


def _template_plans() -> List[Dict[str, Any]]:
    return [{**plan, "is_active": True} for plan in DEFAULT_PLANS]


def _bearer_token(request: aiohttp.web.Request) -> str:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def _require_session(plugin: "CoplanUtilPlugin", request: aiohttp.web.Request) -> Optional[Any]:
    return plugin._sessions.get(_bearer_token(request))


def _require_admin(plugin: "CoplanUtilPlugin", request: aiohttp.web.Request) -> Optional[Any]:
    record = _require_session(plugin, request)
    if record is None or record.role != "admin":
        return None
    return record


class CoplanUtilPlugin(ProviderPlugin):
    def __init__(self) -> None:
        self._store: StrategyStore | None = None
        self._sessions = SessionStore()
        self._standalone: Optional[CoplanStandaloneServer] = None

    def _plugin_path(self) -> Path:
        return Path(self.ctx.plugin_dir)

    def _cfg(self):
        return load_coplan_config(self._plugin_path())

    async def on_load(self) -> None:
        data_dir = self._plugin_path() / "data"
        self._store = StrategyStore(data_dir)
        cfg = self._cfg()
        strategies_dir = self._plugin_path() / cfg.strategies_dir
        try:
            definitions = load_strategy_groups(strategies_dir)
            if definitions:
                synced = self._store.sync_code_groups(definitions)
                self.ctx.logger.info(
                    "Coplan strategies: loaded %d group(s) from %s",
                    len(synced),
                    strategies_dir,
                )
        except ValueError as exc:
            self.ctx.logger.error("Coplan strategies 加载失败: %s", exc)
        self._store.ensure_default_group()
        self.ctx.logger.info(
            "Provider-Coplan-Util: loaded (brand: %s, key_prefix: %s)",
            BRAND_NAME,
            KEY_PREFIX,
        )
        if cfg.standalone_enabled and cfg.standalone_port > 0:
            self._standalone = CoplanStandaloneServer(self)
            try:
                await self._standalone.start(
                    cfg.standalone_host,
                    cfg.standalone_port,
                    access_log=cfg.standalone_access_log,
                )
            except OSError as exc:
                self.ctx.logger.warning("Coplan standalone 启动失败: %s", exc)
                self._standalone = None

    async def on_unload(self) -> None:
        if self._standalone is not None:
            await self._standalone.stop()
            self._standalone = None

    @Route("/v1/coplan/public", methods=["GET"])
    async def public_content(self) -> Dict[str, Any]:
        assert self._store is not None
        cfg = self._cfg()
        payload = build_public_payload(cfg, self._store.get_settings(), MARKET_TEMPLATES)
        if self._standalone is not None and self._standalone.running:
            payload["standalone_url"] = f"http://{cfg.standalone_host}:{cfg.standalone_port}/"
        payload["plans"] = _template_plans()
        return payload

    @Route("/api/auth/login", methods=["POST"])
    async def auth_login(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        try:
            body = await request.json()
        except Exception:
            return aiohttp.web.json_response({"success": False, "error": "invalid json"}, status=400)
        username = str(body.get("username") or "")
        password = str(body.get("password") or "")
        cfg = self._cfg()
        if not verify_admin_credentials(username, password, cfg.admin_username, cfg.admin_password):
            return aiohttp.web.json_response(
                {"success": False, "error": "用户名或密码错误"},
                status=401,
            )
        token = self._sessions.issue(cfg.admin_username, role="admin")
        return aiohttp.web.json_response({
            "success": True,
            "token": token,
            "user": {"username": cfg.admin_username, "role": "admin"},
        })

    @Route("/api/auth/register", methods=["POST"])
    async def auth_register(self, _request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response(
            {"success": False, "error": "暂未开放自助注册，请使用管理员账号或联系管理员开通"},
            status=403,
        )

    @Route("/api/auth/me", methods=["GET"])
    async def auth_me(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        record = _require_session(self, request)
        if record is None:
            return aiohttp.web.json_response({"error": "未登录或令牌无效"}, status=401)
        return aiohttp.web.json_response({
            "user": {"username": record.username, "role": record.role},
        })

    @Route("/api/auth/change-password", methods=["POST"])
    async def auth_change_password(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        record = _require_session(self, request)
        if record is None:
            return aiohttp.web.json_response({"error": "未登录"}, status=401)
        return aiohttp.web.json_response(
            {"error": "请直接修改插件 config.toml 中 [admin] 密码后重启插件"},
            status=501,
        )

    @Route("/api/user/usage", methods=["GET"])
    async def user_usage(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_session(self, request) is None:
            return aiohttp.web.json_response({"error": "未登录"}, status=401)
        assert self._store is not None
        key_count = self._store.key_count()
        return aiohttp.web.json_response({
            "activePlan": _template_plans()[0] if MARKET_TEMPLATES else None,
            "currentPeriodUsage": {
                "requests_5h": 0,
                "requests_month": key_count,
            },
            "total": {"total_requests": key_count, "total_input_tokens": 0, "total_output_tokens": 0},
            "usage": [],
        })

    @Route("/api/user/api-keys", methods=["GET"])
    async def user_api_keys(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_session(self, request) is None:
            return aiohttp.web.json_response({"error": "未登录"}, status=401)
        assert self._store is not None
        keys = []
        for row in self._store.list_keys_flat():
            keys.append({
                "id": row.get("id"),
                "key": row.get("key"),
                "label": row.get("label") or row.get("group_name") or "",
                "is_active": row.get("is_active", True),
                "created_at": row.get("created_at"),
                "group_id": row.get("group_id"),
            })
        return aiohttp.web.json_response({"keys": keys})

    @Route("/api/user/api-keys", methods=["POST"])
    async def user_create_api_key(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_session(self, request) is None:
            return aiohttp.web.json_response({"error": "未登录"}, status=401)
        assert self._store is not None
        try:
            body = await request.json()
        except Exception:
            body = {}
        label = str(body.get("label") or "")
        group_id = str(body.get("group_id") or "")
        if not group_id:
            group_id = self._store.ensure_default_group()["id"]
        try:
            key_entry = self._store.add_key(group_id, label=label)
        except KeyError:
            return aiohttp.web.json_response({"error": "策略组不存在"}, status=404)
        return aiohttp.web.json_response({"key": key_entry["key"], "entry": key_entry})

    @Route("/api/user/api-keys/{key_id}", methods=["DELETE"])
    async def user_revoke_api_key(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_session(self, request) is None:
            return aiohttp.web.json_response({"error": "未登录"}, status=401)
        assert self._store is not None
        key_id = request.match_info.get("key_id", "")
        if not self._store.revoke_key(key_id):
            return aiohttp.web.json_response({"error": "密钥不存在"}, status=404)
        return aiohttp.web.json_response({"success": True})

    @Route("/api/user/plans", methods=["GET"])
    async def user_plans(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_session(self, request) is None:
            return aiohttp.web.json_response({"error": "未登录"}, status=401)
        plans = _template_plans()
        if plans:
            active = dict(plans[0])
            active["activated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        else:
            active = None
        return aiohttp.web.json_response({
            "plans": [{**p, "activated_at": time.strftime("%Y-%m-%d %H:%M:%S")} for p in plans],
            "activePlan": active,
        })

    @Route("/v1/coplan/admin/settings", methods=["GET"])
    async def admin_settings_get(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        record = _require_session(self, request)
        if record is None or record.role != "admin":
            return aiohttp.web.json_response({"error": "需要管理员权限"}, status=403)
        assert self._store is not None
        cfg = self._cfg()
        settings = self._store.get_settings()
        admin_contact = settings.get("admin_contact") or cfg.admin_contact
        return aiohttp.web.json_response({"settings": {"admin_contact": admin_contact}})

    @Route("/v1/coplan/admin/settings", methods=["PUT"])
    async def admin_settings_put(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        record = _require_session(self, request)
        if record is None or record.role != "admin":
            return aiohttp.web.json_response({"error": "需要管理员权限"}, status=403)
        assert self._store is not None
        try:
            body = await request.json()
        except Exception:
            return aiohttp.web.json_response({"error": "invalid json"}, status=400)
        saved = self._store.save_settings({
            "admin_contact": str(body.get("admin_contact") or ""),
        })
        return aiohttp.web.json_response({"success": True, "settings": saved})

    @Route("/v1/coplan/status", methods=["GET"])
    async def status(self) -> Dict[str, Any]:
        groups = self._store.list_groups() if self._store else []
        cfg = self._cfg()
        payload = {
            "brand": BRAND_NAME,
            "brand_title": BRAND_TITLE,
            "key_prefix": KEY_PREFIX,
            "hero_tagline": cfg.hero_tagline,
            "strategy_groups": len(groups),
            "market_templates": len(MARKET_TEMPLATES),
            "api_keys": self._store.key_count() if self._store else 0,
            **cfg.as_public_dict(),
        }
        if self._standalone is not None and self._standalone.running:
            payload["standalone_url"] = f"http://{cfg.standalone_host}:{cfg.standalone_port}/"
        return payload

    @Route("/v1/coplan/strategy-groups", methods=["GET"])
    async def list_groups(self) -> Dict[str, Any]:
        assert self._store is not None
        groups = []
        for group in self._store.list_groups():
            spec = group.get("spec") or {}
            groups.append({
                **group,
                "alias_count": alias_count(spec),
                "route_count": route_count(spec),
            })
        return {"groups": groups, "spec_version": SPEC_VERSION}

    @Route("/v1/coplan/strategy-spec", methods=["GET"])
    async def strategy_spec_doc(self) -> Dict[str, Any]:
        return {
            "spec_version": SPEC_VERSION,
            "routing_strategies": sorted(ROUTING_STRATEGIES),
            "strategies_dir": self._cfg().strategies_dir,
            "python_entry": "STRATEGY_GROUPS",
            "route_fields": ["model", "platform?", "weight?", "params?"],
            "alias_fields": ["match?", "strategy", "routes", "description?"],
            "group_fields": [
                "id",
                "name",
                "description?",
                "aliases",
                "default?",
                "constraints?",
                "limits?",
            ],
        }

    @Route("/v1/coplan/strategy-groups/{group_id}/spec", methods=["GET"])
    async def get_group_spec(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert self._store is not None
        group_id = request.match_info.get("group_id", "")
        group = self._store.get_group(group_id)
        if group is None:
            return aiohttp.web.json_response({"error": "group not found"}, status=404)
        return aiohttp.web.json_response({"group": group})

    @Route("/v1/coplan/strategy-groups/{group_id}/spec", methods=["PUT"])
    async def put_group_spec(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_admin(self, request) is None:
            return aiohttp.web.json_response({"error": "需要管理员权限"}, status=403)
        assert self._store is not None
        group_id = request.match_info.get("group_id", "")
        try:
            body = await request.json()
        except Exception:
            return aiohttp.web.json_response({"error": "invalid json"}, status=400)
        spec_raw = body.get("spec") if isinstance(body.get("spec"), dict) else body
        try:
            group = self._store.update_spec(group_id, spec_raw)
        except PermissionError as exc:
            return aiohttp.web.json_response({"error": str(exc)}, status=403)
        except (KeyError, ValueError) as exc:
            return aiohttp.web.json_response({"error": str(exc)}, status=400)
        return aiohttp.web.json_response({"group": group})

    @Route("/v1/coplan/strategy-groups", methods=["POST"])
    async def create_group(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_admin(self, request) is None:
            return aiohttp.web.json_response({"error": "需要管理员权限"}, status=403)
        assert self._store is not None
        try:
            body = await request.json()
        except Exception:
            return aiohttp.web.json_response({"error": "invalid json"}, status=400)
        name = str(body.get("name") or "").strip()
        if not name:
            return aiohttp.web.json_response({"error": "name required"}, status=400)
        try:
            group = self._store.create_group(name, str(body.get("description") or ""))
        except ValueError as exc:
            return aiohttp.web.json_response({"error": str(exc)}, status=400)
        return aiohttp.web.json_response({"group": group})

    @Route("/v1/coplan/strategy-groups/{group_id}", methods=["DELETE"])
    async def delete_group(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_admin(self, request) is None:
            return aiohttp.web.json_response({"error": "需要管理员权限"}, status=403)
        assert self._store is not None
        group_id = request.match_info.get("group_id", "")
        try:
            if not self._store.delete_group(group_id):
                return aiohttp.web.json_response({"error": "group not found"}, status=404)
        except PermissionError as exc:
            return aiohttp.web.json_response({"error": str(exc)}, status=403)
        return aiohttp.web.json_response({"success": True})

    @Route("/v1/coplan/strategy-groups/{group_id}/keys", methods=["POST"])
    async def add_key(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        record = _require_session(self, request)
        if record is None:
            return aiohttp.web.json_response({"error": "未登录"}, status=401)
        assert self._store is not None
        group_id = request.match_info.get("group_id", "")
        try:
            body = await request.json()
        except Exception:
            body = {}
        label = str(body.get("label") or "")
        try:
            key_entry = self._store.add_key(group_id, label=label)
        except KeyError:
            return aiohttp.web.json_response({"error": "group not found"}, status=404)
        return aiohttp.web.json_response({"key": key_entry})

    @Route("/v1/coplan/strategy-groups/{group_id}/keys/{key_id}", methods=["DELETE"])
    async def delete_key(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        if _require_admin(self, request) is None:
            return aiohttp.web.json_response({"error": "需要管理员权限"}, status=403)
        assert self._store is not None
        group_id = request.match_info.get("group_id", "")
        key_id = request.match_info.get("key_id", "")
        if not self._store.delete_key(group_id, key_id):
            return aiohttp.web.json_response({"error": "key not found"}, status=404)
        return aiohttp.web.json_response({"success": True})

    @Route("/v1/coplan/market/templates", methods=["GET"])
    async def market_templates(self) -> Dict[str, Any]:
        return {"templates": MARKET_TEMPLATES, "brand": BRAND_NAME, "plans": _template_plans()}

    @Route("/coplan", methods=["GET"])
    async def user_page(self) -> aiohttp.web.Response:
        html_path = self._plugin_path() / "static" / "index.html"
        if not html_path.is_file():
            return aiohttp.web.Response(text="Coplan UI missing", status=404)
        return aiohttp.web.Response(
            text=html_path.read_text(encoding="utf-8"),
            content_type="text/html",
        )

    @Route("/coplan/admin", methods=["GET"])
    async def admin_page(self) -> aiohttp.web.Response:
        html_path = self._plugin_path() / "static" / "admin.html"
        if not html_path.is_file():
            return aiohttp.web.Response(text="Coplan admin UI missing", status=404)
        return aiohttp.web.Response(
            text=html_path.read_text(encoding="utf-8"),
            content_type="text/html",
        )


def create_plugin() -> CoplanUtilPlugin:
    return CoplanUtilPlugin()
