from __future__ import annotations

"""Ollama 客户端兼容层。

该模块为历史兼容保留，新功能请直接使用 ``src.platforms.ollama.core.client``。
所有实现已迁移至 core/client.py，本模块仅做转发。
"""

from typing import Any

from src.platforms.ollama.core.client import OllamaClient  # noqa: F401


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入。"""
    if name == "OllamaClient":
        from src.platforms.ollama.core.client import (  # noqa: PLC0415
            OllamaClient as _OllamaClient,
        )

        return _OllamaClient
    raise AttributeError(
        "module 'src.platforms.ollama.client' has no attribute '{}'".format(name)
    )


__all__ = ["OllamaClient"]
