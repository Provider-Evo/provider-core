from __future__ import annotations

"""脚本生成与打包复用工具。"""

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
    """遍历目录下的文件��

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
    """生成 logs/scriptgen 下的文本产物路径��"""
    ensure_directory(directory)
    return directory / "{}_{}.txt".format(prefix, uuid7())


def split_text(
    content: str,
    *,
    max_chars: int,
    separator: str,
) -> List[str]:
    """按可���分隔符优先的策略切分文本。

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