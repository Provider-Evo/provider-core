"""base 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 base 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""


from echotools.protocol.base import *  # noqa: F401,F403
from echotools.protocol.base import (
    ToolProtocol,
    register_protocol,
    get_protocol_by_id,
    list_protocols,
    VALID_PROTOCOL_IDS,
)

try:
    from echotools.protocol.base import unregister_protocol
except ImportError:
    import echotools.protocol.base as _base

    def unregister_protocol(protocol_id: str) -> None:  # type: ignore[misc]
        registry = getattr(_base, "_PROTOCOL_REGISTRY", {})
        registry.pop(protocol_id, None)
