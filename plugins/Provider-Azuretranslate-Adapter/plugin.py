

import importlib

from provider_sdk import ProviderPlugin
from provider_sdk.extensions.platform.bridge import attach_platform_adapter


def _find_adapter_class(mod: object) -> type:
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if not isinstance(obj, type) or not attr.endswith("Adapter"):
            continue
        abstract = getattr(obj, "__abstractmethods__", frozenset())
        if abstract:
            continue
        if all(hasattr(obj, m) for m in ("name", "init", "candidates", "complete", "close")):
            return obj
    raise RuntimeError("no adapter class in {}".format(mod.__name__))


class AzuretranslatePlugin(ProviderPlugin):
    async def on_load(self) -> None:
        mod = importlib.import_module("provider_azuretranslate.core.acore")
        adapter = _find_adapter_class(mod)()
        attach_platform_adapter(self, adapter)


def create_plugin() -> AzuretranslatePlugin:
    return AzuretranslatePlugin()

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================
#
# ``plugin.py`` 由 SDK 通过 ``importlib.util.spec_from_file_location``
# 作为独立模块加载（非包内相对导入环境），因此本文件不得使用
# ``from .module import X`` 语法，否则加载时报
# "attempted relative import with no known parent package"。

__all__ = [
]
