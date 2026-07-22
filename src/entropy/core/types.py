from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from src.routes.shared.thinking import ThinkingConfig

OutputBlockType = Literal["text", "thinking", "tool_call", "tool_result"]


@dataclass
class OutputBlock:
    type: OutputBlockType
    text: Optional[str] = None
    thinking: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None


@dataclass
class TurnRequest:
    model: str
    input: List[Dict[str, Any]]
    tools: Optional[List[Dict[str, Any]]] = None
    thinking: Optional[ThinkingConfig] = None
    stream: bool = False
    max_output_tokens: Optional[int] = None
    stop: Optional[List[str]] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    search: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    protocol_id: str = ""
    platform: str = ""
    tool_choice: Any = None
    upload_files: Optional[List[Any]] = None


@dataclass
class TurnResponse:
    output: List[OutputBlock] = field(default_factory=list)
    usage: Optional[Dict[str, Any]] = None
    platform_id: str = ""
    model: str = ""
    raw_text: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
