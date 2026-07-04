from __future__ import annotations

"""Skill 脚本公共工具。"""

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def get_version() -> str:
    """读取项目版本号。"""
    try:
        from src.core.config import get_config

        return get_config().server.version
    except Exception:
        import tomllib

        with open(PROJECT_ROOT / 'config.toml', 'rb') as file_obj:
            return tomllib.load(file_obj)['server']['version']


def print_output(path: Path) -> None:
    """输出生成文件路径。"""
    print(str(path.resolve()))
