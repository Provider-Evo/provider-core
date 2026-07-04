# -*- coding: utf-8 -*-
"""wenshushu 包入口 — 允许 ``python -m wenshushu`` 运行。"""
from .cli import main  # type: ignore[import-not-found]

raise SystemExit(main())
