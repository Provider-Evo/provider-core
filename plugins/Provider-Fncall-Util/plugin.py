

from provider_sdk import ProviderPlugin
from provider_sdk.extensions.fncall import FncallPluginMixin


def _clear_custom_protocol_factory() -> None:
    """兼容旧版 echotools（无 clear_custom_protocol_factory）。"""
    try:
        from echotools.fncall.registry import clear_custom_protocol_factory

        clear_custom_protocol_factory()
        return
    except ImportError:
        pass
    try:
        import echotools.fncall.registry as reg

        reg.set_custom_protocol_factory(None)
        if hasattr(reg, "_custom_instance"):
            reg._custom_instance = None
    except ImportError:
        pass


class FncallUtilPlugin(ProviderPlugin, FncallPluginMixin):
    async def on_load(self) -> None:
        from echotools.protocol.base import register_protocol
        from provider_fncall_util.protocols.antml import AntmlProtocol
        from provider_fncall_util.protocols.bracket import BracketProtocol
        from provider_fncall_util.protocols.extra.custom import CustomProtocol
        from provider_fncall_util.protocols.dsml import DsmlProtocol
        from provider_fncall_util.protocols.nous import NousProtocol
        from provider_fncall_util.protocols.extra.origin import OriginalProtocol
        from provider_fncall_util.protocols.xml import XmlProtocol

        for proto in (
            XmlProtocol(),
            AntmlProtocol(),
            OriginalProtocol(),
            BracketProtocol(),
            NousProtocol(),
            DsmlProtocol(),
        ):
            register_protocol(proto)

        self.register_custom_protocol_factory(
            lambda prompt_en="", prompt_zh="": CustomProtocol(
                prompt_en=prompt_en, prompt_zh=prompt_zh
            )
        )
        self.ctx.logger.info(
            "Provider-Fncall-Util: xml/antml/original/bracket/nous/dsml/custom registered"
        )

    async def on_unload(self) -> None:
        try:
            from echotools.protocol.base import unregister_protocol

            for protocol_id in (
                "xml",
                "antml",
                "original",
                "bracket",
                "nous",
                "dsml",
            ):
                unregister_protocol(protocol_id)
        except ImportError:
            import echotools.protocol.base as _base

            registry = getattr(_base, "_PROTOCOL_REGISTRY", {})
            for protocol_id in (
                "xml",
                "antml",
                "original",
                "bracket",
                "nous",
                "dsml",
            ):
                registry.pop(protocol_id, None)
        _clear_custom_protocol_factory()
        self._custom_protocol_factory = None
        self.ctx.logger.info("Provider-Fncall-Util: fncall protocols unregistered")


def create_plugin() -> FncallUtilPlugin:
    return FncallUtilPlugin()

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

__all__ = [
]
