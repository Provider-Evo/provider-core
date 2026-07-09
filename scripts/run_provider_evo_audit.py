#!/usr/bin/env python3
"""Provider-Evo 全量审计（阶段 0）。"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
PLATFORMS = ROOT / "src" / "platforms"
OUT = ROOT / ".agents" / "data" / "provider_evo_audit.json"


def _plugin_dirs() -> list[Path]:
    if not PLUGINS.is_dir():
        return []
    return sorted(
        p for p in PLUGINS.iterdir()
        if p.is_dir() and not p.name.startswith(".")
        and ((p / "_manifest.json").is_file() or (p / "_manifest.json.disabled").is_file())
    )


def _grep_src_platforms(path: Path) -> list[str]:
    hits: list[str] = []
    import_pat = re.compile(r"^\s*(?:from|import)\s+src\.platforms", re.MULTILINE)
    for py in path.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        if import_pat.search(text):
            hits.append(str(py.relative_to(ROOT)))
    return hits


def main() -> int:
    plugin_dirs = _plugin_dirs()
    legacy_platform_dirs = sorted(
        p.name for p in PLATFORMS.iterdir() if p.is_dir() and p.name not in {"__pycache__"}
    ) if PLATFORMS.is_dir() else []

    plugin_deps: dict[str, list[str]] = {}
    for pdir in plugin_dirs:
        hits = _grep_src_platforms(pdir)
        if hits:
            plugin_deps[pdir.name] = hits

    admin_plugin_pkg = ROOT / "src" / "webui" / "routers" / "admin" / "plugin"
    routes_exist = {
        "plugins.py": (ROOT / "src/webui/routers/admin/plugins.py").is_file(),
        "plugin_catalog.py": (ROOT / "src/webui/routers/admin/plugin_catalog.py").is_file(),
        "plugin_progress.py": (ROOT / "src/webui/routers/admin/plugin_progress.py").is_file(),
        "plugin_package": admin_plugin_pkg.is_dir(),
        "plugins.css": (ROOT / "src/webui/static/plugins/plugins.css").is_file(),
        "plugins.js": (ROOT / "src/webui/static/plugins/plugins.js").is_file(),
    }

    coplan_brand = {}
    brand_file = PLUGINS / "Provider-Coplan-Util" / "provider_coplan_util" / "brand.py"
    if brand_file.is_file():
        text = brand_file.read_text(encoding="utf-8")
        for key in ("BRAND_NAME", "KEY_PREFIX"):
            m = re.search(rf'{key}\s*=\s*["\']([^"\']+)["\']', text)
            if m:
                coplan_brand[key] = m.group(1)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "plugin_count": len(plugin_dirs),
        "plugins_with_src_platforms_deps": len(plugin_deps),
        "legacy_platform_dirs": legacy_platform_dirs,
        "legacy_platform_count": len(legacy_platform_dirs),
        "plugin_panel_routes": routes_exist,
        "coplan_brand": coplan_brand,
        "requirements_matrix": {
            "R7_plugin_panel": routes_exist.get("plugins.js") and routes_exist.get("plugin_catalog.py"),
            "R12_fault_tolerance": (ROOT / "src/core/server/plugins/runtime.py").is_file(),
            "R16_plugin_repo": (ROOT.parent / "plugin-repo" / "plugins.json").is_file(),
            "plugin_self_contained": len(plugin_deps) == 0,
        },
        "plugin_dependency_samples": dict(list(plugin_deps.items())[:5]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nWrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
