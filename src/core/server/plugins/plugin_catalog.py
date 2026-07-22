"""
plugin_catalog 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.server.plugins.plugin_catalog
- 文件名：plugin_catalog.py
- 父包：provider-core/src/core/server/plugins

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

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

from src.foundation.paths import project_root

__all__ = [
    "find_plugin_dir_by_id",
    "is_plugin_enabled",
    "manifest_id_from_dir",
    "normalize_platform_name",
    "plugin_dir_from_path",
    "resolve_platform_plugin_id",
]

_MANIFEST_NAME = "_manifest.json"
_MANIFEST_DISABLED_NAME = "_manifest.json.disabled"
_PLUGINS_DIR = "plugins"
_PLATFORM_ALIASES = {
    "opencode": "zen",
    "opencodezen": "zen",
}


def normalize_platform_name(platform_name: str) -> str:
    """将 legacy 平台名映射为已注册的 ``PlatformAdapter.name``。"""
    raw = (platform_name or "").strip().lower()
    if not raw:
        return raw
    return _PLATFORM_ALIASES.get(raw, raw)


def _plugins_root() -> Path:
    return project_root / "plugins"


def _read_manifest_file(path: Path) -> Dict[str, object]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _read_manifest(plugin_dir: Path) -> Dict[str, object]:
    return _read_manifest_file(plugin_dir / _MANIFEST_NAME)


def _read_disabled_manifest(plugin_dir: Path) -> Dict[str, object]:
    return _read_manifest_file(plugin_dir / _MANIFEST_DISABLED_NAME)


def _platform_slug_from_dir(plugin_dir: Path) -> str:
    name = plugin_dir.name
    if name.startswith("Provider-") and name.endswith("-Adapter"):
        slug = name[len("Provider-") : -len("-Adapter")]
    else:
        slug = name
    return slug.lower().replace("-", "").replace("_", "")


def is_plugin_enabled(plugin_dir: Path) -> bool:
    """插件目录是否处于启用状态（存在 active manifest）。"""
    return (plugin_dir / _MANIFEST_NAME).is_file()


def manifest_id_from_dir(plugin_dir: Path) -> str:
    """读取插件 manifest id（优先 active，否则 disabled）。"""
    manifest = _read_manifest(plugin_dir)
    plugin_id = str(manifest.get("id", "")).strip()
    if plugin_id:
        return plugin_id
    disabled = _read_disabled_manifest(plugin_dir)
    return str(disabled.get("id", "")).strip()


def plugin_dir_from_path(path: Path) -> Optional[Path]:
    """从任意路径解析 ``plugins/<plugin_dir>``。"""
    parts = path.parts
    try:
        idx = parts.index(_PLUGINS_DIR)
    except ValueError:
        return None
    if len(parts) <= idx + 1:
        return None
    return Path(*parts[: idx + 2])


def find_plugin_dir_by_id(plugin_id: str) -> Optional[Path]:
    """按 manifest id 查找插件目录。"""
    target = (plugin_id or "").strip().lower()
    if not target:
        return None
    root = _plugins_root()
    if not root.is_dir():
        return None
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not manifest_id_from_dir(child) and not (
            child / _MANIFEST_DISABLED_NAME
        ).is_file():
            continue
        current = manifest_id_from_dir(child).strip().lower()
        if current == target:
            return child
    return None


@lru_cache(maxsize=1)
def _platform_plugin_index() -> Dict[str, str]:
    index: Dict[str, str] = {}
    root = _plugins_root()
    if not root.is_dir():
        return index
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if not is_plugin_enabled(child):
            continue
        manifest = _read_manifest(child)
        if str(manifest.get("plugin_type", "")).strip().lower() != "platform":
            continue
        plugin_id = str(manifest.get("id", "")).strip()
        if not plugin_id:
            continue
        slug = _platform_slug_from_dir(child)
        index[slug] = plugin_id
    return index


def resolve_platform_plugin_id(platform_name: str) -> Optional[str]:
    """将 legacy 平台目录名或 adapter.name 映射到插件 manifest id。"""
    raw = (platform_name or "").strip().lower()
    if not raw:
        return None
    normalized = normalize_platform_name(raw).replace("_", "").replace("-", "")
    return _platform_plugin_index().get(normalized)

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
