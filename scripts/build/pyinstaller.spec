# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 草稿 — 见 docs-src/scripts/pyinstaller.md"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent.parent

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "template"), "template"),
        (str(ROOT / "src" / "webui" / "static"), "src/webui/static"),
    ],
    hiddenimports=[
        "aiohttp",
        "loguru",
        "pydantic",
        "echotools",
        "provider_sdk",
        "src.bootstrap.app_factory",
        "src.core.observability",
        "src.core.server.runner",
        "src.core.server.worker",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="provider-v2",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="provider-v2",
)
