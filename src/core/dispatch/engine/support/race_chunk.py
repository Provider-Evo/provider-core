"""竞速 chunk 事件解析 — 从 race_worker 拆出以满足行数约束。"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional


def race_chunk_winner_if_ready(
    info: Dict[str, Any], min_tok: int
) -> Optional[Dict[str, Any]]:
    if info["tok"] >= min_tok:
        return info
    return None


def apply_race_chunk_event(
    info: Dict[str, Any], data: Any, min_tok: int
) -> Optional[Dict[str, Any]]:
    info["buf"].append(data)
    if isinstance(data, str):
        info["tok"] += 1
        info["acc_len"] += len(data)
        if info["ft"] is None:
            info["ft"] = time.monotonic()
        return race_chunk_winner_if_ready(info, min_tok)
    if isinstance(data, dict):
        if "usage" in data:
            info["usage"] = data["usage"]
        elif data.get("thinking"):
            info["acc_len"] += len(str(data["thinking"]))
        return race_chunk_winner_if_ready(info, min_tok)
    return None
