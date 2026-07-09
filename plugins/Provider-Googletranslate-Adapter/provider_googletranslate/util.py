from __future__ import annotations

# src/platforms/googletranslate/util.py
"""Google Translate 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.googletranslate.core`` 子模块
- ``GoogleTranslateAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any

from src.platforms.googletranslate.core.constants import (
    API_KEY,
    BASE_URL,
    CAPS,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    FETCH_MODELS_ENABLED,
    MODEL_FETCH_INTERVAL,
    MODELS,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
    TRANSLATE_PATH,
)


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入实现类。"""
    if name in ("GoogleTranslateAdapter", "Adapter"):
        from src.platforms.googletranslate.core.adaptercore import (  # noqa: PLC0415
            GoogleTranslateAdapter as _GoogleTranslateAdapter,
        )

        return _GoogleTranslateAdapter
    raise AttributeError(
        "module 'src.platforms.googletranslate.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "GoogleTranslateAdapter",
    "Adapter",
    "BASE_URL",
    "TRANSLATE_PATH",
    "API_KEY",
    "DEFAULT_TARGET_LANG",
    "DEFAULT_SOURCE_LANG",
    "RATE_LIMIT_COOLDOWN",
    "RECOVERY_INTERVAL",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
]
