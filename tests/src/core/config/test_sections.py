"""Tests for src/core/config/sections.py."""
import pytest

from src.core.config.sections import (
    ServerCfg, AnthCfg, AuthCfg, GatewayCfg, ProxyCfg,
    FncallCfg, DebugCfg, AutoupdateCfg, PlatformsCfg,
    PlatformsProxyCfg, ModelMappingCfg, AppConfig,
)


class TestServerCfg:
    def test_default_values(self):
        cfg = ServerCfg()
        assert cfg.version == "2.2.21"
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 1337
        assert cfg.debug is False
        assert cfg.startup_force_kill_port is True

    def test_custom_values(self):
        cfg = ServerCfg(version="3.0.0", port=8080)
        assert cfg.version == "3.0.0"
        assert cfg.port == 8080


class TestAnthCfg:
    def test_default_values(self):
        cfg = AnthCfg()
        assert cfg.api_version == "2023-06-01"
        assert cfg.model_mapping == {}

    def test_with_model_mapping(self):
        mapping = {"claude-3": "claude-3-opus"}
        cfg = AnthCfg(model_mapping=mapping)
        assert cfg.model_mapping == mapping


class TestAuthCfg:
    def test_default_values(self):
        cfg = AuthCfg()
        assert cfg.enabled is False
        assert cfg.keys == []
        assert cfg.group_list_type == "blacklist"
        assert cfg.group_list == []
        assert cfg.group_list_set == set()

    def test_post_init_sets_group_set(self):
        cfg = AuthCfg(group_list=["admin", "user"])
        assert cfg.group_list_set == {"admin", "user"}


class TestGatewayCfg:
    def test_default_values(self):
        cfg = GatewayCfg()
        assert cfg.concurrent_enabled is True
        assert cfg.concurrent_count == 3
        assert cfg.min_tokens == 10


class TestProxyCfg:
    def test_default_values(self):
        cfg = ProxyCfg()
        assert cfg.proxy_server == ""
        assert cfg.proxy_enabled is False
        assert cfg.proxy_urls == []
        assert cfg.proxy_url_patterns == []

    def test_post_init_compiles_patterns(self):
        cfg = ProxyCfg(proxy_urls=[r"^https://api\.", r"^http://test\."])
        assert len(cfg.proxy_url_patterns) == 2
        assert hasattr(cfg.proxy_url_patterns[0], "match")


class TestFncallCfg:
    def test_default_values(self):
        cfg = FncallCfg()
        assert cfg.protocol == "xml"
        assert cfg.fncall_mapping == {}
        assert cfg.custom_prompt_en == ""
        assert cfg.custom_prompt_zh == ""
        assert cfg.templates == {}
        assert cfg.record_prompt is False
        assert cfg.print_prompt is False


class TestDebugCfg:
    def test_default_values(self):
        cfg = DebugCfg()
        assert cfg.level == "INFO"
        assert cfg.color is True


class TestAutoupdateCfg:
    def test_default_values(self):
        cfg = AutoupdateCfg()
        assert cfg.enabled is False
        assert cfg.branch == "main"
        assert cfg.interval == 300


class TestPlatformsCfg:
    def test_default_values(self):
        cfg = PlatformsCfg()
        assert cfg.platform_list_type == "blacklist"
        assert cfg.platform_list == []
        assert cfg.platform_list_set == set()

    def test_post_init_sets_platform_set(self):
        cfg = PlatformsCfg(platform_list=["qwen", "deepseek"])
        assert cfg.platform_list_set == {"qwen", "deepseek"}


class TestPlatformsProxyCfg:
    def test_default_values(self):
        cfg = PlatformsProxyCfg()
        assert cfg.enabled_platforms == []
        assert cfg.enabled_platforms_set == set()

    def test_post_init_sets_enabled_set(self):
        cfg = PlatformsProxyCfg(enabled_platforms=["ollama", "vllm"])
        assert cfg.enabled_platforms_set == {"ollama", "vllm"}


class TestModelMappingCfg:
    def test_default_values(self):
        cfg = ModelMappingCfg()
        assert cfg.anthropic == {}
        assert cfg.openai == {}

    def test_with_mappings(self):
        cfg = ModelMappingCfg(
            anthropic={"claude": "claude-3"},
            openai={"gpt4": "gpt-4"}
        )
        assert cfg.anthropic == {"claude": "claude-3"}
        assert cfg.openai == {"gpt4": "gpt-4"}


class TestAppConfig:
    def test_default_has_all_sections(self):
        cfg = AppConfig()
        assert isinstance(cfg.server, ServerCfg)
        assert isinstance(cfg.anthropic, AnthCfg)
        assert isinstance(cfg.auth, AuthCfg)
        assert isinstance(cfg.gateway, GatewayCfg)
        assert isinstance(cfg.proxy, ProxyCfg)
        assert isinstance(cfg.platforms_proxy, PlatformsProxyCfg)
        assert isinstance(cfg.fncall, FncallCfg)
        assert isinstance(cfg.platforms, dict)
        assert isinstance(cfg.platforms_cfg, PlatformsCfg)
        assert isinstance(cfg.debug, DebugCfg)
        assert isinstance(cfg.model_mapping, ModelMappingCfg)
        assert isinstance(cfg.autoupdate, AutoupdateCfg)

    def test_from_dict_basic(self):
        data = {
            "server": {"port": 9999, "debug": True},
            "gateway": {"concurrent_count": 5},
        }
        cfg = AppConfig.from_dict(data)
        assert cfg.server.port == 9999
        assert cfg.server.debug is True
        assert cfg.gateway.concurrent_count == 5

    def test_from_dict_with_platforms(self):
        data = {
            "platforms": {
                "platform_list_type": "whitelist",
                "platform_list": ["qwen"],
                "qwen": {"api_key": "sk-123"},
                "deepseek": {"api_key": "sk-456"},
            }
        }
        cfg = AppConfig.from_dict(data)
        assert cfg.platforms_cfg.platform_list_type == "whitelist"
        assert cfg.platforms_cfg.platform_list_set == {"qwen"}
        assert "qwen" in cfg.platforms
        assert "deepseek" in cfg.platforms

    def test_from_dict_model_mapping_anthropic(self):
        data = {
            "model_mapping": {
                "anthropic": {"claude-2": "claude-3"},
                "global-fallback": "qwen-max",
            },
            "anthropic": {
                "model_mapping": {"claude-1": "claude-2"},
            },
        }
        cfg = AppConfig.from_dict(data)
        # Protocol-level should override root-level
        assert cfg.model_mapping.anthropic["claude-1"] == "claude-2"
        assert cfg.model_mapping.anthropic["claude-2"] == "claude-3"
        assert cfg.model_mapping.anthropic["global-fallback"] == "qwen-max"

    def test_from_dict_model_mapping_openai(self):
        data = {
            "model_mapping": {
                "openai": {"gpt-3": "gpt-4"},
            },
            "openai": {
                "model_mapping": {"gpt-4": "gpt-4-turbo"},
            },
        }
        cfg = AppConfig.from_dict(data)
        assert cfg.model_mapping.openai["gpt-3"] == "gpt-4"
        assert cfg.model_mapping.openai["gpt-4"] == "gpt-4-turbo"
