from __future__ import annotations

"""Custom exception types for the Qwen adapter."""


class WafBlockedError(RuntimeError):
    """Raised when the upstream returns an HTML block page instead of SSE."""
