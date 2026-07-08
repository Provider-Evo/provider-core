from __future__ import annotations
"""Base exception class: ProviderError."""

from typing import Any, Dict, Optional

__all__ = ["ProviderError"]

_ERROR_TYPE_MAP: Dict[type, str] = {}


def _error_type_name(cls: type) -> str:
    """Derive a snake_case error type name from the class name."""
    name = cls.__name__
    result = [name[0].lower()]
    for ch in name[1:]:
        if ch.isupper():
            result.append("_")
            result.append(ch.lower())
        else:
            result.append(ch)
    return "".join(result)


class ProviderError(Exception):
    """Base gateway exception. Root of the Provider-V2 error hierarchy."""

    def __init__(
        self,
        message: str,
        original: Optional[Exception] = None,
        status_code: int = 500,
    ) -> None:
        super().__init__(message)
        self.original = original
        self.status_code = status_code

    @property
    def error_type(self) -> str:
        """Return the snake_case error type name."""
        cls = type(self)
        if cls not in _ERROR_TYPE_MAP:
            _ERROR_TYPE_MAP[cls] = _error_type_name(cls)
        return _ERROR_TYPE_MAP[cls]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error to a JSON-compatible dictionary.

        Returns:
            ``{"error": {"type": ..., "message": ..., "status_code": ...}}``
        """
        return {
            "error": {
                "type": self.error_type,
                "message": str(self),
                "status_code": self.status_code,
            }
        }
