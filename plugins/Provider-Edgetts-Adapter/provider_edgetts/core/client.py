"""Edge TTS HTTP/WebSocket 协调器。

职责限定为协调：账号 / 候选项 / 会话生命周期 /
顶层错误处理与重试。具体 TTS 合成逻辑封装在内部。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import secrets
import socket
import ssl
import struct
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

import certifi

from src.core.dispatch.candidate import Candidate, make_id
from src.core.errors import NotSupportedError
from src.logger import get_logger
from ..accounts import ACCOUNTS
from .constants import (
    CAPS,
    DEFAULT_VOICE,
    MAX_RETRIES,
    SEC_MS_GEC_VERSION,
    TRUSTED_CLIENT_TOKEN,
    WSS_HOST,
    WSS_PATH_BASE,
    WIN_EPOCH,
    S_TO_NS,
)
from .drm import build_wss_headers, remove_incompatible_characters, build_ssml

logger = get_logger(__name__)


class _RawWebSocket:
    """原始 WebSocket 实现（基于 socket + SSL）。"""

    def __init__(self, sock: ssl.SSLSocket) -> None:
        self._sock = sock
        self._closed = False
        self._recv_buf: bytes = b""
        self._fragment_opcode: int = 0
        self._fragment_buffer: bytes = b""

    @staticmethod
    def connect(
        host: str,
        port: int,
        path: str,
        extra_headers: Dict[str, str],
        ssl_ctx: ssl.SSLContext,
        timeout: float,
    ) -> "_RawWebSocket":
        """建立 WebSocket 连接。

        Args:
            host: 主机名。
            port: 端口号。
            path: WebSocket 路径。
            extra_headers: 额外请求头。
            ssl_ctx: SSL 上下文。
            timeout: 超时秒数。

        Returns:
            _RawWebSocket 实例。
        """
        raw_sock = socket.create_connection((host, port), timeout=timeout)
        tls_sock = ssl_ctx.wrap_socket(raw_sock, server_hostname=host)
        tls_sock.settimeout(timeout)

        ws_key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request_lines: List[str] = [
            "GET {} HTTP/1.1".format(path),
            "Host: {}".format(host),
            "Upgrade: websocket",
            "Connection: Upgrade",
            "Sec-WebSocket-Key: {}".format(ws_key),
            "Sec-WebSocket-Version: 13",
        ]
        for k, v in extra_headers.items():
            if k.lower() in (
                "host", "upgrade", "connection",
                "sec-websocket-key", "sec-websocket-version",
                "sec-websocket-extensions", "sec-websocket-protocol",
            ):
                continue
            request_lines.append("{}: {}".format(k, v))
        http_request = "\r\n".join(request_lines) + "\r\n\r\n"
        tls_sock.sendall(http_request.encode("utf-8"))

        response_buf = b""
        while b"\r\n\r\n" not in response_buf:
            chunk = tls_sock.recv(4096)
            if not chunk:
                raise ConnectionError("Connection closed during WebSocket handshake")
            response_buf += chunk

        first_line = response_buf.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
        if "101" not in first_line:
            raise RuntimeError("WebSocket handshake failed: {}".format(first_line.strip()))

        expected_accept = base64.b64encode(
            hashlib.sha1((ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        header_section = response_buf.split(b"\r\n\r\n", 1)[0].decode("ascii", errors="replace")
        if expected_accept not in header_section:
            raise RuntimeError("WebSocket Sec-WebSocket-Accept mismatch")

        ws = _RawWebSocket(tls_sock)
        ws._recv_buf = response_buf.split(b"\r\n\r\n", 1)[1]
        return ws

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        """发送 WebSocket 帧。

        Args:
            opcode: 帧操作码。
            payload: 帧载荷。
        """
        header = bytearray()
        header.append(0x80 | opcode)
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        mask_key = secrets.token_bytes(4)
        header += mask_key
        masked = bytearray(length)
        for i in range(length):
            masked[i] = payload[i] ^ mask_key[i % 4]
        self._sock.sendall(bytes(header) + bytes(masked))

    def send_text(self, text: str) -> None:
        """发送文本消息。

        Args:
            text: 待发送的文本。
        """
        self._send_frame(0x1, text.encode("utf-8"))

    def _recv_bytes(self, n: int, timeout: float) -> bytes:
        """接收指定字节数。

        Args:
            n: 字节数。
            timeout: 超时秒数。

        Returns:
            接收的字节数据。
        """
        buf = getattr(self, "_recv_buf", b"")
        while len(buf) < n:
            self._sock.settimeout(timeout)
            chunk = self._sock.recv(65536)
            if not chunk:
                raise ConnectionError("WebSocket connection closed unexpectedly")
            buf += chunk
        self._recv_buf = buf[n:]
        return buf[:n]

    def _recv_single_frame(self, timeout: float) -> Tuple[int, bytes, bool]:
        """接收单个 WebSocket 帧。

        Args:
            timeout: 超时秒数。

        Returns:
            (操作码, 载荷, 是否最后一帧) 元组。
        """
        header = self._recv_bytes(2, timeout)
        byte0, byte1 = header[0], header[1]
        fin = bool(byte0 & 0x80)
        opcode = byte0 & 0x0F
        masked = bool(byte1 & 0x80)
        payload_len = byte1 & 0x7F
        if payload_len == 126:
            payload_len = struct.unpack(">H", self._recv_bytes(2, timeout))[0]
        elif payload_len == 127:
            payload_len = struct.unpack(">Q", self._recv_bytes(8, timeout))[0]
        mask_key = b""
        if masked:
            mask_key = self._recv_bytes(4, timeout)
        payload = self._recv_bytes(payload_len, timeout)
        if masked:
            payload = bytes(payload[i] ^ mask_key[i % 4] for i in range(len(payload)))
        return opcode, payload, fin

    def recv_message(self, timeout: float = 60.0) -> Tuple[int, bytes]:
        """接收完整消息（自动处理分帧）。

        Args:
            timeout: 超时秒数。

        Returns:
            (操作码, 载荷) 元组。
        """
        while True:
            opcode, payload, fin = self._recv_single_frame(timeout)
            if opcode == 0x9:  # PING
                self._send_frame(0xA, payload)
                continue
            if opcode == 0x8:  # CLOSE
                self._closed = True
                return 0x8, b""
            if opcode == 0x0:
                self._fragment_buffer += payload
                if fin:
                    complete_payload = self._fragment_buffer
                    complete_opcode = self._fragment_opcode
                    self._fragment_buffer = b""
                    self._fragment_opcode = 0
                    return complete_opcode, complete_payload
                continue
            if not fin:
                self._fragment_opcode = opcode
                self._fragment_buffer = payload
                continue
            return opcode, payload

    def close(self) -> None:
        """关闭 WebSocket 连接。"""
        if not self._closed:
            try:
                self._send_frame(0x8, b"")
            except Exception as exc:
                logger.debug("edgetts 发送关闭帧失败: %s", exc)
            self._closed = True
        try:
            self._sock.close()
        except Exception as exc:
            logger.debug("edgetts 关闭 socket 失败: %s", exc)


def _drm_generate_sec_ms_gec() -> str:
    """生成 Sec-MS-GEC 鉴权值。

    Returns:
        鉴权字符串。
    """
    ticks = datetime.now(timezone.utc).timestamp()
    ticks += WIN_EPOCH
    ticks -= ticks % 300
    ticks *= S_TO_NS / 100
    return hashlib.sha256("{}{}".format(ticks, TRUSTED_CLIENT_TOKEN).encode("ascii")).hexdigest().upper()


def _connect_id() -> str:
    """生成连接 ID。

    Returns:
        UUID hex 字符串。
    """
    return uuid.uuid4().hex


def _date_to_string() -> str:
    """生成时间戳字符串。

    Returns:
        格式化的时间字符串。
    """
    return time.strftime(
        "%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)",
        time.gmtime(),
    )


def _parse_tts_text_frame(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    """解析 TTS 文本帧。

    Args:
        data: 原始帧数据。

    Returns:
        (头部字典, 剩余数据) 元组。
    """
    sep = data.find(b"\r\n\r\n")
    if sep < 0:
        return {}, b""
    headers: Dict[bytes, bytes] = {}
    for line in data[:sep].split(b"\r\n"):
        if b":" not in line:
            continue
        key, value = line.split(b":", 1)
        headers[key.strip()] = value.strip()
    return headers, data[sep + 4:]


def _parse_tts_binary_frame(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    """解析 TTS 二进制帧。

    Args:
        data: 原始帧数据。

    Returns:
        (头部字典, 音频数据) 元组。
    """
    if len(data) < 2:
        return {}, b""
    header_length = int.from_bytes(data[:2], "big")
    if 2 + header_length > len(data):
        return {}, b""
    headers: Dict[bytes, bytes] = {}
    for line in data[2:2 + header_length].split(b"\r\n"):
        if b":" not in line:
            continue
        key, value = line.split(b":", 1)
        headers[key.strip()] = value.strip()
    return headers, data[2 + header_length:]


class Client:
    """Edge TTS 客户端协调器。"""

    def __init__(self) -> None:
        self._session: Optional[Any] = None
        self._account_states: Dict[str, Any] = {}
        self._candidates: List[Candidate] = []

    async def init_immediate(self, session: Any) -> None:
        """立即初始化，设置 session 并构建候选项。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        self._rebuild_candidates()
        logger.debug("edgetts 初始化完成")

    async def background_setup(self) -> None:
        """后台设置（TTS 平台无额外后台任务）。"""

    def _rebuild_candidates(self) -> None:
        """根据账号列表重建候选项。"""
        self._candidates = [
            Candidate(
                id=make_id("edgetts", (acc.key or "edge")[:12]),
                platform="edgetts",
                resource_id=(acc.key or "edge")[:12],
                models=list(acc.models),
                meta={"api_key": acc.key},
                **acc.caps,
            )
            for acc in ACCOUNTS
        ]

    def get_candidates(self) -> List[Candidate]:
        """返回当前候选项列表。

        Returns:
            候选项列表。
        """
        return list(self._candidates)

    def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。

        Args:
            count: 期望的候选数量。

        Returns:
            实际可用的候选数量。
        """
        return len(self._candidates)

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        **kw: Any,
    ) -> AsyncGenerator[Any, None]:
        """聊天补全（edge tts 不支持）。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用 thinking。
            search: 是否启用搜索。
            **kw: 额外参数。

        Raises:
            NotSupportedError: 始终抛出，因为 TTS 不支持聊天补全。
        """
        raise NotSupportedError("edgetts 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """语音合成。

        Args:
            candidate: 候选项。
            input_text: 输入文本。
            model: 模型名。
            voice: 声音名称。
            **kw: 额外参数。

        Returns:
            合成后的音频字节。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                audio = await self._run_tts_synthesis(input_text, voice)
                if audio:
                    return audio
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("edgetts 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc)
        if last_exc:
            raise last_exc
        raise RuntimeError("edgetts 未知错误")

    async def _run_tts_synthesis(self, text: str, voice: str) -> bytes:
        """执行 TTS 合成。

        Args:
            text: 待合成文本。
            voice: 声音名称。

        Returns:
            合成的音频字节。
        """
        voice = voice or DEFAULT_VOICE
        escaped_text = remove_incompatible_characters(text)

        connection_id = _connect_id()
        sec_ms_gec = _drm_generate_sec_ms_gec()
        wss_path = (
            "{}&ConnectionId={}&Sec-MS-GEC={}&Sec-MS-GEC-Version={}".format(
                WSS_PATH_BASE, connection_id, sec_ms_gec, SEC_MS_GEC_VERSION,
            )
        )

        headers = build_wss_headers()
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())
        ws = _RawWebSocket.connect(
            host=WSS_HOST,
            port=443,
            path=wss_path,
            extra_headers=headers,
            ssl_ctx=ssl_ctx,
            timeout=15.0,
        )

        try:
            ts = _date_to_string()
            config_payload = (
                "X-Timestamp:{ts}\r\n"
                "Content-Type:application/json; charset=utf-8\r\n"
                "Path:speech.config\r\n"
                "X-RequestId:{rid}\r\n\r\n"
                '{{"context":{{"synthesis":{{"audio":{{'
                '"metadataoptions":{{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"false"}},'
                '"outputFormat":"audio-24khz-48kbitrate-mono-mp3"}}}}}}}}'
            ).format(ts=ts, rid=_connect_id())
            ws.send_text(config_payload)

            ssml = build_ssml(voice, "+0%", "+0%", "+0Hz", escaped_text)
            ssml_payload = (
                "X-RequestId:{rid}\r\n"
                "Content-Type:application/ssml+xml\r\n"
                "X-Timestamp:{ts}Z\r\n"
                "Path:ssml\r\n\r\n"
                "{ssml}"
            ).format(rid=_connect_id(), ts=ts, ssml=ssml)
            ws.send_text(ssml_payload)

            audio_chunks: bytearray = bytearray()
            while True:
                opcode, payload = ws.recv_message(timeout=30.0)
                if opcode == 0x2:
                    frame_headers, audio_data = _parse_tts_binary_frame(payload)
                    if frame_headers.get(b"Path") == b"audio" and audio_data:
                        audio_chunks.extend(audio_data)
                elif opcode == 0x1:
                    frame_headers, _ = _parse_tts_text_frame(payload)
                    if frame_headers.get(b"Path") == b"turn.end":
                        break
                elif opcode == 0x8:
                    break
            return bytes(audio_chunks)
        finally:
            ws.close()

    async def close(self) -> None:
        """关闭客户端。"""
