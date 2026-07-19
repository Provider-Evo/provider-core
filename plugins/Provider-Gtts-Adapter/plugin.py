"""plugin 模块 — Provider 适配器层。

职责：
    作为 Provider-Evo 项目标准模块，提供 plugin 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


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


class GttsPlugin(ProviderPlugin):
    async def on_load(self) -> None:
        mod = importlib.import_module("provider_gtts.core.acore")
        adapter = _find_adapter_class(mod)()
        attach_platform_adapter(self, adapter)


def create_plugin() -> GttsPlugin:
    return GttsPlugin()
