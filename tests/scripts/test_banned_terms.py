from __future__ import annotations

from pathlib import Path

from scripts.check_banned_terms import BANNED_TERMS, scan


def test_banned_terms_constant() -> None:
    """禁用词列表应包含常见外部项目标识。"""
    lowered = {t.lower() for t in BANNED_TERMS}
    assert "maibot" in lowered
    assert "maibot-sdk" in lowered
    assert "maisaka" in lowered


def test_scan_flags_banned_term_in_source(tmp_path: Path) -> None:
    """源码含禁用标识时应被扫描命中。"""
    module = tmp_path / "bad.py"
    module.write_text(
        'from __future__ import annotations\n\n# reference maibot-sdk\n',
        encoding="utf-8",
    )
    hits = scan([str(tmp_path)])
    assert hits
    assert any(term == "maibot-sdk" for _, term, _, _ in hits)


def test_agents_md_exempt_from_banned_scan() -> None:
    """AGENTS.md 允许出现 maibot，扫描应跳过。"""
    hits = scan(["AGENTS.md"])
    assert not hits
