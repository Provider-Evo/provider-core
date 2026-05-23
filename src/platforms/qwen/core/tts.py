"""TTS 语音合成服务（替换内容 → ``/api/v2/tts/completions``）。

依赖一个 "占位聊天" 步骤来获取助手消息 ``response_id``，因此构造
时需要注入用于触发占位聊天的回调（避免与 :class:`StreamHandler` 形成
循环依赖）。
"""

from __future__ import annotations

import asyncio
import base64
import json
from typing import Awaitable, Callable, Final, List, Optional

import aiohttp

from src.logger import get_logger
from .endpoints import (
    BASE_URL,
    TTS_DIR,
    TTS_PATH,
    TTS_TIMEOUT,
)
from .headers import build_headers
from .payloads import (
    build_replace_content_payload,
    build_tts_payload,
)
from .storage import save_wav_file

logger = get_logger(__name__)

MAX_RETRIES: Final[int] = 3
REPLACE_TIMEOUT: Final[int] = 30


class TtsService:
    """TTS 服务封装。

    Args:
        session: 共享的 aiohttp 会话。
        proxy_resolver: 返回当前应使用代理 URL 的回调。
        cookies_provider: 返回当前 Cookie 字典的回调（实时获取，
            避免 Cookie 刷新后引用陈旧值）。
        fingerprint_provider: 返回当前指纹字符串的回调。
        create_chat: 创建新对话的协程（``token, model, chat_type`` →
            ``chat_id``）。
        get_response_id: 通过占位消息获取 ``response_id`` 的协程
            （``chat_id, token, model`` → ``(response_id, origin_text)``）。
        cleanup_chat: 后台清理对话的协程（``chat_id, token``）。
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
        cookies_provider: Callable[[], dict],
        fingerprint_provider: Callable[[], str],
        create_chat: Callable[[str, str, str], Awaitable[str]],
        get_response_id: Callable[
            [str, str, str],
            Awaitable[tuple],
        ],
        cleanup_chat: Callable[[str, str], Awaitable[None]],
    ) -> None:
        self._session = session
        self._resolve_proxy = proxy_resolver
        self._cookies = cookies_provider
        self._fingerprint = fingerprint_provider
        self._create_chat = create_chat
        self._get_response_id = get_response_id
        self._cleanup_chat = cleanup_chat

    # ---------------------------------------------------------------- 公共
    async def synthesize(
        self,
        text: str,
        token: str,
        model: str = "qwen3.6-plus",
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """完整 TTS 合成流程。

        流程：

        1. 创建新对话
        2. 占位消息获取 ``response_id``
        3. 替换助手消息为目标文本
        4. 请求 TTS 合成 SSE
        5. 后台清理对话

        Args:
            text: 待合成文本。
            token: Bearer 令牌。
            model: 模型名称。
            save_dir: WAV 文件保存目录。

        Returns:
            成功时返回 WAV 文件路径；失败返回 ``None``。
        """
        try:
            chat_id = await self._create_chat(token, model, "t2t")
        except (aiohttp.ClientError, RuntimeError, asyncio.TimeoutError) as exc:
            logger.warning("TTS 创建对话失败: %s", exc)
            return None

        try:
            response_id, origin_content = await self._get_response_id(
                chat_id, token, model
            )
        except (
            aiohttp.ClientError,
            RuntimeError,
            asyncio.TimeoutError,
        ) as exc:
            logger.warning("TTS 占位消息失败: %s", exc)
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        if not response_id:
            logger.warning("TTS 未获取到 response_id")
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        ok = await self.replace_message_content(
            chat_id,
            response_id,
            text,
            origin_content.strip() if origin_content else "",
            token,
        )
        if not ok:
            logger.warning("TTS 内容替换失败")
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        audio_path = await self.request_tts(
            chat_id, response_id, token, save_dir
        )
        asyncio.ensure_future(self._cleanup_chat(chat_id, token))

        if audio_path:
            logger.info("TTS 合成成功: %s", audio_path)
        else:
            logger.warning("TTS 合成失败，无音频输出")
        return audio_path

    # ----------------------------------------------------------------- 步骤
    async def replace_message_content(
        self,
        chat_id: str,
        response_id: str,
        new_content: str,
        origin_content: str,
        token: str,
    ) -> bool:
        """替换助手消息内容（TTS 前置步骤）。"""
        url = "{}/api/v2/chats/{}/messages/{}".format(
            BASE_URL, chat_id, response_id
        )
        headers = build_headers(
            token, chat_id=chat_id, cookies=self._cookies()
        )
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
                    timeout=aiohttp.ClientTimeout(total=REPLACE_TIMEOUT),
                    proxy=self._resolve_proxy(),
                ) as resp:
                    if resp.status == 200:
                        return True
                    err = await resp.text()
                    logger.warning(
                        "内容替换失败 HTTP %d: %s", resp.status, err[:200]
                    )
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                logger.warning("内容替换异常: %s", exc)
        return False

    async def request_tts(
        self,
        chat_id: str,
        response_id: str,
        token: str,
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """请求 ``/api/v2/tts/completions``，将 PCM 流保存为 WAV。"""
        headers = build_headers(
            token,
            chat_id=chat_id,
            include_sse=True,
            fingerprint=self._fingerprint(),
            cookies=self._cookies(),
        )
        headers["Accept"] = "*/*"
        payload = build_tts_payload(chat_id, response_id)
        url = "{}{}?chat_id={}".format(BASE_URL, TTS_PATH, chat_id)

        chunks: List[str] = []
        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=TTS_TIMEOUT),
                proxy=self._resolve_proxy(),
            ) as resp:
                if resp.status != 200:
                    logger.warning("TTS 请求失败 HTTP %d", resp.status)
                    return None
                await self._collect_tts_chunks(resp, chunks)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("TTS 请求异常: %s", exc)
            return None

        if not chunks:
            logger.warning("TTS 响应为空，无音频数据")
            return None

        try:
            combined = "".join(chunks)
            padding = 4 - len(combined) % 4
            if padding != 4:
                combined += "=" * padding
            pcm_data = base64.b64decode(combined)
            return save_wav_file(pcm_data, save_dir)
        except (ValueError, OSError) as exc:
            logger.warning("TTS 音频解码失败: %s", exc)
            return None

    @staticmethod
    async def _collect_tts_chunks(
        resp: aiohttp.ClientResponse,
        chunks: List[str],
    ) -> None:
        """从 TTS SSE 流中收集 Base64 PCM 分片到 ``chunks``。"""
        buf = b""
        async for raw in resp.content.iter_any():
            if not raw:
                continue
            buf += raw
            lines = buf.split(b"\n")
            buf = lines[-1]
            for line_bytes in lines[:-1]:
                line = line_bytes.decode("utf-8", errors="replace").strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].lstrip()
                if not data_str or data_str == "[DONE]":
                    continue
                try:
                    payload = json.loads(data_str)
                except (json.JSONDecodeError, ValueError):
                    continue
                choices = payload.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                tts_data = delta.get("tts")
                if tts_data and tts_data.strip():
                    chunks.append(tts_data)
                if delta.get("status") == "finished":
                    return
