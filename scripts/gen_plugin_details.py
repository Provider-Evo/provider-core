#!/usr/bin/env python3
"""从本地 plugins/ 生成 plugin-repo/plugin_details.json。"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
OUT = ROOT.parent / "plugin-repo" / "plugin_details.json"


def main() -> None:
    items = []
    for plugin_dir in sorted(PLUGINS.glob("Provider-*")):
        manifest = None
        for name in ("_manifest.json", "_manifest.json.disabled"):
            path = plugin_dir / name
            if path.is_file():
                try:
                    manifest = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
                break
        if not manifest:
            continue
        pid = str(manifest.get("id") or "").strip()
        if not pid:
            continue
        readme = ""
        for rname in ("README.md", "readme.md"):
            rpath = plugin_dir / rname
            if rpath.is_file():
                readme = rpath.read_text(encoding="utf-8", errors="replace")[:4000]
                break
        items.append(
            {
                "id": pid,
                "manifest": manifest,
                "repositoryUrl": f"https://github.com/nichengfuben/{plugin_dir.name}",
                "changelog": manifest.get("changelog") or "",
                "readme": readme,
            }
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(items)} entries -> {OUT}")


if __name__ == "__main__":
    main()
