"""图片到视频（i2v）生成服务：提交任务 → 轮询 → CDN 下载。"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, Final, Optional

import aiohttp

from src.logger import get_logger
from .cdn import build_cdn_video_url
from .endpoints import (
    BASE_URL,
    CHAT_PATH,
    SSE_TIMEOUT,
    TASK_STATUS_PATH,
    USER_AGENT,
    VIDEO_TASK_MAX_POLL_TIME,
    VIDEO_TASK_POLL_INTERVAL,
)
from .headers import build_headers
from .payloads import build_i2v_payload
from .storage import save_video_file

logger = get_logger(__name__)

POLL_TIMEOUT: Final[int] = 30


class VideoService:
    """i2v 视频生成服务。"""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
        cookies_provider: Callable[[], dict],
        create_chat: Callable[[str, str, str], Awaitable[str]],
        cleanup_chat: Callable[[str, str], Awaitable[None]],
    ) -> None:
        self._session = session
        self._resolve_proxy = proxy_resolver
        self._cookies = cookies_provider
        self._create_chat = create_chat
        self._cleanup_chat = cleanup_chat

    # --------------------------------------------------------------- 主流程
    async def generate(
        self,
        prompt: str,
        image_url: str,
        token: str,
        user_id: str,
        model: str = "qwen-max-latest",
        size: str = "16:9",
        image_name: str = "source.png",
        download: bool = True,
    ) -> Dict[str, Any]:
        """完整 i2v 生成流程。

        Args:
            prompt: 视频描述。
            image_url: 参考图片 URL（已上传到 OSS）。
            token: Bearer 令牌。
            user_id: 用户 ID。
            model: 模型名称。
            size: 视频尺寸。
            image_name: 参考图片文件名。
            download: 是否下载到本地。

        Returns:
            含 ``success`` / ``video_url`` / ``local_path`` / ``task_id`` /
            ``error`` 等字段的结果字典。
        """
        chat_id = await self._create_chat_or_error(token, model)
        if isinstance(chat_id, dict):
            return chat_id

        submit = await self._submit_task(
            prompt=prompt,
            chat_id=chat_id,
            model=model,
            image_url=image_url,
            image_name=image_name,
            size=size,
            token=token,
        )
        if not submit.get("success"):
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return submit

        task_result = await self._poll_or_error(
            submit["task_id"], token, chat_id
        )
        if isinstance(task_result, dict) and not task_result.get("__poll_ok__"):
            return task_result

        return await self._build_final_result(
            submit=submit,
            chat_id=chat_id,
            token=token,
            user_id=user_id,
            size=size,
            task_result=task_result["data"],
            download=download,
        )

    async def _create_chat_or_error(
        self, token: str, model: str
    ) -> Any:
        """创建 i2v 对话；失败时返回错误字典而非抛错。"""
        try:
            return await self._create_chat(token, model, "i2v")
        except (aiohttp.ClientError, RuntimeError, asyncio.TimeoutError) as exc:
            return {
                "success": False,
                "error": "创建 i2v 对话失败: {}".format(exc),
            }

    async def _poll_or_error(
        self, task_id: str, token: str, chat_id: str
    ) -> Dict[str, Any]:
        """轮询任务；成功返回 ``{__poll_ok__: True, data: ...}``，
        失败返回完整错误字典并清理对话。"""
        try:
            data = await self._poll_task_status(task_id, token, chat_id)
            return {"__poll_ok__": True, "data": data}
        except (RuntimeError, aiohttp.ClientError, asyncio.TimeoutError) as exc:
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return {
                "success": False,
                "task_id": task_id,
                "error": str(exc),
            }

    async def _build_final_result(
        self,
        *,
        submit: Dict[str, Any],
        chat_id: str,
        token: str,
        user_id: str,
        size: str,
        task_result: Dict[str, Any],
        download: bool,
    ) -> Dict[str, Any]:
        """根据任务结果组装最终响应（含可选下载）。"""
        task_id = submit["task_id"]
        message_id = submit["message_id"]
        video_url = task_result.get("content") or build_cdn_video_url(
            user_id=user_id,
            video_type="i2v",
            message_id=message_id,
            task_id=task_id,
            token=token,
        )
        result: Dict[str, Any] = {
            "success": True,
            "task_id": task_id,
            "message_id": message_id,
            "chat_id": chat_id,
            "video_url": video_url,
            "size": size,
        }
        if download and video_url:
            local_path = await self._download_video(video_url)
            if local_path:
                result["local_path"] = local_path
                logger.info("视频已下载: %s", local_path)
        asyncio.ensure_future(self._cleanup_chat(chat_id, token))
        return result

    # -------------------------------------------------------------- 子步骤
    async def _submit_task(
        self,
        *,
        prompt: str,
        chat_id: str,
        model: str,
        image_url: str,
        image_name: str,
        size: str,
        token: str,
    ) -> Dict[str, Any]:
        """提交 i2v 任务，返回 ``{success, task_id, message_id}`` 或失败信息。"""
        payload = build_i2v_payload(
            prompt=prompt,
            chat_id=chat_id,
            model=model,
            image_url=image_url,
            image_name=image_name,
            size=size,
        )
        headers = build_headers(
            token, chat_id=chat_id, cookies=self._cookies()
        )
        url = "{}{}?chat_id={}".format(BASE_URL, CHAT_PATH, chat_id)
        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=SSE_TIMEOUT),
                proxy=self._resolve_proxy(),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    return {
                        "success": False,
                        "error": "HTTP {}: {}".format(resp.status, err[:300]),
                    }
                data = await resp.json()
                if not data.get("success"):
                    return {"success": False, "error": str(data)}
                result_data = data.get("data", {})
                message_id = result_data.get("message_id", "")
                task_id = ""
                messages = result_data.get("messages", [])
                if messages:
                    wanx = (
                        messages[0].get("extra", {}).get("wanx", {})
                    )
                    task_id = wanx.get("task_id", "")
                if not task_id:
                    return {
                        "success": False,
                        "error": "响应中未找到 task_id",
                    }
                return {
                    "success": True,
                    "task_id": task_id,
                    "message_id": message_id,
                }
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            return {"success": False, "error": str(exc)}

    async def _poll_task_status(
        self,
        task_id: str,
        token: str,
        chat_id: str,
    ) -> Dict[str, Any]:
        """轮询任务直至成功或超时。"""
        url = "{}{}".format(
            BASE_URL, TASK_STATUS_PATH.format(task_id=task_id)
        )
        headers = build_headers(
            token,
            chat_id=chat_id,
            include_sse=False,
            cookies=self._cookies(),
        )
        start = time.time()
        while time.time() - start < VIDEO_TASK_MAX_POLL_TIME:
            done = await self._poll_once(url, headers, task_id)
            if done is not None:
                return done
            await asyncio.sleep(VIDEO_TASK_POLL_INTERVAL)
        raise RuntimeError(
            "任务轮询超时 ({}s)".format(VIDEO_TASK_MAX_POLL_TIME)
        )

    async def _poll_once(
        self,
        url: str,
        headers: Dict[str, str],
        task_id: str,
    ) -> Optional[Dict[str, Any]]:
        """执行一次轮询请求；成功返回任务数据，未完成返回 ``None``。

        Raises:
            RuntimeError: 任务被服务端标记为 failed。
        """
        try:
            async with self._session.get(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=POLL_TIMEOUT),
                proxy=self._resolve_proxy(),
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                return self._parse_poll_status(data, task_id)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("轮询异常: %s", exc)
            return None

    @staticmethod
    def _parse_poll_status(
        data: Dict[str, Any], task_id: str
    ) -> Optional[Dict[str, Any]]:
        """根据轮询响应判定任务状态；成功返回 data，未完成返回 None。"""
        ts = data.get("task_status", "")
        logger.debug("任务 %s: %s", task_id, ts)
        if ts == "succeeded":
            return data
        if ts == "failed":
            raise RuntimeError(
                "任务失败: {}".format(data.get("message", "未知"))
            )
        return None

    async def _download_video(self, video_url: str) -> Optional[str]:
        """下载 CDN 视频到本地，失败返回 ``None``。"""
        dl_headers = {
            "Accept": "*/*",
            "Origin": BASE_URL,
            "Referer": "{}/".format(BASE_URL),
            "User-Agent": USER_AGENT,
        }
        try:
            async with self._session.get(
                video_url,
                headers=dl_headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=SSE_TIMEOUT),
                proxy=self._resolve_proxy(),
            ) as resp:
                if resp.status != 200:
                    return None
                video_data = await resp.read()
                return save_video_file(video_data)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("视频下载失败: %s", exc)
            return None
