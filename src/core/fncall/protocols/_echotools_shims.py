from __future__ import annotations

"""echotools 协议模块重导出（合并 shim，满足目录宽度 ≤7）。"""

from echotools.fncall.protocols.antml import AntmlProtocol
from echotools.fncall.protocols.antml import *  # noqa: F401,F403
from echotools.fncall.protocols.bracket import BracketProtocol
from echotools.fncall.protocols.bracket import *  # noqa: F401,F403
from echotools.fncall.protocols.custom import CustomProtocol
from echotools.fncall.protocols.custom import *  # noqa: F401,F403
from echotools.fncall.protocols.dsml import DsmlProtocol
from echotools.fncall.protocols.dsml import *  # noqa: F401,F403
from echotools.fncall.protocols.nous import NousProtocol
from echotools.fncall.protocols.nous import *  # noqa: F401,F403
from echotools.fncall.protocols.original import OriginalProtocol
from echotools.fncall.protocols.original import *  # noqa: F401,F403
from echotools.fncall.protocols.xml import XmlProtocol
from echotools.fncall.protocols.xml import *  # noqa: F401,F403

__all__ = [
    "AntmlProtocol",
    "BracketProtocol",
    "CustomProtocol",
    "DsmlProtocol",
    "NousProtocol",
    "OriginalProtocol",
    "XmlProtocol",
]
