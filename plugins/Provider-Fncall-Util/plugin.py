from __future__ import annotations

from provider_sdk import ProviderPlugin
from provider_sdk.extensions.fncall import FncallPluginMixin


class FncallUtilPlugin(ProviderPlugin, FncallPluginMixin):
    async def on_load(self) -> None:
        from echotools.protocol.base import register_protocol
        from provider_fncall_util.protocols.antml import AntmlProtocol
        from provider_fncall_util.protocols.bracket import BracketProtocol
        from provider_fncall_util.protocols.custom import CustomProtocol
        from provider_fncall_util.protocols.dsml import DsmlProtocol
        from provider_fncall_util.protocols.nous import NousProtocol
        from provider_fncall_util.protocols.original import OriginalProtocol
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


def create_plugin() -> FncallUtilPlugin:
    return FncallUtilPlugin()
