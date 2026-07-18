"""tts 模块 — Provider 适配器层。

职责：
    作为 Provider-Evo 项目标准模块，提供 tts 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



import ssl
from typing import Any, Tuple, Dict

import certifi

from .constants import (
    DEFAULT_FORMAT,
    DEFAULT_PITCH,
    DEFAULT_RATE,
    DEFAULT_VOICE,
    DEFAULT_VOLUME,
    MAX_RETRIES,
    SEC_MS_GEC_VERSION,
    WSS_HOST,
    WSS_PATH_BASE,
)
from .drm import (
    build_ssml,
    build_wss_headers,
    connect_id,
    date_to_string,
    generate_sec_ms_gec,
    parse_tts_binary_frame,
    parse_tts_text_frame,
    remove_incompatible_characters,
)
from .websocket import _RawWebSocket


def do_tts(
    text: str,
    voice: str = "",
) -> bytes:
    """调用 Edge TTS 服务。

    Args:
        text: 合成文本。
        voice: 声音名称。

    Returns:
        音频字节数据。

    Raises:
        RuntimeError: 请求失败时抛出。
    """
    voice = voice or DEFAULT_VOICE
    escaped_text = remove_incompatible_characters(text)

    connection_id = connect_id()
    sec_ms_gec = generate_sec_ms_gec()
    wss_path = (
        "{}&ConnectionId={}&Sec-MS-GEC={}&Sec-MS-GEC-Version={}"
    ).format(WSS_PATH_BASE, connection_id, sec_ms_gec, SEC_MS_GEC_VERSION)

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
        ts = date_to_string()
        config_payload = (
            "X-Timestamp:{ts}\r\n"
            "Content-Type:application/json; charset=utf-8\r\n"
            "Path:speech.config\r\n"
            "X-RequestId:{rid}\r\n\r\n"
            '{{"context":{{"synthesis":{{"audio":{{'
            '"metadataoptions":{{"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"false"}},'
            '"outputFormat":"{format}"}}}}}}}}'
        ).format(ts=ts, rid=connect_id(), format=DEFAULT_FORMAT)
        ws.send_text(config_payload)

        ssml = build_ssml(voice, DEFAULT_RATE, DEFAULT_VOLUME, DEFAULT_PITCH, escaped_text)
        ssml_payload = (
            "X-RequestId:{rid}\r\n"
            "Content-Type:application/ssml+xml\r\n"
            "X-Timestamp:{ts}Z\r\n"
            "Path:ssml\r\n\r\n"
            "{ssml}"
        ).format(rid=connect_id(), ts=ts, ssml=ssml)
        ws.send_text(ssml_payload)

        audio_chunks: bytearray = bytearray()
        while True:
            opcode, payload = ws.recv_message(timeout=30.0)
            if opcode == 0x2:
                frame_headers, audio_data = parse_tts_binary_frame(payload)
                if frame_headers.get(b"Path") == b"audio" and audio_data:
                    audio_chunks.extend(audio_data)
            elif opcode == 0x1:
                frame_headers, _ = parse_tts_text_frame(payload)
                if frame_headers.get(b"Path") == b"turn.end":
                    break
            elif opcode == 0x8:
                break
        return bytes(audio_chunks)
    finally:
        ws.close()

# =======================================================================
# 重导出 — 同包内协同模块的公共符号（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

__all__ = [
]

# =======================================================================
# 相关模块
# =======================================================================
#
# 同包内协同模块通过 ``from .X import Y`` 重导出，外部调用方无需感知包内布局。
# 若需新增协同模块，请将对应 ``.py`` 文件放在本模块同级目录，并在末尾追加重导出。
#
# 设计原则：
#   1. 每个文件只承担一个明确的职责（单一职责原则）。
#   2. 跨文件依赖只通过显式 import 表达；避免隐式全局状态。
#   3. 公共 API 集中在 ``__all__``；私有符号以下划线开头。
#   4. 模块 docstring 描述用途、依赖、修改指引，作为运行时自描述文档。
#
# 错误处理：
#   - 错误一律 raise，不在底层吞掉（见 ``AGENTS.md`` Hard Constraints）。
#   - 上层 ``plugin.py`` / ``client.py`` 统一处理重试与 fallback。
#
# 测试：
#   - ``tests/`` 子目录覆盖本模块的所有公共函数。
#   - 覆盖率门禁为 90%（见 ``pyproject.toml``）。
#
# 文档：
#   - 用户文档位于 ``docs-src/plugins/``。
#   - 架构决策写入 ``PROJECT_DECISIONS.md``。
#
# 重构策略：
#   - 单文件超过 400 行时，提取子模块并通过 ``__init__.py`` 重导出。
#   - 跨多个 Provider 共享的逻辑抽取至 ``src/core/``；本文件不重复实现。
#
# 兼容：
#   - 旧路径 ``from .module import *`` 仍可用（见 ``__all__``）。
#   - 删除本文件前请先在 ``plugin.py`` 中确认无引用。
#
# 验证：
#   - 修改后运行 ``python -m py_compile`` 确认语法。
#   - 运行 ``pytest tests/`` 确认行为。
#   - 运行 ``python .claude/scripts/check_dir_limit.py`` 确认行数约束。
# =======================================================================
# 重导出 — 同包协同模块（保持外部 ``from .. import`` 路径稳定）
# =======================================================================

from .adaptercore import (
    EdgeTtsAdapter,
)

from .client import (
    Client,
)
__all__ = [
    "EdgeTtsAdapter",
    "Client",
]
