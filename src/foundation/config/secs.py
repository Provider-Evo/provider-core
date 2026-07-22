from __future__ import annotations

"""所有配置段数据类。"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.foundation.config.base import ConfigBase
from src.foundation.paths import project_root

__all__ = [
    "ServerCfg",
    "AnthCfg",
    "AuthCfg",
    "GatewayCfg",
    "HttpPoolCfg",
    "FallbackCfg",
    "CacheCfg",
    "CircuitCfg",
    "VirtualKeyCfg",
    "RateLimitCfg",
    "MetricsCfg",
    "TerminalCfg",
    "ProxyCfg",
    "FncallCfg",
    "DebugCfg",
    "AutoupdateCfg",
    "PlatformsCfg",
    "AdapterProxyCfg",
    "PlatformsProxyCfg",
    "ModelMappingCfg",
    "AppConfig",
]


def _template_server_version() -> str:
    path = project_root / "template" / "template_config.toml"
    if not path.is_file():
        return "0.0.0"
    try:
        try:
            import tomllib
        except ModuleNotFoundError:
            import tomli as tomllib  # type: ignore[no-redef]
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        version = data.get("server", {}).get("version")
        return str(version) if version else "0.0.0"
    except Exception:
        return "0.0.0"


@dataclass
class ServerCfg(ConfigBase):
    """服务器基础配置：版本、主机地址、端口和调试开关。"""
    version: str = field(default_factory=_template_server_version)
    host: str = "0.0.0.0"
    port: int = 1337
    debug: bool = False
    startup_force_kill_port: bool = True
    fast_restart: bool = True
    max_restarts: int = 3


@dataclass
class AnthCfg(ConfigBase):
    """Anthropic 协议相关配置：API 版本和模型映射。"""
    api_version: str = "2023-06-01"
    model_mapping: Dict[str, str] = field(default_factory=dict)


@dataclass
class AuthCfg(ConfigBase):
    """认证配置：API Key 列表和群组黑白名单。"""
    enabled: bool = False
    keys: List[str] = field(default_factory=list)
    group_list_type: str = "blacklist"
    group_list: List[str] = field(default_factory=list)
    group_list_set: set = field(default_factory=set, repr=False, init=False)

    def __post_init__(self) -> None:
        self.group_list_set = set(self.group_list)


@dataclass
class GatewayCfg(ConfigBase):
    """网关并发配置：并发开关、并发数、最小 Token 数和竞速平台名单。"""
    concurrent_enabled: bool = True
    concurrent_count: int = 3
    min_tokens: int = 10
    # 竞速名单。决定哪些平台*允许并发竞速*；不在名单内的平台仍可正常
    # 路由，只是该请求退化为单发（n=1）。
    # "whitelist"：仅 group_list 中的平台可参与竞速。
    # "blacklist"：除 group_list 外的平台均可参与竞速。
    # group_list 为空时视为"未配置"，所有平台均可竞速（向后兼容）。
    group_list_type: str = "whitelist"
    group_list: List[str] = field(default_factory=list)
    group_list_set: set = field(default_factory=set, repr=False, init=False)

    def __post_init__(self) -> None:
        self.group_list_set = set(self.group_list)

    def is_adapter_enabled(self, name: str) -> bool:
        """判断平台是否允许参与并发竞速。

        当 ``group_list`` 为空时视为"未配置"，所有平台均可竞速
        （保持向后兼容，避免默认配置阻断竞速）。
        """
        if not self.group_list_set:
            return True
        if self.group_list_type.strip().lower() == "blacklist":
            return name not in self.group_list_set
        return name in self.group_list_set
    # 向后兼容别名
    def is_platform_enabled(self, name: str) -> bool:
        return self.is_adapter_enabled(name)


@dataclass
class ProxyCfg(ConfigBase):
    """HTTP 代理配置：代理地址、开关和 URL 匹配规则。"""
    proxy_server: str = ""
    proxy_enabled: bool = False
    proxy_urls: List[str] = field(default_factory=list)
    proxy_url_patterns: List[re.Pattern] = field(default_factory=list, repr=False, init=False)

    def __post_init__(self) -> None:
        self.proxy_url_patterns = [re.compile(p) for p in self.proxy_urls]


@dataclass
class FncallCfg(ConfigBase):
    """函数调用协议与模板配置。"""
    protocol: str = "entml"                    # 协议模式：entml | xml | original | antml | bracket | custom | nous | dsml
    fncall_mapping: Dict[str, str] = field(default_factory=dict)  # 平台到协议的映射
    custom_prompt_en: str = ""                 # custom 协议英文 prompt 模板
    custom_prompt_zh: str = ""                 # custom 协议中文 prompt 模板
    templates: Dict[str, str] = field(default_factory=dict)
    record_prompt: bool = False
    print_prompt: bool = False                 # 注入 prompt 时是否写入日志文件


@dataclass
class HttpPoolCfg(ConfigBase):
    """HTTP 连接池配置：控制 aiohttp TCPConnector 的连接复用行为。

    优化点：
    1. 添加读取超时配置
    2. 添加写入超时配置
    3. 支持分级超时策略
    """
    limit: int = 200              # 总连接数上限
    limit_per_host: int = 20      # 单主机连接数上限
    keepalive_timeout: int = 30   # keepalive 超时（秒）
    connect_timeout: int = 10     # 连接建立超时（秒）
    read_timeout: int = 60        # 读取超时（秒）
    write_timeout: int = 30       # 写入超时（秒）
    total_timeout: int = 120      # 总超时（秒）


@dataclass
class FallbackCfg(ConfigBase):
    """模型 Fallback 链（参考 LiteLLM Router）。"""
    enabled: bool = True
    chains: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class CacheCfg(ConfigBase):
    """非流式响应精确缓存。"""
    enabled: bool = False
    max_entries: int = 512
    ttl_seconds: int = 3600


@dataclass
class CircuitCfg(ConfigBase):
    """平台熔断：成功率低于阈值时临时 open。"""
    enabled: bool = True
    window_size: int = 20
    failure_threshold: float = 0.5
    cooldown_seconds: int = 300


@dataclass
class VirtualKeyCfg(ConfigBase):
    """Virtual Key 二次分发。"""
    enabled: bool = False


@dataclass
class RateLimitCfg(ConfigBase):
    """网关侧按 Key / IP 限流。"""
    enabled: bool = False
    key_rpm: int = 600
    ip_rpm: int = 180


@dataclass
class MetricsCfg(ConfigBase):
    """Prometheus /metrics 导出。"""
    enabled: bool = True


@dataclass
class TerminalCfg(ConfigBase):
    """WebUI 远程终端：恢复策略、后端与资源上限。"""
    backend: str = "direct"  # direct | tmux (Unix only)
    preserve_on_reload: bool = True
    preserve_on_shutdown: bool = False
    ring_buffer_kb: int = 256
    orphan_alive_hours: int = 24
    orphan_destroyed_days: int = 7
    require_ssh_host_key: bool = True
    max_history_lines: int = 5000
    subprocess_monitor_interval: int = 1
    enable_subprocess_monitoring: bool = True
    audit_enabled: bool = True


@dataclass
class DebugCfg(ConfigBase):
    """调试日志级别配置。"""
    level: str = "INFO"
    color: bool = True
    access_log: bool = True
    log_name: str = "provider-v2"


@dataclass
class AutoupdateCfg(ConfigBase):
    """自动更新配置：开关、分支、检查间隔、差异更新和镜像源。"""
    enabled: bool = False
    branch: str = "main"
    interval: int = 300  # 检查间隔（秒）
    diff_update: bool = True  # 差异更新：仅覆盖变更文件
    mirrors: List[str] = field(default_factory=lambda: [
        "https://github.com/",
    ])


@dataclass
class PlatformsCfg(ConfigBase):
    """平台黑白名单配置。"""
    platform_list_type: str = "blacklist"
    platform_list: List[str] = field(default_factory=list)
    platform_list_set: set = field(default_factory=set, repr=False, init=False)

    def __post_init__(self) -> None:
        self.platform_list_set = set(self.platform_list)


@dataclass
class AdapterProxyCfg(ConfigBase):
    """适配器代理切换配置（WebUI 平台/模型切换白名单）。"""
    enable_adapters: List[str] = field(default_factory=list)
    group_list_type: str = "whitelist"
    enable_adapters_set: set = field(default_factory=set, repr=False, init=False)

    def __post_init__(self) -> None:
        self.enable_adapters_set = set(self.enable_adapters)


@dataclass
class PlatformsProxyCfg(ConfigBase):
    """向后兼容：旧 platforms_proxy 段（与 adapter_proxy 语义相同）。"""
    enabled_platforms: List[str] = field(default_factory=list)
    group_list_type: str = "whitelist"
    enabled_platforms_set: set = field(default_factory=set, repr=False, init=False)

    def __post_init__(self) -> None:
        self.enabled_platforms_set = set(self.enabled_platforms)


@dataclass
class ModelMappingCfg(ConfigBase):
    """根级模型映射配置，支持按协议分类。"""
    anthropic: Dict[str, str] = field(default_factory=dict)
    openai: Dict[str, str] = field(default_factory=dict)


@dataclass
class AppConfig(ConfigBase):
    """应用顶层配置：聚合所有子配置段。"""
    server: ServerCfg = field(default_factory=ServerCfg)
    anthropic: AnthCfg = field(default_factory=AnthCfg)
    auth: AuthCfg = field(default_factory=AuthCfg)
    gateway: GatewayCfg = field(default_factory=GatewayCfg)
    http_pool: HttpPoolCfg = field(default_factory=HttpPoolCfg)
    fallback: FallbackCfg = field(default_factory=FallbackCfg)
    cache: CacheCfg = field(default_factory=CacheCfg)
    circuit: CircuitCfg = field(default_factory=CircuitCfg)
    virtual_keys: VirtualKeyCfg = field(default_factory=VirtualKeyCfg)
    rate_limit: RateLimitCfg = field(default_factory=RateLimitCfg)
    metrics: MetricsCfg = field(default_factory=MetricsCfg)
    terminal: TerminalCfg = field(default_factory=TerminalCfg)
    proxy: ProxyCfg = field(default_factory=ProxyCfg)
    fncall: FncallCfg = field(default_factory=FncallCfg)
    platforms: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    platforms_cfg: PlatformsCfg = field(default_factory=PlatformsCfg)
    adapter_proxy: AdapterProxyCfg = field(default_factory=AdapterProxyCfg)
    platforms_proxy: PlatformsProxyCfg = field(default_factory=PlatformsProxyCfg)
    debug: DebugCfg = field(default_factory=DebugCfg)
    model_mapping: ModelMappingCfg = field(default_factory=ModelMappingCfg)
    autoupdate: AutoupdateCfg = field(default_factory=AutoupdateCfg)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """重写 from_dict，特殊处理 [platforms] 段和模型映射合并。"""
        platforms_raw, platforms_cfg_data = _split_platforms_section(data)
        data = dict(data)
        data["platforms_cfg"] = platforms_cfg_data
        data["platforms"] = platforms_raw

        openai_section_mm: dict[str, Any] = {}
        raw_openai = data.get("openai", {})
        if isinstance(raw_openai, dict):
            openai_section_mm = dict(raw_openai.get("model_mapping", {}))

        instance = super().from_dict(data)
        _merge_model_mappings(instance, data, openai_section_mm)
        return instance


def _split_platforms_section(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """分离 [platforms] 段为 platforms_cfg 与 platforms raw dict。"""
    platforms_raw: dict[str, Any] = {}
    platforms_cfg_data: dict[str, Any] = {}
    raw_platforms = data.get("platforms", {})
    if isinstance(raw_platforms, dict):
        for k, v in raw_platforms.items():
            if k in ("platform_list_type", "platform_list"):
                platforms_cfg_data[k] = v
            else:
                platforms_raw[k] = v if isinstance(v, dict) else {}
    return platforms_raw, platforms_cfg_data


def _merge_model_mappings(
    instance: AppConfig,
    data: dict[str, Any],
    openai_section_mm: dict[str, Any],
) -> None:
    """合并三层模型映射并写入 instance.model_mapping。"""
    global_mm = data.get("model_mapping", {})
    if isinstance(global_mm, dict):
        root_anth_mm = dict(global_mm.get("anthropic", {}))
        root_openai_mm = dict(global_mm.get("openai", {}))
        global_fallback = {k: v for k, v in global_mm.items() if k not in ("anthropic", "openai")}
    else:
        root_anth_mm = {}
        root_openai_mm = {}
        global_fallback = {}
    merged_anth = dict(global_fallback)
    merged_anth.update(root_anth_mm)
    merged_anth.update(instance.anthropic.model_mapping)
    merged_openai = dict(global_fallback)
    merged_openai.update(root_openai_mm)
    merged_openai.update(openai_section_mm)
    instance.model_mapping.anthropic = merged_anth
    instance.model_mapping.openai = merged_openai

