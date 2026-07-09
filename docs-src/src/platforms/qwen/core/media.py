"""Media mixin for QwenClient.

Provides video generation (i2v) and TTS speech synthesis.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any, Dict, List, Optional

import aiohttp

from src.logger import get_logger
from src.platforms.qwen.core.shared import (
    BASE_URL,
    CHAT_PATH,
    SSE_TIMEOUT,
    TASK_STATUS_PATH,
    TTS_DIR,
    TTS_PATH,
    TTS_TIMEOUT,
    USER_AGENT,
    VIDEO_TASK_MAX_POLL_TIME,
    VIDEO_TASK_POLL_INTERVAL,
    build_cdn_video_url,
    build_headers,
    build_i2v_payload,
    build_payload,
    build_replace_content_payload,
    build_tts_payload,
    parse_sse_event,
    save_video_file,
    save_wav_file,
)

logger = get_logger(__name__)

MAX_RETRIES: int = 3


class MediaMixin:
    """Mixin providing video generation and TTS synthesis.

    Expects the composed class to provide:
    - ``_session``: aiohttp.ClientSession
    - ``_cookies``: Dict[str, Any]
    - ``_fp``: str (fingerprint)
    - ``_get_proxy_kwarg()``: method returning Optional[str]
    - ``_create_chat(token, model, chat_type)``: coroutine returning chat_id
    - ``_cleanup_chat(chat_id, token)``: coroutine
    """

    # =====================================================================
    # Video generation (i2v)
    # =====================================================================

    async def _poll_task_status(
        self,
        task_id: str,
        token: str,
        chat_id: str,
    ) -> Dict[str, Any]:
        """Poll an async task (video generation, etc.) until completion.

        Args:
            task_id: Task ID.
            token: Bearer token.
            chat_id: Chat ID (for Referer).

        Returns:
            Task result dict on success.

        Raises:
            Exception: task failed or poll timed out.
        """
        url = "{}{}".format(
            BASE_URL,
            TASK_STATUS_PATH.format(task_id=task_id),
        )
        headers = build_headers(
            token,
            chat_id=chat_id,
            include_sse=False,
            cookies=self._cookies,
        )

        start = time.time()
        while time.time() - start < VIDEO_TASK_MAX_POLL_TIME:
            try:
                async with self._session.get(
                    url,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        ts = data.get("task_status", "")
                        logger.debug("任务 %s: %s", task_id, ts)
                        if ts == "succeeded":
                            return data
                        if ts == "failed":
                            raise Exception(
                                "任务失败: {}".format(
                                    data.get("message", "未知")
                                )
                            )
            except Exception as e:
                if "任务失败" in str(e):
                    raise
                logger.debug("轮询异常: %s", e)
            await asyncio.sleep(VIDEO_TASK_POLL_INTERVAL)

        raise Exception(
            "任务轮询超时 ({}s)".format(VIDEO_TASK_MAX_POLL_TIME)
        )

    async def generate_video(
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
        """Image-to-video (i2v) generation full flow.

        Flow: create i2v chat -> submit task -> poll status ->
        build CDN URL -> optional download.

        Args:
            prompt: Video generation prompt.
            image_url: Reference image URL (already uploaded to OSS).
            token: Bearer token.
            user_id: User ID.
            model: Model name.
            size: Aspect ratio (16:9 / 9:16 / 1:1).
            image_name: Reference image file name.
            download: Whether to download the video locally.

        Returns:
            Result dict with success/video_url/local_path/task_id/error.
        """
        # Create i2v chat
        try:
            chat_id = await self._create_chat(token, model, "i2v")
        except Exception as e:
            return {
                "success": False,
                "error": "创建 i2v 对话失败: {}".format(e),
            }

        payload = build_i2v_payload(
            prompt=prompt,
            chat_id=chat_id,
            model=model,
            image_url=image_url,
            image_name=image_name,
            size=size,
        )
        headers = build_headers(token, chat_id=chat_id, cookies=self._cookies)
        url = "{}{}?chat_id={}".format(BASE_URL, CHAT_PATH, chat_id)

        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=SSE_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    asyncio.ensure_future(
                        self._cleanup_chat(chat_id, token)
                    )
                    return {
                        "success": False,
                        "error": "HTTP {}: {}".format(
                            resp.status, err[:300]
                        ),
                    }

                data = await resp.json()
                if not data.get("success"):
                    asyncio.ensure_future(
                        self._cleanup_chat(chat_id, token)
                    )
                    return {"success": False, "error": str(data)}

                result_data = data.get("data", {})
                message_id = result_data.get("message_id", "")
                task_id = ""

                messages = result_data.get("messages", [])
                if messages:
                    wanx = messages[0].get("extra", {}).get("wanx", {})
                    task_id = wanx.get("task_id", "")

                if not task_id:
                    asyncio.ensure_future(
                        self._cleanup_chat(chat_id, token)
                    )
                    return {
                        "success": False,
                        "error": "响应中未找到 task_id",
                    }
        except Exception as e:
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return {"success": False, "error": str(e)}

        # Poll task status
        try:
            task_result = await self._poll_task_status(
                task_id, token, chat_id
            )
        except Exception as e:
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
            }

        # Build CDN URL
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

        # Optional download
        if download and video_url:
            try:
                dl_headers = {
                    "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": "{}/".format(BASE_URL),
                    "User-Agent": USER_AGENT,
                }
                async with self._session.get(
                    video_url,
                    headers=dl_headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=SSE_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        video_data = await resp.read()
                        local_path = save_video_file(video_data)
                        if local_path:
                            result["local_path"] = local_path
                            logger.info(
                                "视频已下载: %s", local_path
                            )
            except Exception as e:
                logger.debug("视频下载失败: %s", e)

        asyncio.ensure_future(self._cleanup_chat(chat_id, token))
        return result

    # =====================================================================
    # TTS speech synthesis
    # =====================================================================

    async def _replace_message_content(
        self,
        chat_id: str,
        response_id: str,
        new_content: str,
        origin_content: str,
        token: str,
    ) -> bool:
        """Replace message content (prerequisite for TTS).

        The TTS flow requires replacing the assistant message content
        with the target text before requesting synthesis.

        Args:
            chat_id: Chat ID.
            response_id: Assistant message ID.
            new_content: New content (TTS target text).
            origin_content: Original content (for token estimation).
            token: Bearer token.

        Returns:
            True on success, False on failure.
        """
        url = "{}/api/v2/chats/{}/messages/{}".format(
            BASE_URL, chat_id, response_id
        )
        headers = build_headers(token, chat_id=chat_id, cookies=self._cookies)
        payload = build_replace_content_payload(new_content, origin_content)

        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        return True
                    err = await resp.text()
                    logger.warning(
                        "内容替换失败 HTTP %d: %s", resp.status, err[:200]
                    )
            except Exception as e:
                logger.warning("内容替换异常: %s", e)

        return False

    async def request_tts(
        self,
        chat_id: str,
        response_id: str,
        token: str,
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """Request TTS synthesis, saving the PCM response as a WAV file.

        Receives Base64 PCM audio chunks via the
        ``/api/v2/tts/completions`` SSE endpoint, concatenates them,
        and wraps them in a WAV container.

        Args:
            chat_id: Chat ID.
            response_id: Assistant message ID (the message to synthesize).
            token: Bearer token.
            save_dir: WAV file save directory.

        Returns:
            WAV file path, or None on failure.
        """
        headers = build_headers(
            token,
            chat_id=chat_id,
            include_sse=True,
            cookies=self._cookies,
        )
        headers["Accept"] = "*/*"
        payload = build_tts_payload(chat_id, response_id)
        url = "{}{}" "?chat_id={}".format(BASE_URL, TTS_PATH, chat_id)

        chunks: List[str] = []
        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=TTS_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "TTS 请求失败 HTTP %d", resp.status
                    )
                    return None

                buf = b""
                async for raw in resp.content.iter_any():
                    if not raw:
                        continue
                    buf += raw
                    lines = buf.split(b"\n")
                    buf = lines[-1]

                    for lb in lines[:-1]:
                        ls = lb.decode("utf-8", errors="replace").strip()
                        if not ls or not ls.startswith("data:"):
                            continue
                        ds = ls[5:].lstrip()
                        if not ds or ds == "[DONE]":
                            continue
                        try:
                            d = json.loads(ds)
                            if "choices" in d and d["choices"]:
                                delta = d["choices"][0].get("delta", {})
                                tts_data = delta.get("tts")
                                if tts_data and tts_data.strip():
                                    chunks.append(tts_data)
                                if delta.get("status") == "finished":
                                    break
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            logger.warning("TTS 请求异常: %s", e)
            return None

        if not chunks:
            logger.warning("TTS 响应为空，无音频数据")
            return None

        # Decode Base64 PCM and save as WAV
        try:
            combined = "".join(chunks)
            padding = 4 - len(combined) % 4
            if padding != 4:
                combined += "=" * padding
            pcm_data = base64.b64decode(combined)
            return save_wav_file(pcm_data, save_dir)
        except Exception as e:
            logger.warning("TTS 音频解码失败: %s", e)
            return None

    async def synthesize_tts(
        self,
        text: str,
        token: str,
        model: str = "qwen3.6-plus",
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """Full TTS synthesis flow.

        Flow:
        1. Create a new chat.
        2. Send a placeholder message to obtain a ``response_id``.
        3. Replace the message content with the target text.
        4. Request TTS synthesis.
        5. Clean up the chat in the background.

        Args:
            text: Text to synthesize.
            token: Bearer token.
            model: Model name.
            save_dir: WAV file save directory.

        Returns:
            WAV file path, or None on failure.
        """
        # Create new chat
        try:
            chat_id = await self._create_chat(token, model, "t2t")
        except Exception as e:
            logger.warning("TTS 创建对话失败: %s", e)
            return None

        # Send placeholder message to get response_id
        quick_msg = "注意：啥都不要说，直接输出\\即可"
        response_id: Optional[str] = None
        origin_content = ""

        try:
            payload = build_payload(
                messages=[{"role": "user", "content": quick_msg}],
                model=model,
                chat_id=chat_id,
                thinking_enabled=False,
                auto_thinking=False,
                thinking_mode="Fast",
                stream=True,
            )
            headers = build_headers(
                token,
                chat_id=chat_id,
                include_sse=True,
                fingerprint=self._fp,
                cookies=self._cookies,
            )
            url = "{}{}?chat_id={}".format(BASE_URL, CHAT_PATH, chat_id)

            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    buf = b""
                    async for raw in resp.content.iter_any():
                        if not raw:
                            continue
                        buf += raw
                        lines = buf.split(b"\n")
                        buf = lines[-1]
                        for lb in lines[:-1]:
                            ls = lb.decode("utf-8", errors="replace").strip()
                            if not ls or not ls.startswith("data:"):
                                continue
                            ds = ls[5:].lstrip()
                            if not ds or ds == "[DONE]":
                                continue
                            try:
                                event = parse_sse_event(ds)
                                if event and event.get("type") == "response_created":
                                    response_id = event.get("response_id")
                                elif event and event.get("type") == "answer":
                                    origin_content += event.get(
                                        "content", ""
                                    )
                            except Exception:
                                continue
        except Exception as e:
            logger.warning("TTS 占位消息失败: %s", e)
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        if not response_id:
            logger.warning("TTS 未获取到 response_id")
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        # Replace message content
        success = await self._replace_message_content(
            chat_id, response_id, text, origin_content.strip(), token
        )
        if not success:
            logger.warning("TTS 内容替换失败")
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        # Request TTS synthesis
        audio_path = await self.request_tts(chat_id, response_id, token, save_dir)

        # Background cleanup
        asyncio.ensure_future(self._cleanup_chat(chat_id, token))

        if audio_path:
            logger.info("TTS 合成成功: %s", audio_path)
        else:
            logger.warning("TTS 合成失败，无音频输出")

        return audio_path
