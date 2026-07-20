


from typing import Any


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入 OllamaAdapter。"""
    if name in ("OllamaAdapter", "Adapter"):
        from provider_ollama.util import (  # noqa: PLC0415
            OllamaAdapter as _OllamaAdapter,
        )

        return _OllamaAdapter
    raise AttributeError(
        "module 'provider_ollama.adapter' has no attribute '{}'".format(name)
    )


__all__ = ["OllamaAdapter", "Adapter"]

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================
