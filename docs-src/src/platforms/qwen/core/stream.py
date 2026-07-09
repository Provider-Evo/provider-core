"""聊天 SSE 流处理器。

将原 ``client._do_request`` 中的 SSE 解析循环抽离为一个独立的 **有状态**
异步生成器：

- 输入：原始 :class:`aiohttp.ClientResponse`
- 输出：``str``（文本增量）/ ``dict``（``thinking`` / ``usage`` /
  ``tool_calls``）

媒体事件（图片 / 视频）通过注入的下载器异步落地为本地文件，再转换为
``tool_calls`` 协议向上 yield。
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

import aiohttp

from src.logger import get_logger
from .sse import parse_sse_event

logger = get_logger(__name__)


class StreamHandler:
    """SSE 流处理器（一次性使用，非线程安全）。

    Args:
        download_image: 协程 ``(url) -> Optional[local_path]``；用于把
            图片事件转成本地路径并附加到 ``tool_calls.arguments``。
    """

    def __init__(
        self,
        download_image: Callable[[str], Awaitable[Optional[str]]],
    ) -> None:
        self._download_image = download_image
        # 流结束后由外部读取的状态
        self.last_response_id: Optional[str] = None
        # 内部累积态
        self._thinking_count: int = 0
        self._tail: bytes = b""

    async def stream(
        self,
        resp: aiohttp.ClientResponse,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """主循环：消费 ``resp.content``，yield 增量协议元素。

        Args:
            resp: 已发起的 SSE 响应（HTTP 200）。

        Yields:
            ``str`` 或 ``dict``。

        Raises:
            RuntimeError: 服务器以 ``error`` 事件返回。
        """
        self.last_response_id = None
        self._thinking_count = 0
        self._tail = b""
        buffer = b""

        # 预读首块：确保连接握手成功且立刻进入读循环
        first_chunk = await resp.content.readany()
        if first_chunk:
            buffer = first_chunk
            async for item in self._process_buffer(buffer):
                yield item
            buffer = self._tail  # 由 _process_buffer 写入尾部残片

        # 主读循环
        async for raw in resp.content.iter_any():
            if not raw:
                continue
            buffer += raw
            async for item in self._process_buffer(buffer):
                yield item
            buffer = self._tail

    # ---------------------------------------------------------------- 内部
    async def _process_buffer(
        self,
        buffer: bytes,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """按行切分并处理 SSE 数据；尾部不完整行存到 ``self._tail``。"""
        lines = buffer.split(b"\n")
        self._tail = lines[-1]
        for line_bytes in lines[:-1]:
            line = line_bytes.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data_str = line[5:].lstrip()
            if not data_str or data_str == "[DONE]":
                continue
            event = parse_sse_event(data_str)
            if event is None:
                continue
            async for item in self._dispatch(event):
                yield item

    async def _dispatch(
        self,
        event: Dict[str, Any],
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """按事件类型分发，yield 0..N 个协议元素。"""
        evt_type = event.get("type", "")
        if evt_type == "error":
            raise RuntimeError(
                "Qwen 服务器错误: {}".format(event.get("message", ""))
            )
        async for item in self._dispatch_by_type(evt_type, event):
            yield item
        # 部分事件可能同时携带 usage
        if "usage" in event and evt_type != "usage":
            yield {"usage": event["usage"]}

    async def _dispatch_by_type(
        self,
        evt_type: str,
        event: Dict[str, Any],
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """按 ``evt_type`` 路由到对应 handler；未知类型静默忽略。"""
        if evt_type == "response_created":
            self.last_response_id = event.get("response_id")
            return
        handler = self._HANDLERS.get(evt_type)
        if handler is None:
            return
        async for item in handler(self, event):
            yield item

    async def _on_answer(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理 ``answer`` 事件。"""
        text = self._strip_think_tags(event.get("content", ""))
        if text:
            yield text

    async def _on_think_raw(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理 ``think`` 事件（raw 模式思考内容）。"""
        content = event.get("content", "")
        if content:
            yield {"thinking": content}

    async def _on_thinking(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理 ``thinking_summary`` 事件。"""
        for piece in self._iter_thinking_pieces(event):
            yield {"thinking": piece}

    async def _on_image_gen_tool(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理批量图片生成事件。"""
        calls = await self._build_image_calls(event.get("urls", []))
        if calls:
            yield {"tool_calls": calls}

    async def _on_image_gen(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理单图生成事件。"""
        url = event.get("content", "")
        if url:
            call = await self._build_single_image_call(url)
            yield {"tool_calls": [call]}

    async def _on_video_gen(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理视频生成事件。"""
        url = event.get("content", "")
        if url:
            yield {"tool_calls": [self._build_video_call(url)]}

    async def _on_usage(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理用量事件。"""
        yield {"usage": event.get("data", {})}

    async def _on_other(
        self, event: Dict[str, Any]
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """处理未知 phase 的兜底事件。"""
        content = self._strip_think_tags(event.get("content", ""))
        if content:
            yield content

    # 事件类型 -> 处理方法 分发表
    _HANDLERS = {
        "answer": _on_answer,
        "think": _on_think_raw,
        "thinking_summary": _on_thinking,
        "image_gen_tool": _on_image_gen_tool,
        "image_gen": _on_image_gen,
        "video_gen": _on_video_gen,
        "usage": _on_usage,
        "other": _on_other,
    }

    # ------------------------------------------------------------ 辅助函数
    @staticmethod
    def _strip_think_tags(content: str) -> str:
        """移除 Qwen 偶发出现的 ``<think>`` / ``</think>`` 标记。"""
        return content.replace("<think>", "").replace("</think>", "")

    def _iter_thinking_pieces(
        self,
        event: Dict[str, Any],
    ) -> List[str]:
        """从 ``thinking_summary`` 事件中提取本次新增的思考片段。"""
        if event.get("status", "") != "typing":
            return []
        extra = event.get("extra", {})
        if not extra:
            return []
        titles = extra.get("summary_title", {}).get("content", [])
        thoughts = extra.get("summary_thought", {}).get("content", [])
        count = max(len(titles), len(thoughts))
        pieces: List[str] = []
        for i in range(self._thinking_count, count):
            title = titles[i] if i < len(titles) else ""
            thought = thoughts[i] if i < len(thoughts) else ""
            pieces.append(
                "{}: {}".format(title, thought) if title else thought
            )
        self._thinking_count = count
        return pieces

    async def _build_image_calls(
        self,
        urls: List[str],
    ) -> List[Dict[str, Any]]:
        """并按顺序为每个 URL 构造图片 ``tool_call``。"""
        return await asyncio.gather(*[self._build_single_image_call(url) for url in urls])

    async def _build_single_image_call(
        self,
        img_url: str,
    ) -> Dict[str, Any]:
        """下载图片并组装 ``qwen.image_gen`` 调用。"""
        local_path = await self._download_image(img_url)
        args: Dict[str, str] = {"url": img_url}
        if local_path:
            args["local_path"] = local_path
        return _wrap_tool_call("qwen.image_gen", args)

    @staticmethod
    def _build_video_call(video_url: str) -> Dict[str, Any]:
        """构造 ``qwen.video_gen`` 调用。"""
        return _wrap_tool_call("qwen.video_gen", {"url": video_url})


def _wrap_tool_call(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """统一构造 OpenAI 兼容的 ``tool_call`` 字典。"""
    return {
        "id": "call_{}".format(uuid.uuid4().hex[:12]),
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args, ensure_ascii=False),
        },
    }


def parse_response_id_from_placeholder(  # noqa: D401
    data_str: str,
) -> Tuple[Optional[str], str]:
    """工具：从占位聊天的 SSE 行中解析 ``response_id`` 与 ``answer`` 片段。

    Args:
        data_str: 已去除 ``data:`` 前缀的 SSE 数据行。

    Returns:
        ``(response_id, answer_chunk)``。若该行不包含相应字段则返回
        ``(None, "")``。
    """
    event = parse_sse_event(data_str)
    if event is None:
        return None, ""
    if event.get("type") == "response_created":
        return event.get("response_id"), ""
    if event.get("type") == "answer":
        return None, event.get("content", "")
    return None, ""
