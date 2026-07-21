"""Backward-compat alias for looppol (achecker-renamed module)."""
from __future__ import annotations

from .looppol import *  # noqa: F403
from .looppol import (  # noqa: F401
    configure_event_loop_policy,
    logger,
    os,
    sys,
)
