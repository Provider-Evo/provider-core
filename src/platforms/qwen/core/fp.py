"""浏览器指纹生成。

仅产出字符串；不写入任何状态。但内部依赖
:func:`time.time` 与 :func:`secrets.randbelow`，因此结果不可复现，
调用方需要自行缓存（典型场景：客户端 ``init`` 一次后存入 ``_fp``）。
"""

from __future__ import annotations

import secrets
import time
from typing import List, Optional


def generate_device_id() -> str:
    """生成 20 字符十六进制设备 ID。

    Returns:
        20 字符的小写十六进制字符串。
    """
    return "".join(secrets.choice("0123456789abcdef") for _ in range(20))


def generate_hash() -> int:
    """生成随机 32 位无符号整数。

    Returns:
        ``[0, 2**32)`` 区间内的随机整数。
    """
    return secrets.randbelow(0x100000000)


def generate_fingerprint(device_id: Optional[str] = None) -> str:
    """生成浏览器指纹字符串。

    Args:
        device_id: 设备 ID，``None`` 表示自动生成。

    Returns:
        以 ``^`` 分隔的 37 字段指纹字符串。

    .. note::
        本函数有 **非确定性**：返回值依赖随机数与当前时间。
    """
    did = device_id or generate_device_id()
    current_timestamp = int(time.time() * 1000)
    fields: List[str] = [
        did,
        "websdk-2.3.15d",
        "1765348410850",
        "91",
        "1|15",
        "zh-CN",
        "-480",
        "16705151|12791",
        "1470|956|283|797|158|0|1470|956|1470|798|0|0",
        "5",
        "MacIntel",
        "10",
        (
            "ANGLE (Apple, ANGLE Metal Renderer: Apple M4, "
            "Unspecified Version)|Google Inc. (Apple)"
        ),
        "30|30",
        "0",
        "28",
        "5|{}".format(generate_hash()),
        str(generate_hash()),
        str(generate_hash()),
        "1",
        "0",
        "1",
        "0",
        "P",
        "0",
        "0",
        "0",
        "416",
        "Google Inc.",
        "8",
        "-1|0|0|0|0",
        str(generate_hash()),
        "11",
        str(current_timestamp),
        str(generate_hash()),
        "0",
        str(secrets.randbelow(91) + 10),
    ]
    return "^".join(fields)
