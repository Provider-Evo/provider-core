"""``bx-ua`` 请求头生成（AES-CBC + Base64）。

通过 PyCryptodome 完成对称加密；本模块本身无 I/O。
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from .endpoints import BXUA_VERSION


def _derive_key_iv(seed: str) -> Tuple[bytes, bytes]:
    """从种子派生 16 字节 AES-CBC 密钥与 IV。

    Args:
        seed: 种子字符串。

    Returns:
        ``(key, iv)`` 二元组。
    """
    digest = hashlib.sha256(seed.encode()).digest()
    return digest[:16], digest[16:32]


def _encrypt_aes_cbc(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CBC 加密并按块大小填充。"""
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, AES.block_size))


def generate_bxua(
    fingerprint: str,
    version: str = BXUA_VERSION,
    timestamp: Optional[int] = None,
    seed: Optional[str] = None,
) -> str:
    """生成 ``bx-ua`` 请求头值。

    Args:
        fingerprint: 指纹字符串（必填）。
        version: BX-UA 版本号。
        timestamp: 毫秒时间戳；``None`` 表示当前时间。
        seed: 加密种子；``None`` 表示复用指纹本身。

    Returns:
        ``"<version>!<base64_encrypted>"`` 形式的字符串。
    """
    ts = timestamp or int(time.time() * 1000)
    fields = fingerprint.split("^")
    rnd = secrets.randbelow(9000) + 1000

    cs_input = "{}{}{}".format(fingerprint, ts, rnd)
    cs = hashlib.md5(cs_input.encode()).hexdigest()[:8]

    payload_dict: Dict[str, Any] = {
        "v": version,
        "ts": ts,
        "fp": fingerprint,
        "d": {
            "deviceId": fields[0] if len(fields) > 0 else "",
            "sdkVer": fields[1] if len(fields) > 1 else "",
            "lang": fields[5] if len(fields) > 5 else "",
            "tz": fields[6] if len(fields) > 6 else "",
            "platform": fields[10] if len(fields) > 10 else "",
            "renderer": fields[12] if len(fields) > 12 else "",
            "mode": fields[23] if len(fields) > 23 else "",
            "vendor": fields[28] if len(fields) > 28 else "",
        },
        "rnd": rnd,
        "seq": 1,
        "cs": cs,
    }
    payload_bytes = json.dumps(
        payload_dict, separators=(",", ":")
    ).encode()
    key, iv = _derive_key_iv(seed or fingerprint)
    encrypted = _encrypt_aes_cbc(payload_bytes, key, iv)
    encoded = base64.b64encode(encrypted).decode("ascii")
    return "{}!{}".format(version, encoded)
