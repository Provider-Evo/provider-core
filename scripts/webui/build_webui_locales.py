#!/usr/bin/env python3
"""从 catalog 生成 WebUI 四语言 locale JSON（嵌套结构）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "src" / "webui" / "static" / "i18n" / "locales"

# (dot.key, zh, en, ja, ko) — source of truth
CATALOG: List[Tuple[str, str, str, str, str]] = [
    # header / sidebar / language / common
    ("header.title", "Provider-V2 WebUI", "Provider-V2 WebUI", "Provider-V2 WebUI", "Provider-V2 WebUI"),
    ("header.subtitle", "生产化内置管理台，覆盖概览、平台状态、模型清单、配置管理与日志反馈。", "Production admin console for overview, platforms, models, config, and logs.", "概要・プラットフォーム・モデル・設定・ログを扱う管理コンソール。", "개요, 플랫폼, 모델, 설정, 로그를 다루는 관리 콘솔."),
    ("header.versionLoading", "版本 loading", "Version loading", "バージョン loading", "버전 loading"),
    ("header.portableSettings", "便携设置", "Portable settings", "ポータブル設定", "휴대용 설정"),
    ("header.reloadServer", "重启服务", "Restart service", "サービス再起動", "서비스 재시작"),
    ("header.reloadConfig", "重载配置", "Reload config", "設定再読込", "설정 다시 로드"),
    ("header.switchLanguage", "切换语言", "Switch language", "言語を切り替え", "언어 전환"),
    ("header.theme", "theme: {{value}}", "theme: {{value}}", "theme: {{value}}", "theme: {{value}}"),
    ("header.refreshInterval", "refresh: {{value}}s", "refresh: {{value}}s", "refresh: {{value}}s", "refresh: {{value}}s"),
    ("header.refreshManual", "refresh: manual", "refresh: manual", "refresh: manual", "refresh: manual"),
    ("language.zh", "中文", "中文", "中文", "中文"),
    ("language.en", "English", "English", "English", "English"),
    ("language.ja", "日本語", "日本語", "日本語", "日本語"),
    ("language.ko", "한국어", "한국어", "한국어", "한국어"),
    ("sidebar.overview", "概览", "Overview", "概要", "개요"),
    ("sidebar.stats", "统计", "Stats", "統計", "통계"),
    ("sidebar.platforms", "平台", "Platforms", "プラットフォーム", "플랫폼"),
    ("sidebar.models", "模型", "Models", "モデル", "모델"),
    ("sidebar.config", "配置", "Config", "設定", "설정"),
    ("sidebar.autoupdate", "更新", "Updates", "更新", "업데이트"),
    ("sidebar.chat", "聊天", "Chat", "チャット", "채팅"),
    ("sidebar.logs", "日志", "Logs", "ログ", "로그"),
    ("sidebar.terminal", "终端", "Terminal", "ターミナル", "터미널"),
    ("sidebar.files", "文件", "Files", "ファイル", "파일"),
    ("sidebar.collapse", "折叠/展开侧边栏", "Collapse/expand sidebar", "サイドバーの折りたたみ", "사이드바 접기/펼치기"),
    ("common.loading", "加载中...", "Loading...", "読み込み中...", "로딩 중..."),
    ("common.cancel", "取消", "Cancel", "キャンセル", "취소"),
    ("common.confirm", "确认", "Confirm", "確認", "확인"),
    ("common.ok", "确定", "OK", "確定", "확인"),
    ("common.save", "保存", "Save", "保存", "저장"),
    ("common.saved", "已保存", "Saved", "保存済み", "저장됨"),
    ("common.unsaved", "未保存", "Unsaved", "未保存", "저장 안 됨"),
    ("common.close", "关闭", "Close", "閉じる", "닫기"),
    ("common.refresh", "刷新", "Refresh", "更新", "새로고침"),
    ("common.copy", "复制", "Copy", "コピー", "복사"),
    ("common.copied", "已复制", "Copied", "コピーしました", "복사됨"),
    ("common.export", "导出", "Export", "エクスポート", "보내기"),
    ("common.delete", "删除", "Delete", "削除", "삭제"),
    ("common.noData", "暂无数据", "No data", "データなし", "데이터 없음"),
    ("common.success", "成功", "Success", "成功", "성공"),
    ("common.failed", "失败", "Failed", "失敗", "실패"),
    ("common.enabled", "已启用", "Enabled", "有効", "사용"),
    ("common.disabled", "未启用", "Disabled", "無効", "사용 안 함"),
    ("common.all", "全部", "All", "すべて", "전체"),
    ("common.unknown", "未知", "Unknown", "不明", "알 수 없음"),
    ("common.off", "关闭", "Off", "オフ", "끔"),
    ("common.on", "开启", "On", "オン", "켬"),
    ("common.notUsing", "不使用", "Not used", "使用しない", "사용 안 함"),
]


def _nest(flat: Dict[str, str]) -> Dict[str, Any]:
    root: Dict[str, Any] = {}
    for key, value in sorted(flat.items()):
        parts = key.split(".")
        node = root
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return root


def _load_extra_catalog() -> List[Tuple[str, str, str, str, str]]:
    extra_path = Path(__file__).with_name("webui_i18n_extra.py")
    if not extra_path.is_file():
        return []
    ns: Dict[str, Any] = {}
    exec(extra_path.read_text(encoding="utf-8"), ns)  # noqa: S102
    return list(ns.get("EXTRA", ()))


def build() -> None:
    """公开方法 build。"""
    rows = CATALOG + _load_extra_catalog()
    for lang_idx, code in enumerate(("zh", "en", "ja", "ko"), start=1):
        flat = {row[0]: row[lang_idx] for row in rows}
        nested = _nest(flat)
        out = OUT / f"{code}.json"
        out.write_text(json.dumps(nested, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out.name} ({len(flat)} keys)")


if __name__ == "__main__":
    build()
