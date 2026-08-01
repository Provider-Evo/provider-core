"""Shared XML utilities for fncall protocols."""

from __future__ import annotations

from echotools.exec.fncall.shared.loop_detect import (
    _PROVIDER_BLOCK_RE,
    _PROVIDER_INVOKE_RE,
    _PROVIDER_PARAM_RE,
    escape_xml_attr,
    extract_cdata,
)

_PROVIDER_START = "<|PROVIDER|tool_calls>"
_PROVIDER_END = "</|PROVIDER|tool_calls>"

__all__ = [
    "_PROVIDER_BLOCK_RE",
    "_PROVIDER_END",
    "_PROVIDER_INVOKE_RE",
    "_PROVIDER_PARAM_RE",
    "_PROVIDER_START",
    "escape_xml_attr",
    "extract_cdata",
]
