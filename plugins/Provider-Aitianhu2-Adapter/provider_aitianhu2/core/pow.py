"""AItianhu2 PoW 算法模块。

提供 FNV-1a 哈希、哨兵配置构建和工作量证明求解。
"""

from __future__ import annotations

import base64
import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from .constants import USER_AGENT


def _fnv1a_hash(text: str) -> int:
    """FNV-1a 哈希算法。

    Args:
        text: 输入文本。

    Returns:
        32 位 FNV-1a 哈希值。
    """
    e = 2166136261
    for ch in text:
        e ^= ord(ch)
        e = (e * 16777619) & 0xFFFFFFFF
    e ^= e >> 16
    e = (e * 2246822507) & 0xFFFFFFFF
    e ^= e >> 13
    e = (e * 3266489909) & 0xFFFFFFFF
    e ^= e >> 16
    return e & 0xFFFFFFFF


def _fnv1a_hex(text: str) -> str:
    """返回 FNV-1a 哈希的零填充 8 字符十六进制字符串。

    Args:
        text: 输入文本。

    Returns:
        8 字符十六进制字符串。
    """
    return format(_fnv1a_hash(text), "08x")


def _encode_payload(data: List[Any]) -> str:
    """编码配置数组为 base64 字符串。

    Args:
        data: 配置数组。

    Returns:
        base64 编码字符串。
    """
    return base64.b64encode(
        json.dumps(data, separators=(",", ":")).encode("utf-8")
    ).decode("ascii")


def _build_sentinel_config(
    device_id: str,
    time_start: Optional[float] = None,
) -> List[Any]:
    """构建哨兵配置数组。

    Args:
        device_id: 设备标识。
        time_start: 起始时间戳（可选，默认当前时间）。

    Returns:
        哨兵配置数组。
    """
    if time_start is None:
        time_start = time.time()
    now = datetime.now(timezone(timedelta(hours=8)))
    return [
        "19201080", str(now), 4239654912, random.random(),
        USER_AGENT, "https://umami.aiyunos.top/script.js", "prod-9f5aa1f7b48d4577791d0e660bac1111ba132ee6",
        "zh-CN", "zh-CN,zh", random.random(),
        "createAuctionNonce\u2212function createAuctionNonce() { [native code] }",
        "location", "navigation",
        round(time.time() * 1000) % 1000000, device_id, "", 8,
        time.time() * 1000,
    ]


def _get_requirements_token(device_id: str) -> str:
    """构造 prepare 阶段的 p 值。

    Args:
        device_id: 设备标识。

    Returns:
        requirements token 字符串。
    """
    t0 = time.time()
    config = _build_sentinel_config(device_id, t0)
    config[3] = 1
    config[9] = round((time.time() - t0) * 1000)
    return "gAAAAAC" + _encode_payload(config)


def _solve_pow(
    seed: str,
    difficulty: str,
    base_config: List[Any],
    time_start: float,
    max_attempts: int = 500000,
) -> str:
    """求解工作量证明。

    Args:
        seed: PoW 种子。
        difficulty: 难度目标。
        base_config: 基础配置数组。
        time_start: 起始时间戳。
        max_attempts: 最大尝试次数。

    Returns:
        PoW 结果字符串。
    """
    config = list(base_config)
    for attempt in range(max_attempts):
        config[3] = attempt
        config[9] = round((time.time() - time_start) * 1000)
        encoded = _encode_payload(config)
        if _fnv1a_hex(seed + encoded)[: len(difficulty)] <= difficulty:
            return "gAAAAAB" + encoded + "~S"
    return "gAAAAAB" + _encode_payload(config)
