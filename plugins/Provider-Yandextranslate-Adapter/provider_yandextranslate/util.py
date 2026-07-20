

# src/platforms/yandextranslate/util.py
"""Yandex Translate 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.yandextranslate.core`` 子模块
- ``YandexTranslateAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any

from provider_yandextranslate.core.consts import (
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
    if name in ("YandexTranslateAdapter", "Adapter"):
        from provider_yandextranslate.core.acore import (  # noqa: PLC0415
            YandexTranslateAdapter as _YandexTranslateAdapter,
        )

        return _YandexTranslateAdapter
    raise AttributeError(
        "module 'src.platforms.yandextranslate.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "YandexTranslateAdapter",
    "Adapter",
    "BASE_URL",
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
