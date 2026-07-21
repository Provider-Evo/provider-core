"""WebUI 配置面板 schema — 与 template/template_config.toml 对齐。"""

from __future__ import annotations

from typing import Any, Dict, List

__all__ = ["CONFIG_PANEL_SCHEMA", "KNOWN_TOP_LEVEL_SECTIONS", "WEBUI_CONFIG_PANEL_SCHEMA", "WEBUI_CONFIG_KNOWN_KEYS"]

_PROTOCOL_OPTIONS = [
    "entml",
    "xml",
    "antml",
    "original",
    "nous",
    "bracket",
    "dsml",
    "custom",
]

_LIST_TYPE_OPTIONS = ["blacklist", "whitelist"]
_LOG_LEVEL_OPTIONS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _section(section_id: str, title: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"id": section_id, "title": title, "fields": fields}


CONFIG_PANEL_SCHEMA: Dict[str, Any] = {
    "file": "config/main_config.toml",
    "sections": [
        _section(
            "server",
            "server",
            [
                {"key": "version", "type": "readonly", "label": "version"},
                {"key": "host", "type": "string", "label": "host"},
                {"key": "port", "type": "number", "label": "port", "min": 1, "max": 65535},
                {"key": "debug", "type": "boolean", "label": "debug"},
                {"key": "startup_force_kill_port", "type": "boolean", "label": "startup_force_kill_port"},
                {"key": "fast_restart", "type": "boolean", "label": "fast_restart"},
                {"key": "max_restarts", "type": "number", "label": "max_restarts", "min": 0},
            ],
        ),
        _section(
            "auth",
            "auth",
            [
                {"key": "enabled", "type": "boolean", "label": "enabled"},
                {"key": "keys", "type": "list", "label": "keys"},
                {
                    "key": "group_list_type",
                    "type": "select",
                    "label": "group_list_type",
                    "options": _LIST_TYPE_OPTIONS,
                },
                {"key": "group_list", "type": "list", "label": "group_list"},
            ],
        ),
        _section(
            "gateway",
            "gateway",
            [
                {"key": "concurrent_enabled", "type": "boolean", "label": "concurrent_enabled"},
                {"key": "concurrent_count", "type": "number", "label": "concurrent_count", "min": 1},
                {"key": "min_tokens", "type": "number", "label": "min_tokens", "min": 0},
                {
                    "key": "group_list_type",
                    "type": "select",
                    "label": "group_list_type",
                    "options": _LIST_TYPE_OPTIONS,
                },
                {"key": "group_list", "type": "list", "label": "group_list"},
            ],
        ),
        _section(
            "http_pool",
            "http_pool",
            [
                {"key": "limit", "type": "number", "label": "limit", "min": 1},
                {"key": "limit_per_host", "type": "number", "label": "limit_per_host", "min": 1},
                {"key": "keepalive_timeout", "type": "number", "label": "keepalive_timeout", "min": 1},
                {"key": "connect_timeout", "type": "number", "label": "connect_timeout", "min": 1},
            ],
        ),
        _section(
            "proxy",
            "proxy",
            [
                {"key": "proxy_enabled", "type": "boolean", "label": "proxy_enabled"},
                {"key": "proxy_server", "type": "string", "label": "proxy_server"},
                {"key": "proxy_urls", "type": "list", "label": "proxy_urls"},
            ],
        ),
        _section(
            "adapter_proxy",
            "adapter_proxy",
            [
                {"key": "enable_adapters", "type": "list", "label": "enable_adapters"},
                {
                    "key": "group_list_type",
                    "type": "select",
                    "label": "group_list_type",
                    "options": _LIST_TYPE_OPTIONS,
                },
            ],
        ),
        _section(
            "platforms_proxy",
            "platforms_proxy",
            [
                {"key": "enabled_platforms", "type": "list", "label": "enabled_platforms"},
                {
                    "key": "group_list_type",
                    "type": "select",
                    "label": "group_list_type",
                    "options": _LIST_TYPE_OPTIONS,
                },
            ],
        ),
        _section(
            "platforms",
            "platforms",
            [
                {
                    "key": "platform_list_type",
                    "type": "select",
                    "label": "platform_list_type",
                    "options": _LIST_TYPE_OPTIONS,
                },
                {"key": "platform_list", "type": "list", "label": "platform_list"},
            ],
        ),
        _section(
            "fncall",
            "fncall",
            [
                {
                    "key": "protocol",
                    "type": "select",
                    "label": "protocol",
                    "options": _PROTOCOL_OPTIONS,
                },
                {"key": "record_prompt", "type": "boolean", "label": "record_prompt"},
                {"key": "print_prompt", "type": "boolean", "label": "print_prompt"},
                {"key": "custom_prompt_en", "type": "string", "label": "custom_prompt_en", "wide": True},
                {"key": "custom_prompt_zh", "type": "string", "label": "custom_prompt_zh", "wide": True},
                {"key": "fncall_mapping", "type": "mapping", "label": "fncall_mapping"},
                {"key": "templates", "type": "json", "label": "templates"},
            ],
        ),
        _section(
            "debug",
            "debug",
            [
                {
                    "key": "level",
                    "type": "select",
                    "label": "level",
                    "options": _LOG_LEVEL_OPTIONS,
                },
                {"key": "color", "type": "boolean", "label": "color"},
                {"key": "access_log", "type": "boolean", "label": "access_log"},
                {"key": "log_name", "type": "string", "label": "log_name"},
            ],
        ),
        _section(
            "fallback",
            "fallback",
            [
                {"key": "enabled", "type": "boolean", "label": "enabled"},
                {"key": "chains", "type": "mapping", "label": "chains"},
            ],
        ),
        _section(
            "cache",
            "cache",
            [
                {"key": "enabled", "type": "boolean", "label": "enabled"},
                {"key": "max_entries", "type": "number", "label": "max_entries", "min": 1},
                {"key": "ttl_seconds", "type": "number", "label": "ttl_seconds", "min": 0},
            ],
        ),
        _section(
            "circuit",
            "circuit",
            [
                {"key": "enabled", "type": "boolean", "label": "enabled"},
                {"key": "window_size", "type": "number", "label": "window_size", "min": 1},
                {
                    "key": "failure_threshold",
                    "type": "number",
                    "label": "failure_threshold",
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                },
                {"key": "cooldown_seconds", "type": "number", "label": "cooldown_seconds", "min": 0},
            ],
        ),
        _section(
            "virtual_keys",
            "virtual_keys",
            [
                {"key": "enabled", "type": "boolean", "label": "enabled"},
            ],
        ),
        _section(
            "rate_limit",
            "rate_limit",
            [
                {"key": "enabled", "type": "boolean", "label": "enabled"},
                {"key": "key_rpm", "type": "number", "label": "key_rpm", "min": 0},
                {"key": "ip_rpm", "type": "number", "label": "ip_rpm", "min": 0},
            ],
        ),
        _section(
            "metrics",
            "metrics",
            [
                {"key": "enabled", "type": "boolean", "label": "enabled"},
            ],
        ),
        _section(
            "anthropic",
            "anthropic",
            [
                {"key": "api_version", "type": "string", "label": "api_version"},
                {"key": "model_mapping", "type": "mapping", "label": "model_mapping"},
            ],
        ),
        _section(
            "openai",
            "openai",
            [
                {"key": "model_mapping", "type": "mapping", "label": "model_mapping"},
            ],
        ),
        _section(
            "model_mapping",
            "model_mapping",
            [
                {"key": "anthropic", "type": "mapping", "label": "anthropic"},
                {"key": "openai", "type": "mapping", "label": "openai"},
            ],
        ),
        _section(
            "terminal",
            "terminal",
            [
                {"key": "max_history_lines", "type": "number", "label": "max_history_lines", "min": 100},
                {
                    "key": "subprocess_monitor_interval",
                    "type": "number",
                    "label": "subprocess_monitor_interval",
                    "min": 1,
                },
                {
                    "key": "enable_subprocess_monitoring",
                    "type": "boolean",
                    "label": "enable_subprocess_monitoring",
                },
            ],
        ),
    ],
}

KNOWN_TOP_LEVEL_SECTIONS = frozenset(section["id"] for section in CONFIG_PANEL_SCHEMA["sections"])

_WEBUI_THEME_OPTIONS = ["auto", "light", "dark"]
_WEBUI_COMPACT_OPTIONS = ["0", "1"]
_WEBUI_LAYOUT_OPTIONS = ["horizontal", "vertical"]

WEBUI_CONFIG_PANEL_SCHEMA: Dict[str, Any] = {
    "file": "config/webui_config.toml",
    "flat": True,
    "sections": [
        _section(
            "display",
            "display",
            [
                {
                    "key": "theme",
                    "type": "select",
                    "label": "theme",
                    "options": _WEBUI_THEME_OPTIONS,
                },
                {
                    "key": "compact",
                    "type": "select",
                    "label": "compact",
                    "options": _WEBUI_COMPACT_OPTIONS,
                    "optionLabels": {"0": "off", "1": "on"},
                },
                {
                    "key": "fontSizeBase",
                    "type": "number",
                    "label": "font_size_base",
                    "min": 12,
                    "max": 20,
                },
            ],
        ),
        _section(
            "timing",
            "timing",
            [
                {
                    "key": "refreshInterval",
                    "type": "number",
                    "label": "refresh_interval",
                    "min": 0,
                    "max": 300,
                },
                {
                    "key": "timeoutMs",
                    "type": "number",
                    "label": "timeout_ms",
                    "min": 500,
                    "max": 30000,
                },
                {
                    "key": "streamIdleTimeoutMs",
                    "type": "number",
                    "label": "stream_idle_timeout_ms",
                    "min": 5000,
                    "max": 600000,
                },
            ],
        ),
        _section(
            "layout",
            "layout",
            [
                {
                    "key": "layout",
                    "type": "select",
                    "label": "tab_layout",
                    "options": _WEBUI_LAYOUT_OPTIONS,
                },
                {"key": "sidebarCompressed", "type": "boolean", "label": "sidebar_compressed"},
            ],
        ),
        _section(
            "voice",
            "voice",
            [
                {
                    "key": "sttModel",
                    "type": "select",
                    "label": "stt_model",
                    "options": [],
                    "dynamic": "stt-model",
                },
                {
                    "key": "ttsModel",
                    "type": "select",
                    "label": "tts_model",
                    "options": [],
                    "dynamic": "tts-model",
                },
                {
                    "key": "recordingDeviceId",
                    "type": "select",
                    "label": "recording_device",
                    "options": [],
                    "dynamic": "audio-input",
                },
                {"key": "ttsPrompt", "type": "textarea", "label": "tts_prompt", "wide": True},
            ],
        ),
    ],
}

WEBUI_CONFIG_KNOWN_KEYS = frozenset(
    field["key"]
    for section in WEBUI_CONFIG_PANEL_SCHEMA["sections"]
    for field in section["fields"]
)
