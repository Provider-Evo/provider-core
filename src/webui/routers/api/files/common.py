
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

BINARY_EXTENSIONS = frozenset(
    {
        ".pyc",
        ".pyo",
        ".so",
        ".dll",
        ".exe",
        ".bin",
        ".obj",
        ".o",
        ".a",
        ".lib",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".xz",
        ".7z",
        ".rar",
        ".whl",
        ".egg",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".bmp",
        ".ico",
        ".webp",
        ".svg",
        ".mp3",
        ".mp4",
        ".avi",
        ".mkv",
        ".wav",
        ".flac",
        ".ogg",
        ".webm",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".sqlite",
        ".db",
        ".lock",
    }
)

# Path components that are forbidden for write operations (exact segment match).
# File names only — never block directories named e.g. config/ or Log/.
SENSITIVE_PATH_PARTS = frozenset(
    {
        ".git",
        ".env",
        ".htaccess",
        ".gitignore",
        "config.toml",
        "main_config.toml",
        "RECORD.md",
    }
)


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
    """Build metadata dict for a single filesystem entry."""
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
    """Check if a file is likely binary based on extension or content sniff."""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def is_write_forbidden(path: Path) -> bool:
    """Return True if *path* touches a sensitive file or directory."""
    try:
        parts = path.resolve().parts
    except (OSError, ValueError):
        parts = path.parts
    return any(part in SENSITIVE_PATH_PARTS for part in parts)


def get_drives() -> List[str]:
    """Return available root paths (drive letters on Windows)."""
    if IS_WINDOWS:
        return [
            f"{letter}:\\"
            for letter in string.ascii_uppercase
            if os.path.exists(f"{letter}:\\")
        ]
    return ["/"]


def entry_info_from_scandir(entry: os.DirEntry) -> Dict[str, Any]:
    """Build metadata dict from a :class:`os.DirEntry` (cached stat)."""
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


# Directory names skipped during recursive file search only (exact segment match,
# case-insensitive). Do NOT add generic names like "config" or "log" — project
# source trees often contain those as legitimate folders.
SEARCH_SKIP_DIRS = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".backup",
        ".tmp",
        ".agents",
        ".cursor",
        ".idea",
        ".vscode",
        "persist",
        "uploads",
        ".qoder",
    }
)
SEARCH_SKIP_DIRS_LOWER = frozenset(d.lower() for d in SEARCH_SKIP_DIRS)


def should_skip_search_dir(name: str) -> bool:
    """True when *name* is a known junk directory (case-insensitive)."""
    return name.lower() in SEARCH_SKIP_DIRS_LOWER


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
