from __future__ import annotations

from pathlib import Path

from scripts.audit_webui_i18n import audit


def test_webui_i18n_keys_aligned_with_zh_locale() -> None:
    """WebUI 静态资源引用的 i18n 键应在 zh.json 中存在。"""
    malformed, missing_zh, parity = audit()
    assert not malformed, malformed
    assert not missing_zh, list(missing_zh.keys())
    assert not parity, parity


def test_audit_detects_malformed_html_marker(tmp_path: Path, monkeypatch) -> None:
    """畸形 data-i18n 写入正文时应被检出。"""
    import scripts.audit_webui_i18n as mod

    static = tmp_path / "static"
    static.mkdir()
    (static / "i18n" / "locales").mkdir(parents=True)
    for lng in ("zh", "en", "ja", "ko"):
        (static / "i18n" / "locales" / f"{lng}.json").write_text("{}", encoding="utf-8")
    (static / "page.html").write_text(
        '<p>data-i18n="foo.bar">broken</p>',
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "STATIC", static)
    monkeypatch.setattr(mod, "LOCALES", static / "i18n" / "locales")
    malformed, _, _ = mod.audit()
    assert malformed
