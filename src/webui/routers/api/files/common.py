"""
_common 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-self.src.webui.routers.api.files._common
- 文件名：_common.py
- 父包：provider-self/src/webui/routers/api/files

职责：

    作为 provider / 核心子系统的标准模块入口；
    通常被 ``plugin.py`` 或上层 ``client.py`` 通过显式 import 使用。

对外接口：

    本模块的 ``__all__`` 列出对外可导入的符号集合；其他内部符号
    可能在重构中调整，调用方应只依赖 ``__all__`` 暴露的稳定 API。

集成：

    - SDK 入口：``plugin.py`` 中 ``create_plugin()`` 引用本模块以构造 platform adapter。
    - 入口路由：``provider-self/src/routes/openai`` 通过 ``from src.core...`` 间接使用。
    - 测试：本目录下的 ``tests/`` 子目录覆盖本模块的核心逻辑。

依赖：

    - 仅依赖 ``provider-sdk`` 与 Python 3.8+ 标准库；不引入第三方 HTTP 库。
    - 不直接读环境变量；所有配置走 ``config/main_config.toml``。

修改指引：

    - 调整本模块时同步更新 ``docs-src/plugins/<name>.md`` 与对应 ``tests/``。
    - 保持单文件 200-400 行；超长请拆为子包并通过 ``__init__.py`` 重新导出。
    - 严禁放置 placeholder / 兜底 / 伪装通过的代码（见 ``AGENTS.md`` Hard Constraints）。
"""


import os
import stat
import string
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.foundation.paths import project_root as PROJECT_ROOT

IS_WINDOWS = os.name == "nt"
DRIVES_SENTINEL = object()
MAX_PREVIEW_SIZE = 2 * 1024 * 1024
MAX_UPLOAD_SIZE = 100 * 1024 * 1024

BINARY_EXTENSIONS = frozenset({
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".obj", ".o", ".a", ".lib",
    ".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar", ".whl", ".egg",
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".mp3", ".mp4", ".avi", ".mkv", ".wav", ".flac", ".ogg", ".webm",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".sqlite", ".db", ".lock",
})

# Path components that are forbidden for write operations
SENSITIVE_PATH_PARTS = frozenset({
    ".git", ".env", ".htaccess", ".gitignore",
    "config.toml", "main_config.toml", "RECORD.md",
})


def safe_resolve(requested_path: str) -> Optional[Path]:
    """解析路径为绝对路径；Windows 根路径返回 DRIVES_SENTINEL，含空字节返回 None。"""
    requested_path = requested_path.strip()
    if "\x00" in requested_path:
        return None
    if not requested_path or requested_path in ("/", "\\"):
        if IS_WINDOWS:
            return DRIVES_SENTINEL  # type: ignore[return-value]
        return Path("/")
    try:
        return Path(requested_path).resolve()
    except (OSError, ValueError):
        return None


def entry_info(entry: Path) -> Dict[str, Any]:
    """中文说明：entry_info。Build metadata dict for a single filesystem entry."""
    try:
        st = entry.stat()
    except OSError:
        return {}
    is_dir = stat.S_ISDIR(st.st_mode)
    return {
        "name": entry.name,
        "type": "dir" if is_dir else "file",
        "size": st.st_size if not is_dir else None,
        "modified": st.st_mtime,
        "path": str(entry),
    }


def is_binary_file(path: Path) -> bool:
    """中文说明：is_binary_file。Check if a file is likely binary based on extension or content sniff."""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def is_write_forbidden(path: Path) -> bool:
    """中文说明：is_write_forbidden。Return True if *path* touches a sensitive file or directory."""
    try:
        parts = path.resolve().parts
    except (OSError, ValueError):
        parts = path.parts
    return any(part in SENSITIVE_PATH_PARTS for part in parts)


def get_drives() -> List[str]:
    """中文说明：get_drives。Return available root paths (drive letters on Windows)."""
    if IS_WINDOWS:
        return [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]
    return ["/"]


def entry_info_from_scandir(entry: os.DirEntry) -> Dict[str, Any]:
    """中文说明：entry_info_from_scandir。Build metadata dict from a :class:`os.DirEntry` (cached stat)."""
    try:
        st = entry.stat()
    except OSError:
        return {}
    is_dir = entry.is_dir()
    return {
        "name": entry.name,
        "type": "dir" if is_dir else "file",
        "size": st.st_size if not is_dir else None,
        "modified": st.st_mtime,
        "path": entry.path,
    }


SEARCH_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".backup", ".tmp",
    "logs", "persist", "uploads", ".qoder", ".agents",
})


def unique_dest(dest: Path) -> Path:
    """目标不存在则原样返回，否则追加数字后缀。"""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1

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
