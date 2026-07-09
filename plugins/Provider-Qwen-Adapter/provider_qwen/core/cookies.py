from __future__ import annotations

"""Lightweight cookie-generation compatibility helpers.

This module exists to preserve legacy import surfaces used by the original
Qwen adapter layout. The current protocol no longer depends on the old
SSXMOD cookie scheme for core requests, but callers may still import these
symbols through ``shared.py``.
"""

from typing import Any, Dict, Final

HASH_FIELDS: Final[list] = [
    "ssxmod_itna",
    "ssxmod_itna2",
    "bx-umidtoken",
    "bx-ua",
]


def generate_cookies(fingerprint: str) -> Dict[str, Any]:
    """Return a compatibility cookie mapping.

    The modern Qwen flow can operate without the old SSXMOD cookies, but the
    adapter preserves these keys so legacy code paths do not break.
    """
    return {
        "ssxmod_itna": "",
        "ssxmod_itna2": "",
        "fingerprint": fingerprint,
    }
