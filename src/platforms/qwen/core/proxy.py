from __future__ import annotations

"""Proxy override state holder."""

from typing import Optional


class ProxyState:
    """Track whether proxy use is forced on, forced off, or inherited."""

    def __init__(self) -> None:
        self.override: Optional[bool] = None

    def set_enabled(self, enabled: bool) -> None:
        """Force proxy on or off."""
        self.override = bool(enabled)

    def load(self, override: Optional[bool]) -> None:
        """Restore the persisted override state."""
        self.override = override

    def is_enabled(self) -> bool:
        """Return whether proxy is currently forced on."""
        return bool(self.override)

    def to_dict(self) -> dict:
        """Serialize the state for persistence."""
        return {"enabled": self.override}
