from __future__ import annotations

"""配置管理器 - 支持模板合并、版本检查、watchdog 热重载。"""

import asyncio
import os
import re
import shutil
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import tomlkit
from tomlkit import TOMLDocument
from tomlkit.items import Table
from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None  # type: ignore

from src.core.config.sections import AppConfig
from src.logger import get_logger, set_color

logger = get_logger(__name__)

TEMPLATE_DIR = "template"
TEMPLATE_NAME = "template_config.toml"


def _find_config() -> Optional[Path]:
    """查找 config.toml，复用原 _find() 逻辑。"""
    env = os.environ.get("CONFIG_PATH")
    if env and Path(env).is_file():
        return Path(env)
    for b in [Path(__file__).parent.parent.parent.parent, Path.cwd()]:
        c = b / "config.toml"
        if c.is_file():
            return c.resolve()
    d = Path(__file__).parent.parent.parent.parent
    for _ in range(5):
        c = d / "config.toml"
        if c.is_file():
            return c.resolve()
        if d.parent == d:
            break
        d = d.parent
    return None


def _find_template() -> Optional[Path]:
    """查找模板文件。"""
    for base in [Path.cwd(), Path(__file__).parent.parent.parent.parent]:
        tpl = base / TEMPLATE_DIR / TEMPLATE_NAME
        if tpl.is_file():
            return tpl.resolve()
    return None


class ConfigManager:
    """配置管理器。

    - 启动时检查/创建配置文件
    - 版本号不同则合并模板新增字段
    - watchdog 实时监控热重载
    - __getattr__ 代理到 AppConfig
    """

    def __init__(self) -> None:
        self._config: Optional[AppConfig] = None
        self._config_path: Optional[Path] = None
        self._lock: Optional[asyncio.Lock] = None
        self._callbacks: Dict[str, List[Callable]] = {}
        self._observer: Optional[Observer] = None
        self._event_handler: Optional[FileSystemEventHandler] = None
        self._reload_debounce_task: Optional[asyncio.Task] = None
        self._debounce_delay: float = 0.5
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._is_reloading: bool = False
        self._last_reload_trigger: float = 0.0

    def _get_lock(self) -> asyncio.Lock:
        """Lazy-initialize asyncio.Lock to avoid event loop issues."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ------------------------------------------------------------------
    # 加载 / 重载
    # ------------------------------------------------------------------

    def load(self, config_path: Optional[str] = None) -> AppConfig:
        """加载配置文件（启动时调用）。"""
        if config_path:
            self._config_path = Path(config_path).resolve()
        else:
            self._config_path = _find_config()

        if self._config_path is None:
            # 不存在则从模板创建
            self._create_from_template()
            if self._config_path is None:
                raise RuntimeError("无法找到或创建 config.toml")

        raw = self._read_raw()
        self._merge_and_check(raw)
        self._config = AppConfig.from_dict(raw)

        # 应用日志颜色配置
        set_color(self._config.debug.color)

        logger.info("配置已加载: %s", self._config_path)
        return self._config

    async def reload(self) -> bool:
        """热重载配置文件。"""
        if self._config_path is None or not self._config_path.exists():
            return False

        async with self._get_lock():
            old_config = self._config
            try:
                raw = self._read_raw()
                new_config = AppConfig.from_dict(raw)

                if old_config is not None:
                    await self._notify_changes(old_config, new_config)

                self._config = new_config
                # 应用日志颜色配置（热重载时也可能变更）
                set_color(new_config.debug.color)
                logger.info("配置重载成功: %s", self._config_path)
                return True
            except Exception as e:
                logger.error("配置重载失败: %s", e, exc_info=True)
                return False

    # ------------------------------------------------------------------
    # 模板与版本
    # ------------------------------------------------------------------

    def _create_from_template(self) -> None:
        """从模板创建配置文件。"""
        tpl = _find_template()
        if tpl is None:
            logger.warning("未找到模板文件 %s/%s", TEMPLATE_DIR, TEMPLATE_NAME)
            return

        # 在项目根目录创建 config.toml
        target = Path.cwd() / "config.toml"
        if not target.exists():
            shutil.copy2(str(tpl), str(target))
            self._config_path = target
            logger.info("从模板创建新配置: %s", target)
            logger.info("请填写配置文件后重新运行")
            raise SystemExit(0)

        self._config_path = target

    def _merge_and_check(self, raw: Dict[str, Any]) -> None:
        """检查版本，合并模板中新增的字段。"""
        if self._config_path is None:
            return

        tpl_path = _find_template()
        if tpl_path is None:
            return

        try:
            with open(str(tpl_path), "r", encoding="utf-8") as f:
                tpl_raw = tomlkit.load(f)
        except Exception as exc:
            logger.debug("加载配置模板失败: %s", exc)
            return

        old_version = raw.get("server", {}).get("version") if isinstance(raw.get("server"), dict) else None
        new_version = tpl_raw.get("server", {}).get("version") if isinstance(tpl_raw.get("server"), dict) else None

        if old_version and new_version and old_version == new_version:
            logger.info("配置版本号相同 (v%s)，跳过合并", old_version)
            return

        if old_version and new_version:
            logger.info("检测到版本差异: v%s -> v%s，合并新增字段", old_version, new_version)
        elif new_version:
            logger.info("未检测到版本号，检查模板是否有新增字段")

        # 备份
        backup_dir = Path.cwd() / "template" / "old"
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"config.toml.bak.{ts}"
        shutil.copy2(str(self._config_path), str(backup_path))
        logger.info("已备份旧配置到: %s", backup_path)

        # 合并：把模板中有但用户配置中没有的键加进去
        self._merge_dicts(raw, dict(tpl_raw))

        # 写回
        self._write_merged(raw)
        logger.info("配置已合并，请检查后重新运行")
        raise SystemExit(0)

    @staticmethod
    def _merge_dicts(target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """递归把 source 中 target 缺少的键补进 target。"""
        for key, value in source.items():
            if key == "version":
                continue
            if key not in target:
                target[key] = value
            elif isinstance(value, dict) and isinstance(target[key], dict):
                ConfigManager._merge_dicts(target[key], value)

    def _write_merged(self, raw: Dict[str, Any]) -> None:
        """用 tomlkit 写回合并后的配置（保留注释）。"""
        if self._config_path is None:
            return
        try:
            with open(str(self._config_path), "r", encoding="utf-8") as f:
                doc = tomlkit.load(f)
        except Exception as exc:
            logger.debug("读取现有配置文件失败，使用空文档: %s", exc)
            doc = tomlkit.document()

        self._merge_toml_doc(doc, raw)
        with open(str(self._config_path), "w", encoding="utf-8") as f:
            f.write(tomlkit.dumps(doc))

    @staticmethod
    def _merge_toml_doc(doc: TOMLDocument, raw: Dict[str, Any]) -> None:
        """递归合并到 TOMLDocument。"""
        for key, value in raw.items():
            if isinstance(value, dict):
                if key not in doc or not isinstance(doc.get(key), (dict, Table)):
                    doc[key] = tomlkit.table()
                ConfigManager._merge_toml_doc(doc[key], value)
            else:
                try:
                    doc[key] = tomlkit.item(value)
                except (TypeError, ValueError):
                    doc[key] = value

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def _read_raw(self) -> Dict[str, Any]:
        if self._config_path is None:
            raise RuntimeError("配置路径未设置")

        if tomllib is None:
            logger.warning("tomllib/tomli 不可用，使用默认配置")
            return {}

        with open(str(self._config_path), "rb") as f:
            return tomllib.load(f)

    # ------------------------------------------------------------------
    # 回调
    # ------------------------------------------------------------------

    def on_config_change(self, config_path: str, callback: Callable) -> None:
        """为特定配置路径注册回调函数。"""
        if config_path not in self._callbacks:
            self._callbacks[config_path] = []
        self._callbacks[config_path].append(callback)

    async def _notify_changes(self, old_config: AppConfig, new_config: AppConfig) -> None:
        for config_path, callbacks in self._callbacks.items():
            try:
                old_value = self._get_value(old_config, config_path)
                new_value = self._get_value(new_config, config_path)
                if old_value != new_value:
                    logger.info("检测到配置变更: %s", config_path)
                    for callback in callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(old_value, new_value)
                            else:
                                callback(old_value, new_value)
                        except Exception as e:
                            logger.error("配置变更回调执行失败 [%s]: %s", config_path, e, exc_info=True)
            except Exception as e:
                logger.error("获取配置值失败 [%s]: %s", config_path, e)

    @staticmethod
    def _get_value(config: AppConfig, path: str) -> Any:
        parts = path.split(".")
        value: Any = config
        for part in parts:
            value = getattr(value, part)
        return value

    # ------------------------------------------------------------------
    # 属性代理
    # ------------------------------------------------------------------

    @property
    def config(self) -> AppConfig:
        if self._config is None:
            raise RuntimeError("配置尚未加载，请先调用 load()")
        return self._config

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")
        if self._config is None:
            raise RuntimeError("配置尚未加载，请先调用 load()")
        return getattr(self._config, name)

    # ------------------------------------------------------------------
    # Watchdog 监控
    # ------------------------------------------------------------------

    async def start_watching(self) -> None:
        if self._observer is not None:
            return

        self._loop = asyncio.get_running_loop()

        config_file_path = str(self._config_path) if self._config_path else ""

        class _Handler(FileSystemEventHandler):
            def __init__(handler_self, mgr: "ConfigManager") -> None:
                handler_self.mgr = mgr
                handler_self.path = config_file_path

            def on_modified(handler_inner, event):  # type: ignore[override]
                if isinstance(event, FileModifiedEvent) and os.path.abspath(event.src_path) == handler_inner.path:
                    logger.debug("检测到配置文件变更: %s", event.src_path)
                    if handler_inner.mgr._loop:
                        asyncio.run_coroutine_threadsafe(
                            handler_inner.mgr._debounced_reload(),
                            handler_inner.mgr._loop,
                        )

        self._event_handler = _Handler(self)
        self._observer = Observer()
        watch_dir = str(self._config_path.parent) if self._config_path else "."
        self._observer.schedule(self._event_handler, watch_dir, recursive=False)
        self._observer.start()
        logger.info("已启动配置文件实时监控: %s", self._config_path)

    async def stop_watching(self) -> None:
        if self._observer is None:
            return
        if self._reload_debounce_task:
            self._reload_debounce_task.cancel()
            try:
                await self._reload_debounce_task
            except asyncio.CancelledError:
                pass
        self._observer.stop()
        self._observer.join(timeout=2)
        self._observer = None
        self._event_handler = None
        logger.info("配置文件监控已停止")

    async def _debounced_reload(self) -> None:
        import time
        trigger_time = time.time()
        self._last_reload_trigger = trigger_time
        await asyncio.sleep(self._debounce_delay)
        if self._last_reload_trigger > trigger_time:
            logger.debug("放弃过时的重载请求")
            return
        if self._is_reloading:
            logger.debug("重载已在进行中，跳过")
            return
        self._is_reloading = True
        try:
            if self._config_path:
                mt = datetime.fromtimestamp(os.path.getmtime(str(self._config_path))).strftime("%Y-%m-%d %H:%M:%S")
                logger.info("配置文件已更新 (修改时间: %s)，正在重载...", mt)
            success = await self.reload()
            if not success:
                logger.error("配置文件重载失败！当前仍使用旧配置运行")
        finally:
            self._is_reloading = False

    def __repr__(self) -> str:
        watching = self._observer is not None and self._observer.is_alive()
        return f"<ConfigManager config_path={self._config_path} watching={watching}>"
