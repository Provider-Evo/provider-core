from __future__ import annotations

"""openaifm public facade.

Re-exports constants and pure functions from ``core/`` modules;
loads :class:`OpenaiFmAdapter` lazily via ``__getattr__``.
"""


from typing import Any

from .core.constants import (
    CAPS,
    DEFAULT_STYLE,
    DEFAULT_VOICE,
    MODELS,
    STYLES,
    STYLE_PROMPTS,
    VOICES,
)
from .core.headers import build_headers
from .core.tts import build_tts_form_data

__all__ = [
    "OpenaiFmAdapter",
    "Adapter",
    "MODELS",
    "CAPS",
    "VOICES",
    "STYLES",
    "DEFAULT_VOICE",
    "DEFAULT_STYLE",
    "STYLE_PROMPTS",
    "build_headers",
    "build_tts_form_data",
]


def __getattr__(name: str) -> Any:
    """Lazy-load :class:`OpenaiFmAdapter` on first access.

    Args:
        name: Attribute name being accessed.

    Returns:
        The requested attribute.

    Raises:
        AttributeError: If the name is not recognized.
    """
    if name == "OpenaiFmAdapter":
        from .core.adaptercore import (  # noqa: PLC0415
            OpenaiFmAdapter as _OpenaiFmAdapter,
        )

        return _OpenaiFmAdapter
    if name == "Adapter":
        from .core.adaptercore import (  # noqa: PLC0415
            OpenaiFmAdapter as _Adapter,
        )

        return _Adapter
    raise AttributeError(
        "module {!r} has no attribute {!r}".format(__name__, name)
    )
