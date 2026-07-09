#!/usr/bin/env python3
"""将单体 files.py 重构为 files/ 包（一次性维护脚本）。"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "src" / "webui" / "routers" / "api"
LEGACY = API_DIR / "files.py"
PKG = API_DIR / "files"

COMMON = '''from __future__ import annotations

"""WebUI 文件管理 API — 常量与路径工具。"""

import base64
import mimetypes
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

SENSITIVE_PATH_PARTS = frozenset({
    ".git", ".env", ".htaccess", ".gitignore",
    "config.toml", "main_config.toml", "RECORD.md",
})

SEARCH_SKIP_DIRS = frozenset({
    ".git", "node_modules", "__pycache__", ".backup", ".tmp",
    "logs", "persist", "uploads", ".qoder", ".agents",
})


def safe_resolve(requested_path: str) -> Optional[Path]:
    """解析请求路径为绝对路径；Windows 根路径返回 DRIVES_SENTINEL。"""
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
    """构建单个文件系统条目的元数据字典。"""
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
    """根据扩展名或内容嗅探判断是否为二进制文件。"""
    if path.suffix.lower() in BINARY_EXTENSIONS:
        return True
    try:
        with open(path, "rb") as handle:
            chunk = handle.read(8192)
        return b"\x00" in chunk
    except OSError:
        return True


def is_write_forbidden(path: Path) -> bool:
    """若路径触及敏感文件或目录则返回 True。"""
    try:
        parts = path.resolve().parts
    except (OSError, ValueError):
        parts = path.parts
    return any(part in SENSITIVE_PATH_PARTS for part in parts)


def get_drives() -> List[str]:
    """返回可用根路径列表（Windows 盘符或 Unix 根目录）。"""
    if IS_WINDOWS:
        drives: List[str] = []
        for letter in string.ascii_uppercase:
            if os.path.exists(f"{letter}:\\"):
                drives.append(f"{letter}:\\")
        return drives
    return ["/"]


def entry_info_from_scandir(entry: os.DirEntry) -> Dict[str, Any]:
    """从 os.DirEntry 构建元数据字典。"""
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
'''

INIT = '''from __future__ import annotations

"""WebUI 文件管理 API 路由包。"""

from .handlers_meta import files_drives, files_project_root
from .handlers_mutate import files_delete, files_mkdir, files_rename, files_write
from .handlers_read import files_download, files_list, files_read
from .handlers_search import files_search
from .handlers_transfer import files_copy, files_move
from .handlers_upload import files_upload

__all__ = [
    "files_copy",
    "files_delete",
    "files_download",
    "files_drives",
    "files_list",
    "files_mkdir",
    "files_move",
    "files_project_root",
    "files_read",
    "files_rename",
    "files_search",
    "files_upload",
    "files_write",
]
'''


def _read_handlers() -> str:
    return LEGACY.read_text(encoding="utf-8")


def _replace_names(text: str) -> str:
    mapping = {
        "_PROJECT_ROOT": "PROJECT_ROOT",
        "_IS_WINDOWS": "IS_WINDOWS",
        "_DRIVES_SENTINEL": "DRIVES_SENTINEL",
        "_MAX_PREVIEW_SIZE": "MAX_PREVIEW_SIZE",
        "_MAX_UPLOAD_SIZE": "MAX_UPLOAD_SIZE",
        "_BINARY_EXTENSIONS": "BINARY_EXTENSIONS",
        "_SENSITIVE_PATH_PARTS": "SENSITIVE_PATH_PARTS",
        "_safe_resolve": "safe_resolve",
        "_entry_info": "entry_info",
        "_is_binary_file": "is_binary_file",
        "_is_write_forbidden": "is_write_forbidden",
        "_get_drives": "get_drives",
        "_entry_info_from_scandir": "entry_info_from_scandir",
        "_unique_dest": "unique_dest",
        "_skip_dirs": "SEARCH_SKIP_DIRS",
    }
    for old, new in mapping.items():
        text = text.replace(old, new)
    return text


def _handler_header(extra: str = "") -> str:
    return f'''from __future__ import annotations

import aiohttp.web
{extra}
from ._common import (
    DRIVES_SENTINEL,
    MAX_PREVIEW_SIZE,
    MAX_UPLOAD_SIZE,
    PROJECT_ROOT,
    SEARCH_SKIP_DIRS,
    entry_info_from_scandir,
    get_drives,
    is_binary_file,
    is_write_forbidden,
    safe_resolve,
    unique_dest,
)

'''


def _extract_block(source: str, start_marker: str, end_marker: str | None) -> str:
    start = source.index(start_marker)
    if end_marker:
        end = source.index(end_marker, start + 1)
        return source[start:end]
    return source[start:]


def _write_handler_files(blocks: dict[str, str], extras: dict[str, str]) -> None:
    for name, body in blocks.items():
        header_doc, rest = body.split("\n\n", 1)
        content = _handler_header(extras[name]) + header_doc + "\n\n" + _replace_names(rest)
        (PKG / name).write_text(content, encoding="utf-8")


def _extract_handler_blocks(raw: str) -> dict[str, str]:
    return {
        "handlers_read.py": '"""WebUI 文件管理 API — 列表、读取与下载。"""\n\n' + _extract_block(
            raw,
            "# ---------------------------------------------------------------------------\n# GET /v1/webui/files/list",
            "# ---------------------------------------------------------------------------\n# POST /v1/webui/files/mkdir",
        ),
        "handlers_mutate.py": '"""WebUI 文件管理 API — 目录与文件变更。"""\n\n' + _extract_block(
            raw,
            "# ---------------------------------------------------------------------------\n# POST /v1/webui/files/mkdir",
            "# ---------------------------------------------------------------------------\n# POST /v1/webui/files/upload",
        ),
        "handlers_upload.py": '"""WebUI 文件管理 API — 文件上传。"""\n\n' + _extract_block(
            raw,
            "# ---------------------------------------------------------------------------\n# POST /v1/webui/files/upload",
            "# ---------------------------------------------------------------------------\n# Helpers for copy / move",
        ),
        "handlers_transfer.py": '"""WebUI 文件管理 API — 复制与移动。"""\n\n' + _extract_block(
            raw,
            "# ---------------------------------------------------------------------------\n# POST /v1/webui/files/copy",
            "# ---------------------------------------------------------------------------\n# GET /v1/webui/files/search",
        ),
        "handlers_search.py": '"""WebUI 文件管理 API — 文件搜索。"""\n\n' + _extract_block(
            raw,
            "# ---------------------------------------------------------------------------\n# GET /v1/webui/files/search",
            "# ---------------------------------------------------------------------------\n# GET /v1/webui/files/drives",
        ),
        "handlers_meta.py": '"""WebUI 文件管理 API — 驱动器与项目根。"""\n\n' + _extract_block(
            raw,
            "# ---------------------------------------------------------------------------\n# GET /v1/webui/files/drives",
            None,
        ),
    }


def _handler_extras() -> dict[str, str]:
    return {
        "handlers_read.py": "import base64\nimport mimetypes\nimport os\nfrom pathlib import Path\nfrom typing import Any, Dict, List\n",
        "handlers_mutate.py": "import shutil\nfrom pathlib import Path\nfrom typing import Any, Dict, List\n",
        "handlers_upload.py": "from pathlib import Path\nfrom typing import Any, Dict, List\n",
        "handlers_transfer.py": "import shutil\nfrom pathlib import Path\nfrom typing import Any, Dict\n",
        "handlers_search.py": "import os\nimport stat\nfrom pathlib import Path\nfrom typing import Any, Dict, List\n",
        "handlers_meta.py": "",
    }


def main() -> None:
    """公开方法 main。"""
    if not LEGACY.is_file():
        raise SystemExit(f"missing {LEGACY}")
    raw = _read_handlers()
    PKG.mkdir(parents=True, exist_ok=True)
    (PKG / "__init__.py").write_text(INIT, encoding="utf-8")
    (PKG / "_common.py").write_text(COMMON, encoding="utf-8")
    _write_handler_files(_extract_handler_blocks(raw), _handler_extras())
    backup = LEGACY.with_suffix(".py.bak")
    shutil.copy2(LEGACY, backup)
    LEGACY.unlink()
    print(f"Package written to {PKG}; backup at {backup}")


if __name__ == "__main__":
    main()
