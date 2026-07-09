"""Configuration manager — wraps echotools ConfigCenter, binds project AppConfig."""
from __future__ import annotations

import asyncio
import copy
import inspect
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence, cast

from echotools.config.center import ConfigCenter
from echotools.logger.manager import get_logger, set_color

from src.core.config.sections import AppConfig

logger = get_logger(__name__)

__all__ = ["ConfigManager"]

ConfigReloadCallback = Callable[..., object]


class ConfigManager:
    """项目配置管理器 — 支持热重载与变更 scope 回调。"""

    def __init__(self) -> None:
        self._center = ConfigCenter()
        self._config: Optional[AppConfig] = None
        self._registry: Optional[Any] = None
        self._session: Optional[Any] = None
        self._reload_lock = asyncio.Lock()
        self._reload_callbacks: List[ConfigReloadCallback] = []
        self._hot_reload_min_interval_s = 1.0
        self._hot_reload_timeout_s = 20.0
        self._last_hot_reload_monotonic = 0.0
        self._last_changed_scopes: tuple[str, ...] = ("main",)
        self.reload_revision = 0

    def bind_runtime(self, registry: Any, session: Any) -> None:
        """绑定运行时 registry/session，供配置热重载更新平台。"""
        self._registry = registry
        self._session = session

    @property
    def last_changed_scopes(self) -> tuple[str, ...]:
        """最近一次热重载检测到的变更 scope 列表。"""
        return self._last_changed_scopes

    def _apply_color(self) -> None:
        if self._config is None:
            return
        set_color(self._config.debug.color)
        try:
            from src.foundation.logger import set_color as _loguru_set_color

            _loguru_set_color(self._config.debug.color)
        except Exception:
            pass

    def load(self, config_path: Optional[str] = None) -> AppConfig:
        """公开方法 load。"""
        if config_path:
            self._center.load(config_path)
        else:
            from src.foundation.paths import config_dir

            default_config_path = config_dir() / "main_config.toml"
            if default_config_path.exists():
                self._center.load(str(default_config_path))
            else:
                self._center.init_from_template(
                    exit_after_create=True, exit_after_merge=False
                )
        self._config = self._center.bind_proxy(AppConfig)
        self._apply_color()
        logger.debug("Config loaded: %s", self._center.path)
        return self._config

    def register_reload_callback(self, callback: ConfigReloadCallback) -> None:
        """公开方法 register_reload_callback。"""
        self._reload_callbacks.append(callback)

    def unregister_reload_callback(self, callback: ConfigReloadCallback) -> None:
        """公开方法 unregister_reload_callback。"""
        try:
            self._reload_callbacks.remove(callback)
        except ValueError:
            return

    def attach_file_watcher(self, watcher: object, config_path: Path) -> str:
        """公开方法 attach_file_watcher。"""
        from src.core.server.reload.file_watcher import FileWatcher

        if not isinstance(watcher, FileWatcher):
            raise TypeError("watcher 必须是 FileWatcher 实例")
        return watcher.subscribe(
            self._handle_config_file_changes,
            paths=[config_path.resolve()],
        )

    async def reload(self) -> bool:
        """公开方法 reload。"""
        async with self._reload_lock:
            old_raw = copy.deepcopy(self._center._raw)
            ok = await self._center.reload()
            if not ok:
                return False
            new_raw = self._center._raw
            self._config = self._center.bind_proxy(AppConfig)
            self._apply_color()
            self.reload_revision += 1
            self._last_changed_scopes = self._resolve_scopes(old_raw, new_raw)
            await self._apply_reload_policy(old_raw, new_raw, self._last_changed_scopes)
            await self._invoke_reload_callbacks(self._last_changed_scopes)
            return True

    @staticmethod
    def _resolve_scopes(old_raw: dict, new_raw: dict) -> tuple[str, ...]:
        from src.core.config.reload_policy import resolve_changed_scopes

        return resolve_changed_scopes(old_raw, new_raw)

    async def _handle_config_file_changes(self, changes: Sequence[object]) -> None:
        if not changes:
            return
        now_monotonic = asyncio.get_running_loop().time()
        if now_monotonic - self._last_hot_reload_monotonic < self._hot_reload_min_interval_s:
            logger.debug("配置热重载跳过：变更过于频繁")
            return
        self._last_hot_reload_monotonic = now_monotonic
        logger.info("检测到配置文件变更: %s", [getattr(c, "path", c) for c in changes])
        try:
            await asyncio.wait_for(self.reload(), timeout=self._hot_reload_timeout_s)
        except asyncio.TimeoutError:
            logger.error("配置热重载超时 (%ss)", self._hot_reload_timeout_s)

    async def _apply_reload_policy(
        self,
        old_raw: dict,
        new_raw: dict,
        scopes: Sequence[str],
    ) -> None:
        from src.core.config.reload_policy import (
            apply_hot_config_side_effects,
            requires_process_restart,
        )

        apply_hot_config_side_effects(old_raw, new_raw)
        if self._registry is not None and self._session is not None:
            try:
                await self._registry.apply_config_reload(
                    old_raw, new_raw, self._session, scopes,
                )
            except Exception as exc:
                logger.warning("平台配置热重载失败: %s", exc)
        if requires_process_restart(old_raw, new_raw):
            from src.core.server.reload.restart import request_process_restart

            await request_process_restart(
                registry=self._registry,
                session=self._session,
                reason="配置项变更需要进程重启",
            )

    async def _invoke_reload_callbacks(self, scopes: Sequence[str]) -> None:
        for callback in list(self._reload_callbacks):
            try:
                await self._invoke_reload_callback(callback, scopes)
            except Exception as exc:
                logger.warning("配置热重载回调失败: %s", exc)

    @staticmethod
    def _callback_accepts_scopes(callback: ConfigReloadCallback) -> bool:
        try:
            parameters = inspect.signature(callback).parameters.values()
        except (TypeError, ValueError):
            return False
        if not parameters:
            return False
        first = next(iter(parameters))
        return first.name in {"changed_scopes", "scopes"}

    async def _invoke_reload_callback(
        self,
        callback: ConfigReloadCallback,
        scopes: Sequence[str],
    ) -> None:
        if self._callback_accepts_scopes(callback):
            scoped = cast(Callable[[Sequence[str]], object], callback)
            result = scoped(scopes)
        else:
            plain = cast(Callable[[], object], callback)
            result = plain()
        if asyncio.iscoroutine(result):
            await result

    async def start_watching(self) -> None:
        """公开方法 start_watching。"""
        logger.warning("ConfigManager.start_watching 已弃用，请使用 HotReloadService")

    async def stop_watching(self) -> None:
        """公开方法 stop_watching。"""
        await self._center.stop_watch()

    def on_config_change(self, config_path: str, callback: ConfigReloadCallback) -> None:
        """公开方法 on_config_change。"""
        self._center.on_change(config_path, callback)

    @property
    def config(self) -> AppConfig:
        """公开方法 config。"""
        if self._config is None:
            raise RuntimeError("Config not loaded yet, call load() first")
        return self._config

    @property
    def _config_path(self):
        return self._center.path

    def __repr__(self) -> str:
        return repr(self._center)
