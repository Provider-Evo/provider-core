from __future__ import annotations

"""Ollama 平台适配器入口。

仅从 util 模块导入，符合平台适配器依赖方向规范：
adapter.py -> util.py -> core/*
"""

from typing import Any


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 OllamaAdapter。"""
    if name in ("OllamaAdapter", "Adapter"):
        from src.platforms.ollama.util import (  # noqa: PLC0415
            OllamaAdapter as _OllamaAdapter,
        )

        return _OllamaAdapter
    raise AttributeError(
        "module 'src.platforms.ollama.adapter' has no attribute '{}'".format(name)
    )


__all__ = ["OllamaAdapter", "Adapter"]
