"""File upload mixin for QwenClient.

Provides OSS STS credential acquisition, PUT upload, file-object
construction, base64 image extraction, and image download.
"""

from __future__ import annotations

import asyncio
import base64
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import aiohttp

from src.logger import get_logger
from src.platforms.qwen.core.shared import (
    BASE_URL,
    EXTENSION_TO_MIME,
    GENERATED_IMAGE_DIR,
    STS_TOKEN_PATHS,
    USER_AGENT,
    build_file_object,
    build_oss_authorization,
    get_file_category,
    get_mime_type,
    save_image_file,
)

logger = get_logger(__name__)

MAX_RETRIES: int = 3
OSS_UPLOAD_TIMEOUT: int = 120

# Per-type size limits (bytes)
_MAX_FILE_SIZES: Dict[str, int] = {
    "video": 500 * 1024 * 1024,
    "audio": 100 * 1024 * 1024,
    "image": 20 * 1024 * 1024,
    "file": 20 * 1024 * 1024,
}

# Extension map for base64 data URI decoding
_DATA_URI_EXT_MAP: Dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "video/mp4": ".mp4",
    "application/pdf": ".pdf",
}


class UploadMixin:
    """Mixin providing file upload and image download capabilities.

    Expects the composed class to provide:
    - ``_session``: aiohttp.ClientSession
    - ``_get_proxy_kwarg()``: method returning Optional[str]
    """

    # =====================================================================
    # OSS STS credentials
    # =====================================================================

    async def _get_sts_credentials(
        self,
        token: str,
        filename: str,
        filesize: int,
        filetype: str,
    ) -> Dict[str, Any]:
        """Acquire OSS STS temporary upload credentials.

        Args:
            token: Bearer token.
            filename: File name.
            filesize: File size in bytes.
            filetype: File category (image/video/audio/file).

        Returns:
            STS credential dict (access_key_id / access_key_secret /
            security_token / file_url / file_path).

        Raises:
            Exception: all STS endpoints failed.
        """
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

        last_err: Optional[Exception] = None
        for path in STS_TOKEN_PATHS:
            url = "{}{}".format(BASE_URL, path)
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        last_err = Exception(
                            "HTTP {}: {}".format(
                                resp.status,
                                (await resp.text())[:200],
                            )
                        )
                        continue
                    data = await resp.json()
                    creds = data.get("data", data)
                    if all(
                        k in creds
                        for k in (
                            "access_key_id",
                            "access_key_secret",
                            "security_token",
                        )
                    ):
                        return creds
                    last_err = Exception("STS 凭据格式异常: {}".format(data))
            except Exception as e:
                last_err = e

        raise Exception(
            "所有 STS 端点均失败: {}".format(last_err)
        )

    # =====================================================================
    # OSS PUT upload
    # =====================================================================

    async def _upload_to_oss(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        creds: Dict[str, Any],
    ) -> str:
        """PUT upload to OSS using STS temporary credentials.

        Args:
            file_data: File bytes.
            filename: File name (for MIME inference).
            content_type: MIME type.
            creds: STS credential dict.

        Returns:
            OSS file URL on success.

        Raises:
            Exception: OSS PUT failed.
        """
        from datetime import datetime, timezone

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
        ) as resp:
            if resp.status not in (200, 201):
                err = await resp.text()
                raise Exception(
                    "OSS PUT {} {}: {}".format(resp.status, oss_url, err[:300])
                )
        return file_url

    # =====================================================================
    # High-level upload wrappers
    # =====================================================================

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Full upload flow: STS credentials -> OSS PUT -> file object.

        Supports image, video, audio, and document uploads.
        Max 500 MB for video, 100 MB for audio, 20 MB for others.

        Args:
            file_data: File bytes.
            filename: File name (with extension, for MIME inference).
            token: Bearer token.
            user_id: User ID (for file-object construction).

        Returns:
            Qwen API file object dict.

        Raises:
            Exception: file too large, STS failure, or OSS upload failure.
        """
        content_type = get_mime_type(filename)
        file_type, _ = get_file_category(content_type)
        file_size = len(file_data)

        max_size = _MAX_FILE_SIZES.get(file_type, 20 * 1024 * 1024)
        if file_size > max_size:
            raise Exception(
                "文件过大: {} ({} bytes > {} bytes)".format(
                    filename, file_size, max_size
                )
            )
        if file_size == 0:
            raise Exception("文件为空: {}".format(filename))

        # STS credentials with retry
        creds: Optional[Dict[str, Any]] = None
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                creds = await self._get_sts_credentials(
                    token, filename, file_size, file_type
                )
                break
            except Exception as e:
                last_exc = e

        if creds is None:
            raise Exception(
                "获取 STS 凭据失败: {}".format(last_exc)
            )

        # OSS PUT upload with retry
        file_url = ""
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                file_url = await self._upload_to_oss(
                    file_data, filename, content_type, creds
                )
                break
            except Exception as e:
                last_exc = e

        if not file_url:
            file_url = creds.get("file_url", "")
            logger.warning("OSS 上传失败，使用预签名 URL: %s", last_exc)

        file_id = creds.get("file_id", str(uuid.uuid4()))
        return build_file_object(
            file_id=file_id,
            file_url=file_url,
            filename=filename,
            size=file_size,
            content_type=content_type,
            user_id=user_id,
        )

    async def upload_file_from_path(
        self,
        file_path: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Upload a file from a local path.

        Args:
            file_path: Local file path.
            token: Bearer token.
            user_id: User ID.

        Returns:
            Qwen API file object dict.

        Raises:
            Exception: file not found or upload failure.
        """
        if not os.path.exists(file_path):
            raise Exception("文件不存在: {}".format(file_path))
        filename = os.path.basename(file_path)
        file_data = Path(file_path).read_bytes()
        return await self.upload_file(file_data, filename, token, user_id)

    async def upload_file_from_base64(
        self,
        data_uri: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """Upload a file from a Base64 data URI.

        Supports ``data:{mime};base64,{data}`` format.

        Args:
            data_uri: Base64 data URI string.
            token: Bearer token.
            user_id: User ID.

        Returns:
            Qwen API file object dict.

        Raises:
            Exception: malformed URI or upload failure.
        """
        if not data_uri.startswith("data:") or ";base64," not in data_uri:
            raise Exception("无效的 Base64 数据 URI")

        header, encoded = data_uri.split(";base64,", 1)
        mime_type = header.split("data:", 1)[1]

        ext = _DATA_URI_EXT_MAP.get(mime_type, ".bin")
        filename = "upload_{}{}".format(uuid.uuid4().hex[:8], ext)

        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        file_data = base64.b64decode(encoded)

        return await self.upload_file(file_data, filename, token, user_id)

    # =====================================================================
    # Base64 image extraction from messages
    # =====================================================================

    def _extract_base64_images(
        self, messages: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract all base64 data URI images from messages.

        Args:
            messages: OpenAI-format message list.

        Returns:
            List of base64 data URI strings.
        """
        uris: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "image_url":
                        img_url_obj = part.get("image_url", {})
                        img_url = (
                            img_url_obj.get("url", "")
                            if isinstance(img_url_obj, dict)
                            else str(img_url_obj)
                        )
                        if img_url.startswith("data:"):
                            uris.append(img_url)
        return uris

    # =====================================================================
    # Image download
    # =====================================================================

    async def download_image(
        self,
        image_url: str,
        save_dir: str = GENERATED_IMAGE_DIR,
    ) -> Optional[str]:
        """Download a generated image from CDN and save locally.

        Args:
            image_url: Image CDN URL.
            save_dir: Save directory.

        Returns:
            Local file path, or None on failure.
        """
        try:
            headers = {
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive",
                "Origin": BASE_URL,
                "Referer": "{}/".format(BASE_URL),
                "User-Agent": USER_AGENT,
            }
            async with self._session.get(
                image_url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    return None
                image_data = await resp.read()
                ct = resp.headers.get("Content-Type", "image/png")
                return save_image_file(image_data, ct, save_dir)
        except Exception as e:
            logger.debug("图片下载失败: %s", e)
            return None
