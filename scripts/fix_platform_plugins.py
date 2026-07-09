#!/usr/bin/env python3
"""批量修复 plugins/Provider-*-Adapter/plugin.py 适配器发现逻辑。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"

TEMPLATE = '''from __future__ import annotations

import importlib

from provider_sdk import ProviderPlugin
from provider_sdk.extensions.platform.bridge import attach_platform_adapter


def _find_adapter_class(mod: object) -> type:
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if not isinstance(obj, type) or not attr.endswith("Adapter"):
            continue
        if all(hasattr(obj, m) for m in ("name", "init", "candidates", "complete", "close")):
            return obj
    raise RuntimeError(f"no adapter class in {{mod.__name__}}")


class {class_name}(ProviderPlugin):
    async def on_load(self) -> None:
        mod = importlib.import_module("{module_name}")
        adapter = _find_adapter_class(mod)()
        attach_platform_adapter(self, adapter)


def create_plugin() -> {class_name}:
    return {class_name}()
'''


def _class_name(platform: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[_-]", platform)) + "Plugin"


def main() -> None:
    for plugin_dir in sorted(PLUGINS.glob("Provider-*-Adapter")):
        if plugin_dir.name == "Provider-OpencodeZen-Adapter":
            continue
        name = plugin_dir.name.replace("Provider-", "").replace("-Adapter", "").lower()
        pkg = f"provider_{name}"
        content = TEMPLATE.format(
            class_name=_class_name(name),
            module_name=f"{pkg}.core.adaptercore",
        )
        path = plugin_dir / "plugin.py"
        path.write_text(content, encoding="utf-8")
        print("fixed", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
