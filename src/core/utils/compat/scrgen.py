"""
scriptgen 模块。

本文件为 Provider-Evo 项目标准模块，使用以下约定：

- 模块路径：provider-core.src.core.utils.compat.scrgen
- 文件名：scriptgen.py
- 父包：provider-core/src/core/utils/compat

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


import mimetypes
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Sequence, Set

from src.core.fncall.shared import _uuid7 as uuid7
from src.core.utils.io_utils import atomic_write_text, ensure_directory

__all__ = [
    "SCRIPTGEN_ROOT",
    "SCRIPTGEN_SPLIT_ROOT",
    "iter_files",
    "is_text_file",
    "make_log_text_path",
    "split_text",
]

SCRIPTGEN_ROOT = Path("logs/scriptgen")
SCRIPTGEN_SPLIT_ROOT = SCRIPTGEN_ROOT / "spilt"

_TEXT_EXTENSIONS: Set[str] = {
    ".txt",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".css",
    ".md",
    ".ini",
    ".cfg",
    ".conf",
    ".csv",
    ".log",
    ".sql",
    ".sh",
    ".bat",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".go",
    ".rs",
    ".rst",
}


def iter_files(
    root: Path,
    *,
    include_hidden: bool,
    exclude_names: Optional[Sequence[str]] = None,
    exclude_dirs: Optional[Sequence[str]] = None,
) -> Iterator[Path]:
    """遍历目录下的文件。

    Args:
        root: 根目录。
        include_hidden: 是否包含隐藏路径。
        exclude_names: 要排除的文件名序列。
        exclude_dirs: 要排除的目录名序列。

    Yields:
        文件路径。
    """
    excluded_names = set(exclude_names or [])
    excluded_dirs = set(exclude_dirs or [])
    for current in root.rglob("*"):
        if current.is_dir():
            continue
        if not include_hidden and any(part.startswith(".") for part in current.relative_to(root).parts):
            continue
        if current.name in excluded_names:
            continue
        if any(part in excluded_dirs for part in current.relative_to(root).parts):
            continue
        yield current


def is_text_file(path: Path) -> bool:
    """判断是否为文本文件。"""
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    mime_type, _ = mimetypes.guess_type(str(path))
    return bool(mime_type and mime_type.startswith("text/"))


def make_log_text_path(prefix: str, directory: Path) -> Path:
    """生成 logs/scriptgen 下的文本产物路径。"""
    ensure_directory(directory)
    return directory / "{}_{}.txt".format(prefix, uuid7())


def split_text(
    content: str,
    *,
    max_chars: int,
    separator: str,
) -> List[str]:
    """按可选分隔符优先的策略切分文本。

    Args:
        content: 原始文本。
        max_chars: 每段最大字符数。
        separator: 优先分隔符，可为空字符串。

    Returns:
        切分后的文本列表。
    """
    if not content:
        return []
    if max_chars <= 0:
        raise ValueError("max_chars 必须大于 0")
    parts: List[str] = []
    start = 0
    while start < len(content):
        end = min(start + max_chars, len(content))
        chunk = content[start:end]
        if separator and end < len(content):
            split_at = chunk.rfind(separator)
            if split_at > 0:
                end = start + split_at + len(separator)
                chunk = content[start:end]
        parts.append(chunk)
        start = end
    return parts


def write_log_text(path: Path, content: str) -> Path:
    """写入脚本文本产物。"""
    atomic_write_text(path, content)
    return path

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
