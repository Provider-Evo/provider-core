
from echotools.protocol.base import *  # noqa: F401,F403
from echotools.protocol.base import (
    VALID_PROTOCOL_IDS,
    ToolProtocol,
    get_protocol_by_id,
    list_protocols,
    register_protocol,
)

try:
    from echotools.protocol.base import unregister_protocol
except ImportError:
    import echotools.protocol.base as _base

    def unregister_protocol(protocol_id: str) -> None:  # type: ignore[misc]
        registry = getattr(_base, "_PROTOCOL_REGISTRY", {})
        registry.pop(protocol_id, None)
