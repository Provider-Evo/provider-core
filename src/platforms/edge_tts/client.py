from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import secrets
import socket
import ssl
import struct
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import certifi

from src.core.candidate import Candidate, make_id
from src.core.errors import NotSupportedError
from src.platforms.edge_tts.accounts import API_KEYS

logger = logging.getLogger(__name__)

CHROMIUM_FULL_VERSION: str = "143.0.3650.75"
CHROMIUM_MAJOR_VERSION: str = CHROMIUM_FULL_VERSION.split(".", 1)[0]
SEC_MS_GEC_VERSION: str = f"1-{CHROMIUM_FULL_VERSION}"
TRUSTED_CLIENT_TOKEN: str = "6A5AA1D4EAFF4E9FB37E23D68491D6F4"
WSS_HOST: str = "speech.platform.bing.com"
WSS_PATH_BASE: str = (
    "/consumer/speech/synthesize/readaloud/edge/v1"
    "?TrustedClientToken={}".format(TRUSTED_CLIENT_TOKEN)
)
DEFAULT_VOICE: str = "zh-CN-XiaoxiaoNeural"
WIN_EPOCH: int = 11644473600
S_TO_NS: float = 1e9
MAX_RETRIES: int = 3

BASE_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/{mv}.0.0.0 Safari/537.36 Edg/{mv}.0.0.0"
    ).format(mv=CHROMIUM_MAJOR_VERSION),
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
}

WSS_HANDSHAKE_HEADERS: Dict[str, str] = {
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
    "Origin": "chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold",
}
WSS_HANDSHAKE_HEADERS.update(BASE_HEADERS)


class _RawWebSocket:
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
                "host",
                "upgrade",
                "connection",
                "sec-websocket-key",
                "sec-websocket-version",
                "sec-websocket-extensions",
                "sec-websocket-protocol",
            ):
                continue
            request_lines.append(f"{k}: {v}")
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
            raise RuntimeError(f"WebSocket handshake failed: {first_line.strip()}")

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
        self._send_frame(0x1, text.encode("utf-8"))

    def _recv_bytes(self, n: int, timeout: float) -> bytes:
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
        if not self._closed:
            try:
                self._send_frame(0x8, b"")
            except Exception:
                pass
            self._closed = True
        try:
            self._sock.close()
        except Exception:
            pass


# === 工具函数 ===

def _drm_generate_sec_ms_gec() -> str:
    ticks = datetime.now(timezone.utc).timestamp()
    ticks += WIN_EPOCH
    ticks -= ticks % 300
    ticks *= S_TO_NS / 100
    return hashlib.sha256(f"{ticks:.0f}{TRUSTED_CLIENT_TOKEN}".encode("ascii")).hexdigest().upper()


def _connect_id() -> str:
    return uuid.uuid4().hex


def _date_to_string() -> str:
    return time.strftime("%a %b %d %Y %H:%M:%S GMT+0000 (Coordinated Universal Time)", time.gmtime())


def _remove_incompatible_characters(string: str) -> str:
    chars = list(string)
    for idx, ch in enumerate(chars):
        code = ord(ch)
        if (0 <= code <= 8) or (11 <= code <= 12) or (14 <= code <= 31):
            chars[idx] = " "
    return "".join(chars)


def _mkssml(voice: str, rate: str, volume: str, pitch: str, text: str) -> str:
    return (
        "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'>"
        "<voice name='{voice}'><prosody pitch='{pitch}' rate='{rate}' volume='{volume}'>"
        "{text}</prosody></voice></speak>"
    ).format(voice=voice, pitch=pitch, rate=rate, volume=volume, text=text)


def _parse_tts_text_frame(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    sep = data.find(b"\r\n\r\n")
    if sep < 0:
        return {}, b""
    headers: Dict[bytes, bytes] = {}
    for line in data[:sep].split(b"\r\n"):
        if b":" not in line:
            continue
        key, value = line.split(b":", 1)
        headers[key.strip()] = value.strip()
    return headers, data[sep + 4 :]


def _parse_tts_binary_frame(data: bytes) -> Tuple[Dict[bytes, bytes], bytes]:
    if len(data) < 2:
        return {}, b""
    header_length = int.from_bytes(data[:2], "big")
    if 2 + header_length > len(data):
        return {}, b""
    headers: Dict[bytes, bytes] = {}
    for line in data[2 : 2 + header_length].split(b"\r\n"):
        if b":" not in line:
            continue
        key, value = line.split(b":", 1)
        headers[key.strip()] = value.strip()
    return headers, data[2 + header_length :]


def _build_wss_headers() -> Dict[str, str]:
    h = dict(WSS_HANDSHAKE_HEADERS)
    h["Cookie"] = "muid={};".format(secrets.token_hex(16).upper())
    return h


class EdgeTtsClient:
    def __init__(self) -> None:
        self._session: Optional[Any] = None

    async def init(self, session: Any) -> None:
        self._session = session
        logger.info("edge_tts 初始化完成")

    async def candidates(self) -> List[Candidate]:
        from src.platforms.edge_tts.adapter import CAPS, MODELS
        return [
            Candidate(
                id=make_id("edge_tts"),
                platform="edge_tts",
                resource_id=(key or "edge")[:12],
                models=MODELS,
                meta={"api_key": key},
                **CAPS,
            )
            for key in API_KEYS
        ]

    async def ensure_candidates(self, count: int) -> int:
        return len(API_KEYS)

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
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        raise NotSupportedError("edge_tts 不支持 chat 补全")

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
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
                logger.warning("edge_tts 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, exc)
        if last_exc:
            raise last_exc
        raise RuntimeError("edge_tts 未知错误")

    async def _run_tts_synthesis(self, text: str, voice: str) -> bytes:
        voice = voice or DEFAULT_VOICE
        escaped_text = _remove_incompatible_characters(text)

        connection_id = _connect_id()
        sec_ms_gec = _drm_generate_sec_ms_gec()
        wss_path = (
            f"{WSS_PATH_BASE}&ConnectionId={connection_id}&Sec-MS-GEC={sec_ms_gec}&Sec-MS-GEC-Version={SEC_MS_GEC_VERSION}"
        )

        headers = _build_wss_headers()
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
                "{{\"context\":{{\"synthesis\":{{\"audio\":{{"
                "\"metadataoptions\":{{\"sentenceBoundaryEnabled\":\"false\",\"wordBoundaryEnabled\":\"false\"}},"
                "\"outputFormat\":\"audio-24khz-48kbitrate-mono-mp3\"}}}}}}}}"
            ).format(ts=ts, rid=_connect_id())
            ws.send_text(config_payload)

            ssml = _mkssml(voice, "+0%", "+0%", "+0Hz", escaped_text)
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
        return
