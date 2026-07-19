"""
service 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.server.reload.service
- 文件名：service.py
- 父包：provider-core/src/core/server/reload

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-core/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Sequence

from src.foundation.logger import get_logger

from src.core.server.reload.coord import ReloadCoordinator
from src.core.server.reload.file_watcher import FileChange, FileWatcher

__all__ = ["HotReloadService"]

logger = get_logger(__name__)

_SOURCE_EXTENSIONS = {".py", ".js", ".css", ".html", ".toml"}


class HotReloadService:
    """持有单个 ``FileWatcher``，订阅源码、主配置与 WebUI 配置。"""

    def __init__(
        self,
        root: Path,
        registry: Any,
        session: Any,
        app_host: Any,
        config_manager: Any,
        *,
        dry_run: bool = False,
    ) -> None:
        self._root = root.resolve()
        self._config_manager = config_manager
        self._coordinator = ReloadCoordinator(
            registry,
            session,
            app_host,
            dry_run=dry_run,
        )
        self._watcher: Optional[FileWatcher] = None
        self._source_sub_id: Optional[str] = None
        self._main_config_sub_id: Optional[str] = None
        self._webui_config_sub_id: Optional[str] = None

    @property
    def coordinator(self) -> ReloadCoordinator:
        """公开方法 coordinator。"""
        return self._coordinator

    @property
    def watcher(self) -> Optional[FileWatcher]:
        """返回当前 FileWatcher 实例（未启动时为 None），供健康检查读取。"""
        return self._watcher

    def _collect_watch_paths(self) -> tuple[list[Path], Optional[Path], Path]:
        """收集需要监视的路径，返回 (watch_paths, main_config_path, webui_config_path)。"""
        watch_paths: list[Path] = []
        src = self._root / "src"
        if src.is_dir():
            watch_paths.append(src)
        main_py = self._root / "main.py"
        if main_py.is_file():
            watch_paths.append(main_py)

        main_config_path = self._config_manager._config_path
        if main_config_path is not None:
            watch_paths.append(Path(main_config_path))

        plugins_dir = self._root / "plugins"
        if plugins_dir.is_dir():
            watch_paths.append(plugins_dir)

        from src.foundation.paths import config_dir

        webui_config_path = config_dir() / "webui_config.toml"
        if webui_config_path.is_file():
            watch_paths.append(webui_config_path)

        return watch_paths, main_config_path, webui_config_path

    def _subscribe_watch_paths(
        self,
        watch_paths: list[Path],
        main_config_path: Optional[Path],
        webui_config_path: Path,
    ) -> None:
        """基于已创建的 ``self._watcher`` 订阅源码/主配置/WebUI 配置变更。"""
        source_paths = [p for p in watch_paths if p.name not in {"main_config.toml", "webui_config.toml"}]
        self._source_sub_id = self._watcher.subscribe(
            self._on_source_changes,
            paths=source_paths,
        )

        if main_config_path is not None:
            self._main_config_sub_id = self._config_manager.attach_file_watcher(
                self._watcher,
                Path(main_config_path),
            )

        if webui_config_path.is_file():
            self._webui_config_sub_id = self._watcher.subscribe(
                self._on_webui_config_changes,
                paths=[webui_config_path.resolve()],
            )

    async def start(self) -> None:
        """启动统一文件监视器。"""
        watch_paths, main_config_path, webui_config_path = self._collect_watch_paths()

        self._watcher = FileWatcher(
            watch_paths,
            debounce_ms=600,
            callback_timeout_s=15.0,
            callback_failure_threshold=3,
            callback_cooldown_s=30.0,
        )

        self._subscribe_watch_paths(watch_paths, main_config_path, webui_config_path)

        await self._watcher.start()
        logger.info("热重载服务已启动: %s", self._root)

    async def stop(self) -> None:
        """停止监视器并输出统计。"""
        if self._watcher is None:
            return
        stats = self._watcher.stats
        for sub_id in (self._source_sub_id, self._main_config_sub_id, self._webui_config_sub_id):
            if sub_id is not None:
                self._watcher.unsubscribe(sub_id)
        self._source_sub_id = None
        self._main_config_sub_id = None
        self._webui_config_sub_id = None
        await self._watcher.stop()
        self._watcher = None
        logger.info(
            "热重载服务已停止: batches=%d changes=%d ok=%d failed=%d timeout=%d cooldown_skip=%d restart=%d",
            stats.batches_seen,
            stats.changes_seen,
            stats.callbacks_succeeded,
            stats.callbacks_failed,
            stats.callbacks_timed_out,
            stats.callbacks_skipped_cooldown,
            stats.restart_count,
        )

    async def _on_source_changes(self, changes: Sequence[FileChange]) -> None:
        paths = {
            str(change.path)
            for change in changes
            if self._accept_source_change(change)
        }
        if paths:
            await self._coordinator.handle_changes(paths)

    async def _on_webui_config_changes(self, changes: Sequence[FileChange]) -> None:
        names = sorted({change.path.name for change in changes})
        if names:
            logger.debug("WebUI 配置已变更（跳过热重载，API 按需读取）: %s", names)

    @staticmethod
    def _accept_source_change(change: FileChange) -> bool:
        path = change.path
        if path.name in {"main_config.toml", "webui_config.toml"}:
            return False
        # 插件运行时配置文件 — 按需读取，不触发热重载
        if "plugins" in path.parts and path.name in {
            "config.toml", "config.toml.example",
            "accounts.py", "accounts.py.example",
            "config_schema.json",
        }:
            return False
        if path.suffix == ".json":
            return (
                "plugins" in path.parts
                and path.name in {"_manifest.json", "_manifest.json.disabled"}
            )
        if path.suffix and path.suffix not in _SOURCE_EXTENSIONS:
            return False
        return True

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
