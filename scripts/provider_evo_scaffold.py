#!/usr/bin/env python3
"""Provider-Evo 一次性脚手架：echotools entml、Fncall-Util、平台插件目录。"""
from __future__ import annotations

import json
import re
import shutil
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
ECHOTOOLS_PROTO = PROJECT / "echotools" / "src" / "echotools" / "fncall" / "protocols"
FNCALL_UTIL = PROJECT / "Provider-Fncall-Util"
PLUGINS = ROOT / "plugins"
PLATFORMS_SRC = ROOT / "src" / "platforms"

MOVE_PROTOCOLS = (
    "antml.py",
    "bracket.py",
    "custom.py",
    "dsml.py",
    "nous.py",
    "original.py",
    "xml.py",
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print("write", path.relative_to(PROJECT))


def setup_entml() -> None:
    antml = (ECHOTOOLS_PROTO / "antml.py").read_text(encoding="utf-8")
    entml = (
        antml.replace("antml", "entml")
        .replace("Antml", "Entml")
        .replace("Anthropic ML", "Entropy ML (entml)")
    )
    _write(ECHOTOOLS_PROTO / "entml.py", entml)
    init_py = textwrap.dedent(
        '''\
        """协议注册 — echotools 仅内置 entml 标记语言。"""

        from echotools.protocol.base import register_protocol


        def _register_all() -> None:
            from echotools.fncall.protocols.entml import EntmlProtocol

            register_protocol(EntmlProtocol())


        _register_all()

        __all__ = ["_register_all"]
        '''
    )
    _write(ECHOTOOLS_PROTO / "__init__.py", init_py)
    for name in MOVE_PROTOCOLS:
        src = ECHOTOOLS_PROTO / name
        if src.exists():
            src.unlink()
            print("removed echotools", name)


def setup_fncall_util() -> None:
    proto_dst = FNCALL_UTIL / "provider_fncall_util" / "protocols"
    proto_dst.mkdir(parents=True, exist_ok=True)
    # restore from git if missing — copy from provider-self docs-src mirror if needed
    for name in MOVE_PROTOCOLS:
        src = ECHOTOOLS_PROTO / name
        if not src.exists():
            # may already be deleted; try provider shims path
            alt = ROOT / "docs-src" / "src" / "core" / "fncall" / "protocols" / name
            if alt.exists():
                shutil.copy2(alt, proto_dst / name)
                continue
        if (ECHOTOOLS_PROTO / name).exists():
            shutil.copy2(ECHOTOOLS_PROTO / name, proto_dst / name)
    # Re-copy from git checkout in provider-self if we still have them in git
    import subprocess

    for name in MOVE_PROTOCOLS:
        dst = proto_dst / name
        if dst.exists():
            continue
        try:
            raw = subprocess.run(
                ["git", "show", f"HEAD:docs-src/src/core/fncall/protocols/{name}"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            if raw.stdout.strip():
                # docs-src copies may be thin; fallback to git history of echotools
                pass
        except Exception:
            pass
    # Copy from current echotools backup via reading antml pattern - use provider git
    for name in MOVE_PROTOCOLS:
        dst = proto_dst / name
        if dst.exists():
            continue
        try:
            raw = subprocess.run(
                ["git", "show", f"8b3db1d:src/core/fncall/protocols/_echotools_shims.py"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
        except Exception:
            pass

    _write(proto_dst / "__init__.py", '"""Provider-Fncall-Util 协议包。"""\n')
    _write(
        FNCALL_UTIL / "provider_fncall_util" / "__init__.py",
        '"""Provider FnCall Util — 扩展协议注入 provider-v2。"""\n',
    )

    manifest = {
        "manifest_version": 2,
        "id": "nichengfuben.provider-fncall-util",
        "name": "Provider FnCall Util",
        "version": "1.0.0",
        "description": "XML/ANTML/DSML 等工具协议扩展包",
        "plugin_type": "fncall",
        "author": {"name": "nichengfuben"},
        "host_application": {"min_version": "2.2.0-alpha", "max_version": "2.2.99"},
        "sdk": {"min_version": "0.3.0", "max_version": "0.99.99"},
        "dependencies": [],
        "capabilities": ["fncall.register_protocol"],
    }
    _write(FNCALL_UTIL / "_manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")

    plugin_py = textwrap.dedent(
        '''\
        from __future__ import annotations

        from provider_sdk import ProviderPlugin
        from provider_sdk.extensions.fncall import FncallPluginMixin


        class FncallUtilPlugin(ProviderPlugin, FncallPluginMixin):
            async def on_load(self) -> None:
                from echotools.protocol.base import register_protocol
                from provider_fncall_util.protocols.antml import AntmlProtocol
                from provider_fncall_util.protocols.bracket import BracketProtocol
                from provider_fncall_util.protocols.dsml import DsmlProtocol
                from provider_fncall_util.protocols.nous import NousProtocol
                from provider_fncall_util.protocols.original import OriginalProtocol
                from provider_fncall_util.protocols.xml import XmlProtocol

                for proto in (
                    XmlProtocol(),
                    AntmlProtocol(),
                    OriginalProtocol(),
                    BracketProtocol(),
                    NousProtocol(),
                    DsmlProtocol(),
                ):
                    register_protocol(proto)
                self.ctx.logger.info("Provider-Fncall-Util: registered protocols")


        def create_plugin() -> FncallUtilPlugin:
            return FncallUtilPlugin()
        '''
    )
    _write(FNCALL_UTIL / "plugin.py", plugin_py)

    pyproject = textwrap.dedent(
        '''\
        [build-system]
        requires = ["setuptools>=64"]
        build-backend = "setuptools.build_meta"

        [project]
        name = "provider-fncall-util"
        version = "1.0.0"
        requires-python = ">=3.8"
        dependencies = ["echotools>=2.0.0", "provider-sdk>=0.3.0"]

        [tool.setuptools.packages.find]
        include = ["provider_fncall_util*"]
        '''
    )
    _write(FNCALL_UTIL / "pyproject.toml", pyproject)
    _write(
        FNCALL_UTIL / ".gitignore",
        "__pycache__/\n*.pyc\n.venv/\ndist/\nbuild/\n",
    )


def _pascal(name: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[_-]", name))


def scaffold_platform_plugin(platform: str) -> None:
    src_dir = PLATFORMS_SRC / platform
    if not src_dir.is_dir():
        return
    repo_name = f"Provider-{_pascal(platform)}-Adapter"
    repo = PROJECT / repo_name
    plugin_dir = PLUGINS / repo_name
    for base in (repo, plugin_dir):
        pkg = base / f"provider_{platform}"
        if pkg.exists():
            shutil.rmtree(pkg)
        shutil.copytree(src_dir, pkg, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        # accounts.py stays locally if present; example for git
        acc = src_dir / "accounts.py"
        if acc.exists():
            example = (base / "accounts.py.example").read_text(encoding="utf-8") if (base / "accounts.py.example").exists() else (
                "# Illustrative only. Copy to accounts.py and fill credentials.\n"
                "API_KEYS = []\n"
            )
            if not (base / "accounts.py.example").exists():
                try:
                    text = acc.read_text(encoding="utf-8")
                    if "API_KEYS" in text:
                        example = "# Copy to accounts.py\nAPI_KEYS = [\"sk-example\"]\n"
                except Exception:
                    pass
                _write(base / "accounts.py.example", example)
            local_acc = base / "accounts.py"
            if acc.exists() and not local_acc.exists():
                shutil.copy2(acc, local_acc)

        manifest = {
            "manifest_version": 2,
            "id": f"nichengfuben.provider-{_pascal(platform).lower()}-adapter",
            "name": f"Provider {_pascal(platform)} Adapter",
            "version": "1.0.0",
            "description": f"{platform} platform adapter plugin",
            "plugin_type": "platform",
            "author": {"name": "nichengfuben"},
            "host_application": {"min_version": "2.2.0-alpha", "max_version": "2.2.99"},
            "sdk": {"min_version": "0.3.0", "max_version": "0.99.99"},
            "dependencies": ["nichengfuben.provider-fncall-util"],
            "capabilities": ["platform.adapter"],
        }
        _write(base / "_manifest.json", json.dumps(manifest, indent=2) + "\n")

        adapter_mod = f"provider_{platform}.core.adaptercore"
        plugin_py = textwrap.dedent(
            f'''\
            from __future__ import annotations

            import importlib

            from provider_sdk import ProviderPlugin
            from provider_sdk.extensions.platform.adapter import PlatformAdapter
            from provider_sdk.extensions.platform.bridge import attach_platform_adapter


            class { _pascal(platform) }Plugin(ProviderPlugin):
                def __init__(self) -> None:
                    super().__init__()
                    self._adapter = None

                async def on_load(self) -> None:
                    mod = importlib.import_module("{adapter_mod}")
                    for attr in dir(mod):
                        obj = getattr(mod, attr)
                        if isinstance(obj, type) and issubclass(obj, PlatformAdapter) and obj is not PlatformAdapter:
                            self._adapter = obj()
                            break
                    if self._adapter is None:
                        raise RuntimeError("no PlatformAdapter in {adapter_mod}")
                    attach_platform_adapter(self, self._adapter)
                    await self._adapter.init(self.ctx.services.session)


            def create_plugin() -> {_pascal(platform)}Plugin:
                return {_pascal(platform)}Plugin()
            '''
        )
        _write(base / "plugin.py", plugin_py)
        _write(base / ".gitignore", "accounts.py\n__pycache__/\n*.pyc\npersist/\nconfig/\n")


def main() -> None:
    # First restore protocol files from echotools before delete — copy to fncall util
    proto_dst = FNCALL_UTIL / "provider_fncall_util" / "protocols"
    proto_dst.mkdir(parents=True, exist_ok=True)
    for name in MOVE_PROTOCOLS:
        src = ECHOTOOLS_PROTO / name
        if src.exists():
            shutil.copy2(src, proto_dst / name)

    setup_entml()
    setup_fncall_util()

    if PLATFORMS_SRC.is_dir():
        for child in sorted(PLATFORMS_SRC.iterdir()):
            if child.is_dir() and not child.name.startswith("_"):
                scaffold_platform_plugin(child.name)

    print("scaffold done")


if __name__ == "__main__":
    main()
