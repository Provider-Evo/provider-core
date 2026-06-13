"""会话级别 HTTP 操作：创建 / 停止 / 删除对话、图片下载、占位消息。"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Callable, Dict, Final, Optional, Tuple

import aiohttp

from src.logger import get_logger
from .endpoints import (
    BASE_URL,
    CHAT_PATH,
    DELETE_CHAT_PATH,
    GENERATED_IMAGE_DIR,
    NEW_CHAT_PATH,
    STOP_CHAT_PATH,
    USER_AGENT,
)
from .headers import (
    build_headers,
    build_stop_headers,
)
from .payloads import (
    build_new_chat_payload,
    build_payload,
    build_stop_payload,
)
from .storage import save_image_file
from .sse import parse_sse_event

logger = get_logger(__name__)

NEW_CHAT_TIMEOUT: Final[int] = 15
STOP_DELETE_TIMEOUT: Final[int] = 15
PLACEHOLDER_TIMEOUT: Final[int] = 60
IMAGE_DOWNLOAD_TIMEOUT: Final[int] = 60


class ChatSession:
    """对话生命周期 HTTP 操作集合。

    Args:
        session: 共享的 aiohttp 会话。
        proxy_resolver: 返回当前代理 URL 的回调。
        cookies_provider: 返回当前 Cookie 字典的回调。
        fingerprint_provider: 返回当前指纹字符串的回调。
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
        cookies_provider: Callable[[], Dict],
        fingerprint_provider: Callable[[], str],
    ) -> None:
        self._session = session
        self._resolve_proxy = proxy_resolver
        self._cookies = cookies_provider
        self._fingerprint = fingerprint_provider

    # ====================================================================
    # 对话创建 / 停止 / 删除
    # ====================================================================
    async def create(
        self,
        token: str,
        model: str,
        chat_type: str = "t2t",
    ) -> str:
        """创建新对话，返回 ``chat_id``。

        Raises:
            RuntimeError: 创建失败。
        """
        headers = {
            "authorization": "Bearer {}".format(token),
            "content-type": "application/json;charset=UTF-8",
            "source": "web",
            "user-agent": USER_AGENT,
            "origin": BASE_URL,
            "referer": "{}/".format(BASE_URL),
            "accept": "application/json",
            "accept-language": "zh-CN,zh;q=0.9",
            "x-request-id": str(uuid.uuid4()),
        }
        payload = build_new_chat_payload(model, chat_type)
        url = "{}{}".format(BASE_URL, NEW_CHAT_PATH)

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=NEW_CHAT_TIMEOUT),
            proxy=self._resolve_proxy(),
        ) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise RuntimeError(
                    "Qwen 创建对话失败 HTTP {}: {}".format(
                        resp.status, err[:200]
                    )
                )
            data = await resp.json()
            if not data.get("success"):
                raise RuntimeError("Qwen 创建对话失败: {}".format(data))
            chat_id = data.get("data", {}).get("id")
            if not chat_id:
                raise RuntimeError(
                    "Qwen 创建对话响应缺少 chat_id: {}".format(data)
                )
            return chat_id

    async def stop(self, chat_id: str, token: str) -> bool:
        """向 Qwen 发送停止生成指令。"""
        if not chat_id or not token:
            return False
        url = "{}{}".format(BASE_URL, STOP_CHAT_PATH)
        headers = build_stop_headers(token)
        payload = build_stop_payload(chat_id)
        try:
            async with self._session.post(
                url,
                headers=headers,
                json=payload,
                ssl=False,
                timeout=aiohttp.ClientTimeout(
                    connect=5, total=STOP_DELETE_TIMEOUT
                ),
                proxy=self._resolve_proxy(),
            ) as resp:
                if resp.status in (200, 204):
                    return True
                logger.warning(
                    "Qwen 停止生成失败: HTTP %d", resp.status
                )
                return False
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning("Qwen 停止生成异常: %s", exc)
            return False

    async def delete(self, chat_id: str, token: str) -> bool:
        """删除指定对话。"""
        if not chat_id or not token:
            return False
        url = "{}{}".format(
            BASE_URL, DELETE_CHAT_PATH.format(chat_id=chat_id)
        )
        headers = build_headers(token, cookies=self._cookies())
        try:
            async with self._session.delete(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(
                    connect=5, total=STOP_DELETE_TIMEOUT
                ),
                proxy=self._resolve_proxy(),
            ) as resp:
                return resp.status in (200, 204)
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return False

    async def cleanup(self, chat_id: str, token: str) -> None:
        """后台异步清理对话；忽略一切错误。"""
        try:
            await self.delete(chat_id, token)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("Qwen 对话清理异常: %s", exc)

    # ====================================================================
    # 图片下载
    # ====================================================================
    async def download_image(
        self,
        image_url: str,
        save_dir: str = GENERATED_IMAGE_DIR,
    ) -> Optional[str]:
        """下载图片到本地。"""
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
                timeout=aiohttp.ClientTimeout(
                    total=IMAGE_DOWNLOAD_TIMEOUT
                ),
                proxy=self._resolve_proxy(),
            ) as resp:
                if resp.status != 200:
                    return None
                image_data = await resp.read()
                ct = resp.headers.get("Content-Type", "image/png")
                return save_image_file(image_data, ct, save_dir)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.debug("图片下载失败: %s", exc)
            return None

    # ====================================================================
    # 占位消息（用于 TTS 获取 response_id）
    # ====================================================================
    async def send_placeholder_message(
        self,
        chat_id: str,
        token: str,
        model: str,
    ) -> Tuple[Optional[str], str]:
        """发送一条 "忽略" 占位消息，返回 ``(response_id, origin_text)``。"""
        quick_msg = "注意：啥都不要说，直接输出\\即可"
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
            fingerprint=self._fingerprint(),
            cookies=self._cookies(),
        )
        url = "{}{}?chat_id={}".format(BASE_URL, CHAT_PATH, chat_id)

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=PLACEHOLDER_TIMEOUT),
            proxy=self._resolve_proxy(),
        ) as resp:
            if resp.status != 200:
                return None, ""
            return await self._consume_placeholder(resp)

    @staticmethod
    async def _consume_placeholder(
        resp: aiohttp.ClientResponse,
    ) -> Tuple[Optional[str], str]:
        """从占位消息的 SSE 流中提取 ``response_id`` 与累积文本。"""
        response_id: Optional[str] = None
        origin_content = ""
        buf = b""
        async for raw in resp.content.iter_any():
            if not raw:
                continue
            buf += raw
            lines = buf.split(b"\n")
            buf = lines[-1]
            for line_bytes in lines[:-1]:
                line = line_bytes.decode(
                    "utf-8", errors="replace"
                ).strip()
                if not line or not line.startswith("data:"):
                    continue
                data_str = line[5:].lstrip()
                if not data_str or data_str == "[DONE]":
                    continue
                event = parse_sse_event(data_str)
                if event is None:
                    continue
                if event.get("type") == "response_created":
                    response_id = event.get("response_id")
                elif event.get("type") == "answer":
                    origin_content += event.get("content", "")
        return response_id, origin_content


# 兼容 noqa：让外部能从此模块继续 import Any 与 Dict（部分类型别名场景）
__all__ = ["ChatSession", "Any", "Dict"]
