from __future__ import annotations

"""Qwen 平台适配器入口——仅负责导出适配器类。"""

from typing import Any


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 QwenAdapter。"""
    if name in ("QwenAdapter", "Adapter"):
        from src.platforms.qwen.util import (  # noqa: PLC0415
            QwenAdapter as _QwenAdapter,
        )

        return _QwenAdapter
    raise AttributeError(
        "module 'src.platforms.qwen.adapter' has no attribute '{}'".format(name)
    )


__all__ = ["QwenAdapter", "Adapter"]
