from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
bak = ROOT / "src" / "webui" / "routers" / "api" / "files.py.bak"
out = ROOT / "src" / "webui" / "routers" / "api" / "files" / "_common.py"
lines = bak.read_text(encoding="utf-8").splitlines()

replacements = {
    "_PROJECT_ROOT": "PROJECT_ROOT",
    "_IS_WINDOWS": "IS_WINDOWS",
    "_DRIVES_SENTINEL": "DRIVES_SENTINEL",
    "_MAX_PREVIEW_SIZE": "MAX_PREVIEW_SIZE",
    "_BINARY_EXTENSIONS": "BINARY_EXTENSIONS",
    "_SENSITIVE_PATH_PARTS": "SENSITIVE_PATH_PARTS",
    "_safe_resolve": "safe_resolve",
    "_entry_info": "entry_info",
    "_is_binary_file": "is_binary_file",
    "_is_write_forbidden": "is_write_forbidden",
    "_get_drives": "get_drives",
    "_entry_info_from_scandir": "entry_info_from_scandir",
}

header = '''from __future__ import annotations

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

'''

extra = '''

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
'''

chunk = "\n".join(lines[48:171])
for old, new in replacements.items():
    chunk = chunk.replace(old, new)
chunk = chunk.replace(
    'def safe_resolve(requested_path: str) -> Optional[Path]:\n    """Resolve',
    'def safe_resolve(requested_path: str) -> Optional[Path]:\n    """解析',
)
out.write_text(header + chunk + extra, encoding="utf-8")
print("wrote", out)
