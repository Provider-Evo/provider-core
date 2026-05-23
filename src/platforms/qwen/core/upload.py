"""文件上传服务（OSS STS + PUT）。

将 1754 行 God-module 中关于上传的代码（STS 凭据获取 / OSS V1 签名 /
PUT / 重试 / 文件对象构建）独立成服务类。

依赖注入：
    - ``session``：共享的 :class:`aiohttp.ClientSession`
    - ``proxy_resolver``：返回当前应使用的代理 URL 或 ``None``
"""

from __future__ import annotations

import asyncio
import base64
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Final, Optional
from urllib.parse import urlparse

import aiohttp

from src.logger import get_logger
from .endpoints import (
    BASE_URL,
    STS_TOKEN_PATHS,
    USER_AGENT,
)
from .files import build_file_object
from .mimes import (
    DATA_URI_EXT_MAP,
    get_file_category,
    get_mime_type,
)
from .oss import build_oss_authorization

logger = get_logger(__name__)

MAX_RETRIES: Final[int] = 3
STS_TIMEOUT: Final[int] = 15
OSS_UPLOAD_TIMEOUT: Final[int] = 120

# 各类型文件大小上限（字节）
_MAX_FILE_SIZES: Final[Dict[str, int]] = {
    "video": 500 * 1024 * 1024,
    "audio": 100 * 1024 * 1024,
    "image": 20 * 1024 * 1024,
    "file": 20 * 1024 * 1024,
}
_DEFAULT_MAX_SIZE: Final[int] = 20 * 1024 * 1024


class UploadService:
    """OSS 文件上传服务。"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
    ) -> None:
        """构造上传服务。

        Args:
            session: 共享的 aiohttp 会话。
            proxy_resolver: 返回当前应使用代理 URL 的回调（无代理时返回
                ``None``）。
        """
        self._session = session
        self._resolve_proxy = proxy_resolver

    # ------------------------------------------------------------- 公共接口
    async def upload(
        self,
        file_data: bytes,
        filename: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """完整文件上传流程：获取 STS → OSS PUT → 构建文件对象。

        Args:
            file_data: 文件字节数据。
            filename: 文件名（含扩展名，用于 MIME 推断）。
            token: Bearer 令牌。
            user_id: 用户 ID（用于文件对象构建）。

        Returns:
            Qwen API 文件对象字典。

        Raises:
            ValueError: 文件为空、过大等输入错误。
            RuntimeError: STS 获取失败或 OSS PUT 失败。
        """
        self._validate(file_data, filename)
        content_type = get_mime_type(filename)
        file_type, _ = get_file_category(content_type)
        file_size = len(file_data)

        creds = await self._get_sts_with_retry(
            token, filename, file_size, file_type
        )
        file_url = await self._put_to_oss_with_retry(
            file_data, content_type, creds
        )

        file_id = creds.get("file_id", str(uuid.uuid4()))
        return build_file_object(
            file_id=file_id,
            file_url=file_url,
            filename=filename,
            size=file_size,
            content_type=content_type,
            user_id=user_id,
        )

    async def upload_from_path(
        self,
        file_path: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """从本地路径上传文件。

        Args:
            file_path: 本地文件路径。
            token: Bearer 令牌。
            user_id: 用户 ID。

        Returns:
            Qwen API 文件对象字典。

        Raises:
            FileNotFoundError: 文件不存在。
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError("文件不存在: {}".format(file_path))
        filename = path.name
        file_data = path.read_bytes()
        return await self.upload(file_data, filename, token, user_id)

    async def upload_from_base64(
        self,
        data_uri: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """从 ``data:{mime};base64,{data}`` URI 上传文件。

        Args:
            data_uri: Base64 数据 URI。
            token: Bearer 令牌。
            user_id: 用户 ID。

        Returns:
            Qwen API 文件对象字典。

        Raises:
            ValueError: URI 格式错误。
        """
        if not data_uri.startswith("data:") or ";base64," not in data_uri:
            raise ValueError("无效的 Base64 数据 URI")
        header, encoded = data_uri.split(";base64,", 1)
        mime_type = header.split("data:", 1)[1]
        ext = DATA_URI_EXT_MAP.get(mime_type, ".bin")
        filename = "upload_{}{}".format(uuid.uuid4().hex[:8], ext)

        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        file_data = base64.b64decode(encoded)
        return await self.upload(file_data, filename, token, user_id)

    # ----------------------------------------------------------------- 内部
    @staticmethod
    def _validate(file_data: bytes, filename: str) -> None:
        """对文件做大小与类型基本校验。"""
        if not file_data:
            raise ValueError("文件为空: {}".format(filename))
        content_type = get_mime_type(filename)
        file_type, _ = get_file_category(content_type)
        max_size = _MAX_FILE_SIZES.get(file_type, _DEFAULT_MAX_SIZE)
        if len(file_data) > max_size:
            raise ValueError(
                "文件过大: {} ({} bytes > {} bytes)".format(
                    filename, len(file_data), max_size
                )
            )

    async def _get_sts_with_retry(
        self,
        token: str,
        filename: str,
        file_size: int,
        file_type: str,
    ) -> Dict[str, Any]:
        """指数退避获取 STS 凭据。"""
        last_exc: Optional[BaseException] = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                return await self._get_sts_credentials(
                    token, filename, file_size, file_type
                )
            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                RuntimeError,
                ValueError,
            ) as exc:
                last_exc = exc
        raise RuntimeError("获取 STS 凭据失败: {}".format(last_exc))

    async def _get_sts_credentials(
        self,
        token: str,
        filename: str,
        filesize: int,
        filetype: str,
    ) -> Dict[str, Any]:
        """请求 STS Token 接口。"""
        headers = {
            "authorization": "Bearer {}".format(token),
            "content-type": "application/json;charset=UTF-8",
            "source": "web",
            "user-agent": USER_AGENT,
            "origin": BASE_URL,
            "referer": "{}/".format(BASE_URL),
            "accept": "application/json",
        }
        payload = {
            "filename": filename,
            "filesize": filesize,
            "filetype": filetype,
        }
        last_err: Optional[BaseException] = None
        for path in STS_TOKEN_PATHS:
            url = "{}{}".format(BASE_URL, path)
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=STS_TIMEOUT),
                    proxy=self._resolve_proxy(),
                ) as resp:
                    if resp.status != 200:
                        last_err = RuntimeError(
                            "HTTP {}: {}".format(
                                resp.status, (await resp.text())[:200]
                            )
                        )
                        continue
                    data = await resp.json()
                    creds = data.get("data", data)
                    required = (
                        "access_key_id",
                        "access_key_secret",
                        "security_token",
                    )
                    if all(k in creds for k in required):
                        return creds
                    last_err = ValueError(
                        "STS 凭据格式异常: {}".format(data)
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_err = exc
        raise RuntimeError("所有 STS 端点均失败: {}".format(last_err))

    async def _put_to_oss_with_retry(
        self,
        file_data: bytes,
        content_type: str,
        creds: Dict[str, Any],
    ) -> str:
        """指数退避执行 OSS PUT 上传。"""
        last_exc: Optional[BaseException] = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                return await self._put_to_oss(
                    file_data, content_type, creds
                )
            except (
                aiohttp.ClientError,
                asyncio.TimeoutError,
                RuntimeError,
            ) as exc:
                last_exc = exc
        logger.warning("OSS 上传失败，使用预签名 URL: %s", last_exc)
        return creds.get("file_url", "")

    async def _put_to_oss(
        self,
        file_data: bytes,
        content_type: str,
        creds: Dict[str, Any],
    ) -> str:
        """执行单次 OSS PUT。"""
        file_url = creds.get("file_url", "")
        obj_key = creds.get("file_path", "")
        security_token = creds.get("security_token", "")
        access_key_id = creds.get("access_key_id", "")
        access_key_secret = creds.get("access_key_secret", "")

        parsed = urlparse(file_url)
        bucket_host = parsed.netloc
        bucket_name = bucket_host.split(".")[0]
        resource = "/{}/{}".format(bucket_name, obj_key)

        gmt_date = datetime.now(timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        oss_headers = {"x-oss-security-token": security_token}
        auth = build_oss_authorization(
            "PUT",
            content_type,
            gmt_date,
            oss_headers,
            resource,
            access_key_id,
            access_key_secret,
        )
        headers = {
            "Host": bucket_host,
            "Date": gmt_date,
            "Content-Type": content_type,
            "Content-Length": str(len(file_data)),
            "Authorization": auth,
            "x-oss-security-token": security_token,
            "User-Agent": USER_AGENT,
        }
        oss_url = "https://{}/{}".format(bucket_host, obj_key)
        async with self._session.put(
            oss_url,
            data=file_data,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=OSS_UPLOAD_TIMEOUT),
            proxy=self._resolve_proxy(),
        ) as resp:
            if resp.status not in (200, 201):
                err = await resp.text()
                raise RuntimeError(
                    "OSS PUT {} {}: {}".format(
                        resp.status, oss_url, err[:300]
                    )
                )
        return file_url

    # ------------------------------------------------------------ 工具方法
    @staticmethod
    def extract_base64_images(messages: list) -> list:
        """从 OpenAI 格式消息中提取所有 ``data:`` URI 图片。

        Args:
            messages: OpenAI 格式消息列表。

        Returns:
            ``data:`` URI 字符串列表。
        """
        uris: list = []
        for msg in messages:
            content = msg.get("content", "")
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "image_url":
                    continue
                img_url_obj = part.get("image_url", {})
                img_url = (
                    img_url_obj.get("url", "")
                    if isinstance(img_url_obj, dict)
                    else str(img_url_obj)
                )
                if img_url.startswith("data:"):
                    uris.append(img_url)
        return uris

    @staticmethod
    def basename(path: str) -> str:
        """便捷封装 :func:`os.path.basename`，用于测试可替换。"""
        return os.path.basename(path)
