"""Cookie 生成（``ssxmod_itna`` / ``ssxmod_itna2``）。

依赖 :mod:`.fp` 与 :mod:`.lzw`；本身无 I/O。
"""

from __future__ import annotations

import secrets
import time
from typing import Any, Dict, Final, List, Optional

from .fp import (
    generate_fingerprint,
    generate_hash,
)
from .lzw import custom_encode

# ---------------------------------------------------------------------------
# 指纹字段处理规则：索引 -> 处理类型（"split" 或 "full"）
# ---------------------------------------------------------------------------
HASH_FIELDS: Final[Dict[int, str]] = {
    16: "split",
    17: "full",
    18: "full",
    31: "full",
    34: "full",
    36: "full",
}


def _process_fingerprint_fields(fields: List[str]) -> List[str]:
    """处理指纹字段用于 Cookie 生成（返回新列表，不修改输入）。"""
    processed = list(fields)
    ts_now = int(time.time() * 1000)
    for idx, ft in HASH_FIELDS.items():
        if idx >= len(processed):
            continue
        if ft == "split":
            parts = processed[idx].split("|")
            if len(parts) == 2:
                processed[idx] = "{}|{}".format(parts[0], generate_hash())
        elif ft == "full":
            if idx == 36:
                processed[idx] = str(secrets.randbelow(91) + 10)
            else:
                processed[idx] = str(generate_hash())
    if 33 < len(processed):
        processed[33] = str(ts_now)
    return processed


def generate_cookies(fingerprint: Optional[str] = None) -> Dict[str, Any]:
    """生成 SSXMOD Cookie 字典。

    Args:
        fingerprint: 指纹字符串；``None`` 表示自动生成。

    Returns:
        含 ``ssxmod_itna`` / ``ssxmod_itna2`` / ``timestamp`` 的字典。

    .. note::
        与 :func:`.fingerprint.generate_fingerprint` 同样具有非确定性。
    """
    fp_data = fingerprint or generate_fingerprint()
    fields = fp_data.split("^")
    processed = _process_fingerprint_fields(fields)

    itna_data = "^".join(processed)
    ssxmod_itna = "1-" + custom_encode(itna_data, url_safe=True)

    itna2_fields = [
        processed[0],
        processed[1],
        processed[23],
        "0",
        "",
        "0",
        "",
        "",
        "0",
        "0",
        "0",
        processed[32],
        processed[33],
        "0",
        "0",
        "0",
        "0",
        "0",
    ]
    itna2_data = "^".join(itna2_fields)
    ssxmod_itna2 = "1-" + custom_encode(itna2_data, url_safe=True)

    timestamp = int(processed[33])
    return {
        "ssxmod_itna": ssxmod_itna,
        "ssxmod_itna2": ssxmod_itna2,
        "timestamp": timestamp,
    }
