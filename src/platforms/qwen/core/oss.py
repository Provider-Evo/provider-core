"""OSS V1 签名生成（用于上传文件至 Aliyun OSS）。

本模块为纯函数；签名时不与 OSS 网络交互。
"""

from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
from typing import Dict


def build_oss_authorization(
    method: str,
    content_type: str,
    date: str,
    oss_headers: Dict[str, str],
    resource: str,
    access_key_id: str,
    access_key_secret: str,
) -> str:
    """生成 OSS V1 签名授权头。

    Args:
        method: HTTP 方法（``PUT`` / ``GET`` 等）。
        content_type: 文件 MIME 类型。
        date: RFC1123 格式日期字符串。
        oss_headers: ``x-oss-`` 前缀的自定义头字典。
        resource: 规范化资源路径（``/{bucket}/{object}``）。
        access_key_id: OSS AccessKey ID。
        access_key_secret: OSS AccessKey Secret。

    Returns:
        ``"OSS {access_key_id}:{signature}"`` 形式的授权头值。
    """
    canonicalized = ""
    if oss_headers:
        sorted_h = sorted(oss_headers.items())
        canonicalized = (
            "\n".join("{}:{}".format(k, v) for k, v in sorted_h) + "\n"
        )
    sts = "{}\n\n{}\n{}\n{}{}".format(
        method, content_type, date, canonicalized, resource
    )
    sig = base64.b64encode(
        _hmac.new(
            access_key_secret.encode(),
            sts.encode(),
            hashlib.sha1,
        ).digest()
    ).decode()
    return "OSS {}:{}".format(access_key_id, sig)
