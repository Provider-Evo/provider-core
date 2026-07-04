# -*- coding: utf-8 -*-
"""wenshushu 包 — 文叔叔文件传输工具。

公共 API re-export,对外暴露核心符号。
"""
from __future__ import annotations

from .cli import main
from .client import WenShuShuClient
from .bootstrap import create_container
from .use_cases import UploadUseCase, DownloadUseCase
from .container import Config

__version__ = "2.2.48"

__all__ = [
    # 入口
    "main",
    # 客户端
    "WenShuShuClient",
    # 引导
    "create_container",
    # 用例
    "UploadUseCase",
    "DownloadUseCase",
    # 配置
    "Config",
]
