from __future__ import annotations

# Qwen core cryptographic functions (signing, hashing, LZW compression)

import base64
import hashlib
import hmac as _hmac
import json
import secrets
import time
from typing import Any, Callable, Dict, Final, List, Optional, Tuple

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from src.platforms.qwen.core.endpoints import (
    BXUA_VERSION,
    CUSTOM_BASE64_CHARS,
    HASH_FIELDS,
)

# =============================================================================
# LZW compression + custom encoding
# =============================================================================
def lzw_compress(
    data: str,
    bits: int,
    char_func: Callable[[int], str],
) -> str:
    """执行 LZW 压缩。

    Args:
        data: 待压缩字符串。
        bits: 每个字符的位数。
        char_func: 索引到字符的映射函数。

    Returns:
        压缩后的字符串。
    """
    if not data:
        return ""

    dictionary: Dict[str, int] = {}
    dict_to_create: Dict[str, bool] = {}
    w: str = ""
    enlarge_in: int = 2
    dict_size: int = 3
    num_bits: int = 2
    result: List[str] = []
    val: int = 0
    pos: int = 0

    def _write(v: int, p: int, code: int, bc: int) -> Tuple[int, int]:
        for _ in range(bc):
            v = (v << 1) | (code & 1)
            if p == bits - 1:
                p = 0
                result.append(char_func(v))
                v = 0
            else:
                p += 1
            code >>= 1
        return v, p

    def _zeros(v: int, p: int, count: int) -> Tuple[int, int]:
        for _ in range(count):
            v <<= 1
            if p == bits - 1:
                p = 0
                result.append(char_func(v))
                v = 0
            else:
                p += 1
        return v, p

    def _new_char(v: int, p: int, ch: str, nb: int) -> Tuple[int, int]:
        cp = ord(ch)
        if cp < 256:
            v, p = _zeros(v, p, nb)
            v, p = _write(v, p, cp, 8)
        else:
            marker = 1
            for _ in range(nb):
                v = (v << 1) | marker
                if p == bits - 1:
                    p = 0
                    result.append(char_func(v))
                    v = 0
                else:
                    p += 1
                marker = 0
            v, p = _write(v, p, cp, 16)
        return v, p

    for c in data:
        if c not in dictionary:
            dictionary[c] = dict_size
            dict_size += 1
            dict_to_create[c] = True
        wc = w + c
        if wc in dictionary:
            w = wc
        else:
            if w in dict_to_create:
                val, pos = _new_char(val, pos, w[0], num_bits)
                enlarge_in -= 1
                if enlarge_in == 0:
                    enlarge_in = 2 ** num_bits
                    num_bits += 1
                del dict_to_create[w]
            else:
                val, pos = _write(val, pos, dictionary[w], num_bits)
                enlarge_in -= 1
                if enlarge_in == 0:
                    enlarge_in = 2 ** num_bits
                    num_bits += 1
            dictionary[wc] = dict_size
            dict_size += 1
            w = c

    if w:
        if w in dict_to_create:
            val, pos = _new_char(val, pos, w[0], num_bits)
            enlarge_in -= 1
            if enlarge_in == 0:
                enlarge_in = 2 ** num_bits
                num_bits += 1
            del dict_to_create[w]
        else:
            val, pos = _write(val, pos, dictionary[w], num_bits)
            enlarge_in -= 1
            if enlarge_in == 0:
                enlarge_in = 2 ** num_bits
                num_bits += 1

    val, pos = _write(val, pos, 2, num_bits)
    while True:
        val <<= 1
        if pos == bits - 1:
            result.append(char_func(val))
            break
        pos += 1

    return "".join(result)


def custom_encode(data: str, url_safe: bool = True) -> str:
    """使用自定义字符集编码数据。

    Args:
        data: 待编码字符串。
        url_safe: 是否 URL 安全模式。

    Returns:
        编码后的字符串。
    """
    if not data:
        return ""
    cs = CUSTOM_BASE64_CHARS
    compressed = lzw_compress(data, 6, lambda idx: cs[idx])
    if not url_safe:
        rem = len(compressed) % 4
        padding_map = {1: "===", 2: "==", 3: "="}
        compressed += padding_map.get(rem, "")
    return compressed


# =============================================================================
# Fingerprint generation
# =============================================================================
def generate_device_id() -> str:
    """生成 20 字符十六进制设备 ID。

    Returns:
        设备 ID 字符串。
    """
    return "".join(
        secrets.choice("0123456789abcdef") for _ in range(20)
    )


def _generate_hash() -> int:
    """生成随机 32 位哈希值。

    Returns:
        随机无符号 32 位整数。
    """
    return secrets.randbelow(0x100000000)


def generate_fingerprint(device_id: Optional[str] = None) -> str:
    """生成浏览器指纹字符串（随机数+时间戳副作用）。
    注意：此函数涉及随机数生成(_generate_hash())和time.time()时间戳。
    在client.py的init()中调用并存储（_fp），用于后续请求头生成。

    Args:
        device_id: 设备 ID，为 None 则自动生成。

    Returns:
        以 ^ 分隔的 37 字段指纹字符串。
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
        "5|{}".format(_generate_hash()),
        str(_generate_hash()),
        str(_generate_hash()),
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
        str(_generate_hash()),
        "11",
        str(current_timestamp),
        str(_generate_hash()),
        "0",
        str(secrets.randbelow(91) + 10),
    ]
    return "^".join(fields)


# =============================================================================
# Cookie generation
# =============================================================================
def _process_fingerprint_fields(fields: List[str]) -> List[str]:
    """处理指纹字段用于 Cookie 生成。

    Args:
        fields: 指纹字段列表。

    Returns:
        处理后的字段列表。
    """
    processed = list(fields)
    ts_now = int(time.time() * 1000)
    for idx, ft in HASH_FIELDS.items():
        if idx >= len(processed):
            continue
        if ft == "split":
            parts = processed[idx].split("|")
            if len(parts) == 2:
                processed[idx] = "{}|{}".format(parts[0], _generate_hash())
        elif ft == "full":
            if idx == 36:
                processed[idx] = str(secrets.randbelow(91) + 10)
            else:
                processed[idx] = str(_generate_hash())
    if 33 < len(processed):
        processed[33] = str(ts_now)
    return processed


def generate_cookies(
    fingerprint: Optional[str] = None,
) -> Dict[str, Any]:
    """生成 SSXMOD Cookie 字典（随机数+时间戳副作用）。

    注意：此函数涉及随机数生成(_generate_hash())和time.time()时间戳。
    在client.py的init()中调用并存储(_cookies)，用于后续请求。

    Args:
        fingerprint: 指纹字符串，为 None 则自动生成。

    Returns:
        包含 ssxmod_itna、ssxmod_itna2、timestamp 的字典。
    """
    fp_data = fingerprint or generate_fingerprint()
    fields = fp_data.split("^")
    processed = _process_fingerprint_fields(fields)

    itna_data = "^".join(processed)
    ssxmod_itna = "1-" + custom_encode(itna_data, url_safe=True)

    itna2_fields = [
        processed[0], processed[1], processed[23], "0",
        "", "0", "", "", "0", "0", "0",
        processed[32], processed[33], "0", "0", "0", "0", "0",
    ]
    itna2_data = "^".join(itna2_fields)
    ssxmod_itna2 = "1-" + custom_encode(itna2_data, url_safe=True)

    timestamp = int(processed[33])
    return {
        "ssxmod_itna": ssxmod_itna,
        "ssxmod_itna2": ssxmod_itna2,
        "timestamp": timestamp,
    }


# =============================================================================
# BX-UA generation
# =============================================================================
def _derive_key_iv(seed: str) -> Tuple[bytes, bytes]:
    """从种子派生 AES-CBC 密钥和 IV。

    Args:
        seed: 种子字符串。

    Returns:
        (key, iv) 各 16 字节。
    """
    digest = hashlib.sha256(seed.encode()).digest()
    return digest[:16], digest[16:32]


def _encrypt_aes_cbc(data: bytes, key: bytes, iv: bytes) -> bytes:
    """AES-CBC 加密并填充。

    Args:
        data: 待加密数据。
        key: 16 字节密钥。
        iv: 16 字节初始化向量。

    Returns:
        加密后的字节数据。
    """
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(data, AES.block_size))


def generate_bxua(
    fingerprint: str,
    version: str = BXUA_VERSION,
    timestamp: Optional[int] = None,
    seed: Optional[str] = None,
) -> str:
    """生成 bx-ua 请求头值。

    Args:
        fingerprint: 指纹字符串。
        version: BX-UA 版本号。
        timestamp: 毫秒时间戳，为 None 则用当前时间。
        seed: 加密种子，为 None 则用指纹本身。

    Returns:
        格式为 "version!base64_encrypted" 的字符串。
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


# =============================================================================
# Password hashing
# =============================================================================
def hash_password(password: str) -> str:
    """SHA-256 哈希密码。

    Args:
        password: 原始密码。

    Returns:
        十六进制哈希字符串。
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()
