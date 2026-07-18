"""util 模块 — Provider 适配器层。

职责：
    提供运行期无关的小工具（路径解析、字符串转换、header 构造等）。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


# src/platforms/azuretranslate/util.py
"""Azure Translator 对外工具门面。

该模块只负责导出稳定接口：
- 共享常量/函数来自 ``src.platforms.azuretranslate.core`` 子模块
- ``AzureTranslateAdapter`` 与 ``Adapter`` 通过 ``__getattr__`` 延迟加载
"""

from typing import Any

from provider_azuretranslate.core.constants import (
    API_VERSION,
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
    if name in ("AzureTranslateAdapter", "Adapter"):
        from provider_azuretranslate.core.adaptercore import (  # noqa: PLC0415
            AzureTranslateAdapter as _AzureTranslateAdapter,
        )

        return _AzureTranslateAdapter
    raise AttributeError(
        "module 'src.platforms.azuretranslate.util' has no attribute '{}'".format(name)
    )


__all__ = [
    "AzureTranslateAdapter",
    "Adapter",
    "BASE_URL",
    "TRANSLATE_PATH",
    "API_VERSION",
    "DEFAULT_TARGET_LANG",
    "DEFAULT_SOURCE_LANG",
    "RATE_LIMIT_COOLDOWN",
    "RECOVERY_INTERVAL",
    "MODELS",
    "CAPS",
    "FETCH_MODELS_ENABLED",
    "MODEL_FETCH_INTERVAL",
]
