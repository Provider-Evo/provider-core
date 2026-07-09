"""AItianhu2 文件上传服务模块。

提供完整的文件上传流程：获取预签名 URL、上传到存储、最终确认。
"""

from __future__ import annotations

import os
import struct
from typing import Any, Callable, Dict, Optional
from urllib.parse import parse_qs, urlparse

import aiohttp

from src.logger import get_logger
from .constants import BASE_URL, USER_AGENT
from .headers import build_headers

logger = get_logger(__name__)


class UploadService:
    """OSS 文件上传服务。

    负责文件上传的完整流程，包括获取预签名 URL、
    上传到存储（Azure Blob 或 multipart）、最终确认。
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
    ) -> None:
        """初始化上传服务。

        Args:
            session: 共享的 aiohttp ClientSession。
            proxy_resolver: 代理解析回调。
        """
        self._session = session
        self._resolve_proxy = proxy_resolver

    async def upload(
        self,
        device_id: str,
        api_key: str,
        file_path: str,
        use_case: str = "multimodal",
        conversation_id: str = "",
        *,
        account_id: str = "",
    ) -> Dict[str, Any]:
        """完整文件上传流程。

        Args:
            device_id: 设备标识。
            api_key: API key。
            file_path: 本地文件路径。
            use_case: 使用场景（默认 "multimodal"）。
            conversation_id: 会话 ID（可选）。
            account_id: 动态 ``chatgpt-account-id``（可选）。

        Returns:
            {"file_id": str, "upload_url": str, "status": str, "metadata": dict}

        Raises:
            RuntimeError: 获取上传 URL 失败。
        """
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        import mimetypes
        file_type, _ = mimetypes.guess_type(file_path)
        file_type = file_type or "application/octet-stream"

        url_info = await self._get_upload_url(
            device_id, api_key,
            file_name, file_size, file_type, use_case, conversation_id,
            account_id=account_id,
        )
        if url_info.get("status") != "success":
            raise RuntimeError(f"获取上传 URL 失败: {url_info}")

        upload_url: str = url_info["upload_url"]
        file_id: str = url_info["file_id"]

        with open(file_path, "rb") as f:
            file_content = f.read()

        await self._upload_to_url(
            upload_url, file_id, file_name, file_content, file_type, use_case,
        )

        meta: Dict[str, Any] = {
            **await self._finalize_stream(
                device_id, api_key, file_id, file_name, use_case,
                account_id=account_id,
            ),
            **await self._finalize_estuary(
                device_id, api_key, upload_url, file_id, file_name,
                file_content, file_type, use_case,
                account_id=account_id,
            ),
        }

        return {
            "file_id": file_id,
            "upload_url": upload_url,
            "status": "success",
            "metadata": meta,
        }

    async def _get_upload_url(
        self,
        device_id: str,
        api_key: str,
        file_name: str,
        file_size: int,
        file_type: str,
        use_case: str,
        conversation_id: str,
        *,
        account_id: str = "",
    ) -> Dict[str, Any]:
        """POST /backend-api/files — 获取预签名上传 URL。"""
        body: Dict[str, Any] = {
            "file_name": file_name,
            "file_size": file_size,
            "file_type": file_type,
            "use_case": use_case,
        }
        if conversation_id:
            body["conversation_id"] = conversation_id
        headers = {
            **build_headers(device_id),
            "Authorization": f"Bearer {api_key}",
        }
        if account_id:
            headers["chatgpt-account-id"] = account_id
        async with self._session.post(
            f"{BASE_URL}/backend-api/files",
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def _upload_to_url(
        self,
        upload_url: str,
        file_id: str,
        file_name: str,
        file_content: bytes,
        file_type: str,
        use_case: str,
    ) -> None:
        """上传文件到预签名 URL。"""
        parsed = urlparse(upload_url)
        is_azure = "sv=" in parsed.query or "sig=" in parsed.query
        content_type = file_type or "application/octet-stream"

        if is_azure:
            async with self._session.put(
                upload_url,
                data=file_content,
                headers={
                    "x-ms-blob-type": "BlockBlob",
                    "Content-Type": content_type,
                    "user-agent": USER_AGENT,
                },
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()
        else:
            query_params = parse_qs(parsed.query)
            actual_url = query_params.get("upload_url", [upload_url])[0]
            if actual_url.startswith("/"):
                post_url = BASE_URL + actual_url
            elif actual_url.startswith("http"):
                post_url = actual_url
            else:
                post_url = f"{BASE_URL}/{actual_url}"
            data = aiohttp.FormData()
            data.add_field(
                "file", file_content, filename=file_name,
                content_type=content_type,
            )
            data.add_field("upload_url", actual_url)
            data.add_field("file_id", file_id)
            data.add_field("file_name", file_name)
            data.add_field("use_case", use_case)
            data.add_field("index_for_retrieval", "false")
            async with self._session.post(
                post_url,
                data=data,
                headers={"user-agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                resp.raise_for_status()

    async def _finalize_stream(
        self,
        device_id: str,
        api_key: str,
        file_id: str,
        file_name: str,
        use_case: str,
        *,
        account_id: str = "",
    ) -> Dict[str, Any]:
        """POST /backend-api/files/process_upload_stream — SSE 流式最终确认。"""
        headers = {
            **build_headers(device_id),
            "Authorization": f"Bearer {api_key}",
            "accept": "text/event-stream",
        }
        if account_id:
            headers["chatgpt-account-id"] = account_id
        async with self._session.post(
            f"{BASE_URL}/backend-api/files/process_upload_stream",
            headers=headers,
            json={
                "file_id": file_id,
                "use_case": use_case,
                "gizmo_id": None,
                "index_for_retrieval": False,
                "file_name": file_name,
            },
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            resp.raise_for_status()
            result: Dict[str, Any] = {}
            async for line in resp.content:
                raw = line.decode("utf-8", errors="replace").strip()
                if not raw:
                    continue
                if raw.startswith("data: "):
                    ds = raw[6:]
                elif raw.startswith("data:"):
                    ds = raw[5:]
                else:
                    continue
                if ds.strip() == "[DONE]":
                    break
                try:
                    import json
                    d = json.loads(ds)
                    if isinstance(d, dict):
                        if "total_tokens" in d:
                            result["fileTokenSize"] = d["total_tokens"]
                        if "metadata_object_id" in d:
                            result["libraryFileId"] = d["metadata_object_id"]
                except json.JSONDecodeError:
                    continue
            return result

    async def _finalize_estuary(
        self,
        device_id: str,
        api_key: str,
        upload_url: str,
        file_id: str,
        file_name: str,
        file_content: bytes,
        file_type: str,
        use_case: str,
        *,
        account_id: str = "",
    ) -> Dict[str, Any]:
        """POST /backend-api/estuary/upload_content_and_finalize — 二次确认。"""
        content_type = file_type or "application/octet-stream"
        h = {
            k: v for k, v in build_headers(device_id).items()
            if k.lower() != "content-type"
        }
        h["Authorization"] = f"Bearer {api_key}"
        if account_id:
            h["chatgpt-account-id"] = account_id
        try:
            data = aiohttp.FormData()
            data.add_field(
                "file", file_content, filename=file_name,
                content_type=content_type,
            )
            data.add_field("upload_url", upload_url)
            data.add_field("file_id", file_id)
            data.add_field("file_name", file_name)
            data.add_field("use_case", use_case)
            async with self._session.post(
                f"{BASE_URL}/backend-api/estuary/upload_content_and_finalize",
                headers=h,
                data=data,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status != 200:
                    return {}
                result: Dict[str, Any] = {}
                async for raw in resp.content:
                    line = raw.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        ds = line[6:].strip()
                    elif line.startswith("data:"):
                        ds = line[5:].strip()
                    else:
                        continue
                    if ds == "[DONE]":
                        break
                    try:
                        import json
                        d = json.loads(ds)
                        if isinstance(d, dict):
                            if "total_tokens" in d:
                                result["fileTokenSize"] = d["total_tokens"]
                            if "metadata_object_id" in d:
                                result["libraryFileId"] = d["metadata_object_id"]
                            if "event" in d:
                                result["last_event"] = d["event"]
                    except json.JSONDecodeError:
                        continue
                return result
        except Exception:
            return {}


def image_dimensions(file_path: str, file_type: str) -> Dict[str, int]:
    """从文件头读取图像宽高（PNG / JPEG）。

    Args:
        file_path: 图像文件路径。
        file_type: MIME 类型。

    Returns:
        {"width": int, "height": int} 或空字典。
    """
    dims: Dict[str, int] = {}
    try:
        with open(file_path, "rb") as f:
            header = f.read(32)
        if file_type == "image/png" and header[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", header[16:24])
            dims["width"] = w
            dims["height"] = h
        elif file_type == "image/jpeg" and header[:2] == b"\xff\xd8":
            with open(file_path, "rb") as f:
                raw = f.read()
            pos = 2
            while pos < len(raw) - 9:
                if raw[pos] == 0xFF and raw[pos + 1] in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", raw[pos + 5: pos + 9])
                    dims["width"] = w
                    dims["height"] = h
                    break
                pos += 1
    except Exception as exc:
        logger.debug("读取图片尺寸失败: %s", exc)
    return dims
