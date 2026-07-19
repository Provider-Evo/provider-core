"""_echotools 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 _echotools 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""

from echotools.fncall.protocols.antml import *  # noqa: F401,F403
from echotools.fncall.protocols.antml import AntmlProtocol
from echotools.fncall.protocols.bracket import *  # noqa: F401,F403
from echotools.fncall.protocols.bracket import BracketProtocol
from echotools.fncall.protocols.custom import *  # noqa: F401,F403
from echotools.fncall.protocols.custom import CustomProtocol
from echotools.fncall.protocols.dsml import *  # noqa: F401,F403
from echotools.fncall.protocols.dsml import DsmlProtocol
from echotools.fncall.protocols.nous import *  # noqa: F401,F403
from echotools.fncall.protocols.nous import NousProtocol
from echotools.fncall.protocols.original import *  # noqa: F401,F403
from echotools.fncall.protocols.original import OriginalProtocol
from echotools.fncall.protocols.xml import *  # noqa: F401,F403
from echotools.fncall.protocols.xml import XmlProtocol

__all__ = [
    "AntmlProtocol",
    "BracketProtocol",
    "CustomProtocol",
    "DsmlProtocol",
    "NousProtocol",
    "OriginalProtocol",
    "XmlProtocol",
]
