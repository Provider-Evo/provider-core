from __future__ import annotations

import json
from pathlib import Path

from scripts.webui import i18n_validate_webui as mod


def test_i18n_validate_passes_on_repo_locales() -> None:
    """仓库内四语言 locale 应键对齐且无占位符差异。"""
    assert mod.main([]) == 0


def test_i18n_validate_reports_missing_keys(tmp_path: Path, monkeypatch) -> None:
    """目标语言缺少键时应返回非零。"""
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    (locale_dir / "zh.json").write_text(
        json.dumps({"chat": {"title": "标题"}}),
        encoding="utf-8",
    )
    (locale_dir / "en.json").write_text(json.dumps({"chat": {}}), encoding="utf-8")
    for lng in ("ja", "ko"):
        (locale_dir / f"{lng}.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mod, "LOCALE_DIR", locale_dir)
    assert mod.main([]) != 0
