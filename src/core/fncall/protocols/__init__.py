# src/core/fncall/protocols/__init__.py
"""协议注册。

导入时自动注册所有内置协议。
"""

from src.core.fncall.base import register_protocol


def _register_all() -> None:
    """注册所有内置协议。"""
    from src.core.fncall.protocols.xml import XmlProtocol
    from src.core.fncall.protocols.antml import AntmlProtocol
    from src.core.fncall.protocols.original import OriginalProtocol
    from src.core.fncall.protocols.bracket import BracketProtocol
    from src.core.fncall.protocols.nous import NousProtocol

    register_protocol(XmlProtocol())
    register_protocol(AntmlProtocol())
    register_protocol(OriginalProtocol())
    register_protocol(BracketProtocol())
    register_protocol(NousProtocol())
    # custom 协议按需创建，不在此注册


# 模块导入时自动注册
_register_all()

__all__ = ["_register_all"]
