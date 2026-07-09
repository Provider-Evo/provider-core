from __future__ import annotations

"""协议注册 → echotools 重导出。"""

from echotools.fncall.protocols import *  # noqa: F401,F403

from ._echotools_shims import (
    AntmlProtocol,
    BracketProtocol,
    CustomProtocol,
    DsmlProtocol,
    NousProtocol,
    OriginalProtocol,
    XmlProtocol,
)

__all__ = [
    "AntmlProtocol",
    "BracketProtocol",
    "CustomProtocol",
    "DsmlProtocol",
    "NousProtocol",
    "OriginalProtocol",
    "XmlProtocol",
]
