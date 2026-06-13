from __future__ import annotations

"""所有配置段数据类。"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.core.config.base import ConfigBase

__all__ = [
    "ServerCfg",
    "AnthCfg",
    "AuthCfg",
    "GatewayCfg",
    "ProxyCfg",
    "FncallCfg",
    "DebugCfg",
    "AutoupdateCfg",
    "PlatformsCfg",
    "PlatformsProxyCfg",
    "ModelMappingCfg",
    "AppConfig",
]


@dataclass
class ServerCfg(ConfigBase):
    """服务器基础配置：版本、主机地址、端口和调试开关。"""
    version: str = "2.2.21"
    host: str = "0.0.0.0"
    port: int = 1337
    debug: bool = False
    startup_force_kill_port: bool = True


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

    def is_platform_enabled(self, name: str) -> bool:
        """判断平台是否允许参与并发竞速。

        当 ``group_list`` 为空时视为"未配置"，所有平台均可竞速
        （保持向后兼容，避免默认配置阻断竞速）。
        """
        if not self.group_list_set:
            return True
        if self.group_list_type.strip().lower() == "blacklist":
            return name not in self.group_list_set
        return name in self.group_list_set


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
    protocol: str = "xml"                      # 协议模式：xml | original | antml | bracket | custom | nous
    fncall_mapping: Dict[str, str] = field(default_factory=dict)  # 平台到协议的映射
    custom_prompt_en: str = ""                 # custom 协议英文 prompt 模板
    custom_prompt_zh: str = ""                 # custom 协议中文 prompt 模板
    templates: Dict[str, str] = field(default_factory=dict)
    record_prompt: bool = False
    print_prompt: bool = False                 # 注入 prompt 时是否写入日志文件


@dataclass
class DebugCfg(ConfigBase):
    """调试日志级别配置。"""
    level: str = "INFO"
    color: bool = True


@dataclass
class AutoupdateCfg(ConfigBase):
    """自动更新配置：开关、分支和检查间隔。"""
    enabled: bool = False
    branch: str = "main"
    interval: int = 300  # 检查间隔（秒）


@dataclass
class PlatformsCfg(ConfigBase):
    """平台黑白名单配置。"""
    platform_list_type: str = "blacklist"
    platform_list: List[str] = field(default_factory=list)
    platform_list_set: set = field(default_factory=set, repr=False, init=False)

    def __post_init__(self) -> None:
        self.platform_list_set = set(self.platform_list)


@dataclass
class PlatformsProxyCfg(ConfigBase):
    """允许使用代理切换的平台列表（支持黑白名单）。

    enabled_platforms 的语义由 group_list_type 决定：
    * "whitelist"（默认，向后兼容）：仅列表中的平台可使用代理切换。
    * "blacklist"：列表外的平台均可使用代理切换。
    """
    enabled_platforms: List[str] = field(default_factory=list)
    enabled_platforms_set: set = field(default_factory=set, repr=False, init=False)
    group_list_type: str = "whitelist"

    def __post_init__(self) -> None:
        self.enabled_platforms_set = set(self.enabled_platforms)

    def is_platform_enabled(self, name: str) -> bool:
        """根据 group_list_type 判断平台是否允许代理切换。

        当 ``enabled_platforms`` 为空时保持旧语义（无平台被允许代理切换）；
        列表非空时按 ``group_list_type`` 走白名单或黑名单。
        """
        if not self.enabled_platforms_set:
            return False
        if self.group_list_type.strip().lower() == "blacklist":
            return name not in self.enabled_platforms_set
        return name in self.enabled_platforms_set


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
    proxy: ProxyCfg = field(default_factory=ProxyCfg)
    platforms_proxy: PlatformsProxyCfg = field(default_factory=PlatformsProxyCfg)
    fncall: FncallCfg = field(default_factory=FncallCfg)
    platforms: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    platforms_cfg: PlatformsCfg = field(default_factory=PlatformsCfg)
    debug: DebugCfg = field(default_factory=DebugCfg)
    model_mapping: ModelMappingCfg = field(default_factory=ModelMappingCfg)
    autoupdate: AutoupdateCfg = field(default_factory=AutoupdateCfg)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppConfig":
        """重写 from_dict，特殊处理 [platforms] 段和模型映射合并。

        [platforms] 在 TOML 中同时包含：
        - platform_list_type / platform_list -> PlatformsCfg
        - 其他键（qwen, deepseek 等） -> platforms raw dict

        模型映射支持三种来源（优先级从高到低）：
        1. 协议级：[anthropic.model_mapping] / [openai.model_mapping]
        2. 根级协议：[model_mapping.anthropic] / [model_mapping.openai]
        3. 根级全局：[model_mapping]（非 anthropic/openai 的键作为全局 fallback）
        """
        # 分离 platforms 段
        platforms_raw = {}
        platforms_cfg_data = {}
        raw_platforms = data.get("platforms", {})
        if isinstance(raw_platforms, dict):
            for k, v in raw_platforms.items():
                if k in ("platform_list_type", "platform_list"):
                    platforms_cfg_data[k] = v
                else:
                    platforms_raw[k] = v if isinstance(v, dict) else {}

        # 用分离后的数据构造 platforms_cfg
        data = dict(data)
        data["platforms_cfg"] = platforms_cfg_data
        data["platforms"] = platforms_raw

        # 提取 openai.model_mapping（无 OpenAICfg 段，需手动提取）
        openai_section_mm = {}
        raw_openai = data.get("openai", {})
        if isinstance(raw_openai, dict):
            openai_section_mm = dict(raw_openai.get("model_mapping", {}))

        # 构造实例
        instance = super().from_dict(data)

        # 合并模型映射
        global_mm = data.get("model_mapping", {})
        if isinstance(global_mm, dict):
            root_anth_mm = dict(global_mm.get("anthropic", {}))
            root_openai_mm = dict(global_mm.get("openai", {}))
            global_fallback = {k: v for k, v in global_mm.items() if k not in ("anthropic", "openai")}
        else:
            root_anth_mm = {}
            root_openai_mm = {}
            global_fallback = {}

        # Anthropic 合并：协议级 > 根级协议 > 全局 fallback
        anth_section_mm = instance.anthropic.model_mapping
        merged_anth = dict(global_fallback)
        merged_anth.update(root_anth_mm)
        merged_anth.update(anth_section_mm)

        # OpenAI 合并：协议级 > 根级协议 > 全局 fallback
        merged_openai = dict(global_fallback)
        merged_openai.update(root_openai_mm)
        merged_openai.update(openai_section_mm)

        # 写入合并结果
        instance.model_mapping.anthropic = merged_anth
        instance.model_mapping.openai = merged_openai

        return instance
