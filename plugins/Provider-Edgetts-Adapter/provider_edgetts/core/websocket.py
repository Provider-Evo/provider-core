from __future__ import annotations

"""edgetts 原始 WebSocket 实现。"""

import base64
import hashlib
import secrets
import socket
import ssl
import struct
from typing import Dict, Tuple

from src.logger import get_logger

_logger = get_logger(__name__)


class _RawWebSocket:
    """原始 WebSocket 连接实现。"""

    def __init__(self, sock: ssl.SSLSocket) -> None:
        """初始化 WebSocket。

        Args:
            sock: SSL 包装的 socket。
        """
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
            timeout: 超时时间（秒）。

        Returns:
            WebSocket 实例。

        Raises:
            ConnectionError: 连接关闭时抛出。
            RuntimeError: 握手失败时抛出。
        """
        raw_sock = socket.create_connection((host, port), timeout=timeout)
        tls_sock = ssl_ctx.wrap_socket(raw_sock, server_hostname=host)
        tls_sock.settimeout(timeout)

        ws_key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
        request_lines: list[str] = [
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
            opcode: 操作码。
            payload: 载荷数据。
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
            text: 文本内容。
        """
        self._send_frame(0x1, text.encode("utf-8"))

    def _recv_bytes(self, n: int, timeout: float) -> bytes:
        """接收指定字节数。

        Args:
            n: 字节数。
            timeout: 超时时间。

        Returns:
            接收到的字节数据。

        Raises:
            ConnectionError: 连接关闭时抛出。
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
            timeout: 超时时间。

        Returns:
            元组 (操作码, 载荷数据, 是否完整帧)。
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
        """接收完整消息。

        Args:
            timeout: 超时时间。

        Returns:
            元组 (操作码, 载荷数据)。
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
                _logger.debug("发送 WebSocket 关闭帧失败: %s", exc)
            self._closed = True
        try:
            self._sock.close()
        except Exception as exc:
            _logger.debug("关闭 WebSocket 连接失败: %s", exc)
