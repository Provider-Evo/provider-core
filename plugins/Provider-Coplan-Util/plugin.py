"""Provider-Coplan-Util 插件入口。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from provider_sdk import ProviderPlugin

from provider_coplan_util.auth.auth import SessionStore
from provider_coplan_util import BRAND_NAME, KEY_PREFIX
from provider_coplan_util.stores.catalog_store import CatalogStore
from provider_coplan_util.routing.config import load_coplan_config, DEFAULT_MODELS, DEFAULT_PLANS
from provider_coplan_util.stores.key_store import UserKeyStore
from provider_coplan_util.stores.market_store import StrategyMarketStore
from provider_coplan_util.auth.stalone import CoplanStandaloneServer
from provider_coplan_util.routing.loader import load_strategy_groups
from provider_coplan_util.stores.store import StrategyStore
from provider_coplan_util.stores.user_store import UserStore
from provider_coplan_util.routing.plans import highest_active_plan_id, resolve_user_active_plan
from provider_coplan_util.stores.usage_store import UsageStore

from provider_coplan_util.handlers.account_routes import AuthRoutesMixin, MarketRoutesMixin
from provider_coplan_util.handlers.user_strat import (
    UserRoutesMixin,
    StrategyUserRoutesMixin,
)
from provider_coplan_util.handlers.strat_routes import AdminStrategyRoutesMixin
from provider_coplan_util.handlers.cfg_routes import (
    AdminSettingsRoutesMixin,
    AdminCatalogRoutesMixin,
)
from provider_coplan_util.handlers.misc_routes import (
    PublicRoutesMixin,
    PagesRoutesMixin,
    HooksMixin,
)


class CoplanUtilPlugin(
    ProviderPlugin,
    AuthRoutesMixin,
    UserRoutesMixin,
    StrategyUserRoutesMixin,
    PublicRoutesMixin,
    AdminSettingsRoutesMixin,
    AdminStrategyRoutesMixin,
    MarketRoutesMixin,
    AdminCatalogRoutesMixin,
    PagesRoutesMixin,
    HooksMixin,
):
    def __init__(self) -> None:
        self._store: StrategyStore | None = None
        self._catalog: CatalogStore | None = None
        self._market: StrategyMarketStore | None = None
        self._users: UserStore | None = None
        self._keys: UserKeyStore | None = None
        self._usage: UsageStore | None = None
        self._sessions = SessionStore()
        self._standalone: Optional[CoplanStandaloneServer] = None

    def _user_active_plan(self, username: str) -> Optional[Dict[str, Any]]:
        assert self._users is not None
        assert self._catalog is not None
        return resolve_user_active_plan(self._catalog, self._users, username)

    def _plugin_path(self) -> Path:
        return Path(self.ctx.plugin_dir)

    def _cfg(self):
        return load_coplan_config(self._plugin_path())

    async def on_load(self) -> None:
        data_dir = self._plugin_path() / "provider_coplan_util" / "support" / "_data" / "data"
        self._store = StrategyStore(data_dir)
        self._catalog = CatalogStore(data_dir)
        self._catalog.ensure_defaults(DEFAULT_PLANS, DEFAULT_MODELS)
        self._market = StrategyMarketStore(data_dir)
        self._users = UserStore(data_dir)
        self._keys = UserKeyStore(data_dir)
        self._usage = UsageStore(data_dir)
        cfg = self._cfg()
        self._users.ensure_admin_user(
            cfg.admin_username,
            cfg.admin_password,
            active_plan_id=highest_active_plan_id(self._catalog),
        )
        strategies_dir = self._plugin_path() / "provider_coplan_util" / "support" / "_data" / cfg.strategies_dir
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
                    startup_force_kill_port=cfg.standalone_startup_force_kill_port,
                )
            except OSError as exc:
                self.ctx.logger.warning("Coplan standalone 启动失败: %s", exc)
                self._standalone = None

    async def on_unload(self) -> None:
        if self._standalone is not None:
            await self._standalone.stop()
            self._standalone = None


def create_plugin() -> CoplanUtilPlugin:
    return CoplanUtilPlugin()
