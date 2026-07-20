

# src/platforms/deepl/util.py
"""DeepL 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.deepl.core`` 子模块
- ``DeepLAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any

from provider_deepl.core.consts import (
    CAPS,
    DEFAULT_SOURCE_LANG,
    DEFAULT_TARGET_LANG,
    FETCH_MODELS_ENABLED,
    FREE_BASE_URL,
    MODEL_FETCH_INTERVAL,
    MODELS,
    PAID_BASE_URL,
    RATE_LIMIT_COOLDOWN,
    RECOVERY_INTERVAL,
    TRANSLATE_PATH,
)


def __getattr__(name: str) -> Any:
    """模块级懒属性，按需导入实现类。"""
    if name in ("DeepLAdapter", "Adapter"):
        from provider_deepl.core.acore import (  # noqa: PLC0415
            DeepLAdapter as _DeepLAdapter,
        )

        return _DeepLAdapter
    raise AttributeError(
        "module 'src.platforms.deepl.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "DeepLAdapter",
    "Adapter",
    "FREE_BASE_URL",
    "PAID_BASE_URL",
    "TRANSLATE_PATH",
    "DEFAULT_TARGET_LANG",
    "DEFAULT_SOURCE_LANG",
    "RATE_LIMIT_COOLDOWN",
    "RECOVERY_INTERVAL",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
]
