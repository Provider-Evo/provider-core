from __future__ import annotations

"""WebUI 文件管理 API — 常量与路径工具。"""

import os
import stat
import string
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.paths import project_root as PROJECT_ROOT

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
