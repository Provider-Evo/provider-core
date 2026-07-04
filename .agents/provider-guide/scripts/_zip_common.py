from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from typing import Iterable, List, Set

from common import PROJECT_ROOT, get_version, print_output

SKIP_DIRS: Set[str] = {'__pycache__', '.backup', '.tmp', 'uploads', 'node_modules', '.qoder'}
SKIP_FILES: Set[str] = set()

CONFIG_TOML = 'config.toml'


def iter_project_files(root: Path, output_name: str) -> Iterable[Path]:
    for current, dirs, files in os.walk(root):
        current_path = Path(current)
        dirs[:] = [name for name in dirs if name not in SKIP_DIRS]
        for file_name in files:
            file_path = current_path / file_name
            if file_name == output_name or file_path.suffix == '.zip':
                continue
            if any(part in SKIP_DIRS for part in file_path.relative_to(root).parts):
                continue
            yield file_path


def _patch_config(file_path: Path) -> bytes:
    """Read config.toml and set autoupdate = true and color = false without modifying the source file."""
    content = file_path.read_text(encoding='utf-8')
    content = re.sub(r'^(autoupdate\s*=\s*)false\b', r'\1true', content, flags=re.MULTILINE | re.IGNORECASE)
    content = re.sub(r'^(color\s*=\s*)true\b', r'\1false', content, flags=re.MULTILINE | re.IGNORECASE)
    return content.encode('utf-8')


def make_zip(
    output_name: str,
    extra_skip: List[str],
    patch_autoupdate: bool = False,
    include_git: bool = False,
) -> Path:
    target = PROJECT_ROOT / output_name
    if target.exists():
        target.unlink()
    original_skip = set(SKIP_DIRS)
    if not include_git:
        SKIP_DIRS.add('.git')
    SKIP_DIRS.update(extra_skip)
    try:
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as zip_obj:
            for file_path in iter_project_files(PROJECT_ROOT, output_name):
                arcname = file_path.relative_to(PROJECT_ROOT).as_posix()
                if file_path.name == CONFIG_TOML and patch_autoupdate:
                    zip_obj.writestr(arcname, _patch_config(file_path))
                else:
                    zip_obj.write(file_path, arcname)
    finally:
        SKIP_DIRS.clear()
        SKIP_DIRS.update(original_skip)
    print_output(target)
    return target
