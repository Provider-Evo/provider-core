"""AItianhu2 对话服务模块。

提供对话 prepare、SSE 流式对话、SSE 解析、图像解析和对话清理。
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import aiohttp

from src.logger import get_logger
from .constants import (
    BASE_URL,
    BUILD_HASH,
    USER_AGENT,
)
from .headers import build_headers

logger = get_logger(__name__)


_COOLDOWN_RE = re.compile(r"(?:please\s+)?wait\s+(\d+)\s+seconds?", re.IGNORECASE)


def _parse_cooldown(body: str, default: int = 180) -> int:
    """从上游 429 body 中解析冷却秒数；未匹配则返回 ``default``。"""
    if not body:
        return default
    m = _COOLDOWN_RE.search(body)
    if m:
        try:
            return max(int(m.group(1)), 1) + 5  # 多留 5s 余量
        except ValueError:
            return default
    return default


class RateLimitError(Exception):
    """上游 429 限流异常，携带冷却秒数供上层做账号级退避。"""

    def __init__(
        self,
        message: str,
        *,
        cooldown: int = 180,
        body: str = "",
    ) -> None:
        super().__init__(message)
        self.cooldown = cooldown
        self.body = body


class ChatService:
    """对话会话服务。

    负责对话 prepare、SSE 流式请求、响应解析、
    图像资产下载和对话清理。
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
    ) -> None:
        """初始化对话服务。

        Args:
            session: 共享的 aiohttp ClientSession。
            proxy_resolver: 代理解析回调。
        """
        self._session = session
        self._resolve_proxy = proxy_resolver

    async def prepare(
        self,
        device_id: str,
        api_key: str,
        model: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        system_hints: Optional[List[str]] = None,
        *,
        account_id: str = "",
    ) -> Dict[str, Any]:
        """POST /backend-api/f/conversation/prepare — 返回 conduit_token。

        Args:
            device_id: 设备标识。
            api_key: API key。
            model: 模型名。
            attachments: 附件列表（可选）。
            system_hints: 服务端提示列表（可选），如 ``["picture_v2"]``
                          用于激活图像生成模式。
            account_id: 动态 ``chatgpt-account-id``（可选）。

        Returns:
            服务器响应字典。
        """
        body: Dict[str, Any] = {
            "action": "next",
            "fork_from_shared_post": False,
            "parent_message_id": "client-created-root",
            "model": model,
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "system_hints": system_hints or [],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {"app_name": "3h96y9.aitianhu2.top"},
        }
        if attachments:
            body["attachments"] = attachments

        headers = {
            **build_headers(device_id),
            "Authorization": f"Bearer {api_key}",
            "x-conduit-token": "no-token",
        }
        if account_id:
            headers["chatgpt-account-id"] = account_id
        async with self._session.post(
            f"{BASE_URL}/backend-api/f/conversation/prepare",
            headers=headers,
            json=body,
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def stream(
        self,
        device_id: str,
        api_key: str,
        model: str,
        message: str,
        chat_token: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        system_hints: Optional[List[str]] = None,
        conduit_token: Optional[str] = None,
        *,
        account_id: str = "",
    ) -> Dict[str, Any]:
        """POST /backend-api/f/conversation — SSE 流式对话。

        Args:
            device_id: 设备标识。
            api_key: API key。
            model: 模型名。
            message: 用户消息文本。
            chat_token: 哨兵 chat token。
            attachments: 附件列表（可选）。
            system_hints: 服务端提示列表（可选），如 ``["picture_v2"]``。
            conduit_token: ``/conversation/prepare`` 返回的 conduit_token（可选），
                          用于激活服务端 conduit 通道。

        Returns:
            {"text", "image_assets", "conversation_id", "message_id", "title"}
        """
        message_id = str(uuid.uuid4())

        content_parts: List[Any] = []
        if attachments:
            for att in attachments:
                if att.get("width") is not None and att.get("height") is not None:
                    content_parts.append({
                        "content_type": "image_asset_pointer",
                        "asset_pointer": f"sediment://{att['id']}",
                        "size_bytes": att.get("size"),
                        "width": att.get("width"),
                        "height": att.get("height"),
                    })
        content_parts.append(message)

        has_image_part = any(isinstance(p, dict) for p in content_parts)
        msg_meta: Dict[str, Any] = {
            "developer_mode_connector_ids": [],
            "selected_connector_ids": [],
            "selected_sync_knowledge_store_ids": [],
            "selected_sources": [],
            "selected_github_repos": [],
            "selected_all_github_repos": False,
            "serialization_metadata": {"custom_symbol_offsets": []},
        }
        if attachments:
            msg_meta["attachments"] = attachments

        body: Dict[str, Any] = {
            "action": "next",
            "messages": [{
                "id": message_id,
                "author": {"role": "user"},
                "create_time": time.time(),
                "content": {
                    "content_type": (
                        "multimodal_text" if has_image_part else "text"
                    ),
                    "parts": content_parts,
                },
                "metadata": msg_meta,
            }],
            "parent_message_id": "client-created-root",
            "model": model,
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "enable_message_followups": True,
            "system_hints": system_hints or [],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {
                "is_dark_mode": True,
                "time_since_loaded": 20,
                "page_height": 681,
                "page_width": 715,
                "pixel_ratio": 1,
                "screen_height": 1080,
                "screen_width": 1920,
                "app_name": "3h96y9.aitianhu2.top",
            },
            "paragen_cot_summary_display_override": "allow",
            "force_parallel_switch": "auto",
        }
        if system_hints:
            body["client_prepare_state"] = "success"

        headers = {
            **build_headers(device_id),
            "Authorization": f"Bearer {api_key}",
            "accept": "text/event-stream",
            "oai-echo-logs": "0,6655,3,17963,1,19482",
            "openai-sentinel-chat-requirements-token": chat_token,
        }
        if account_id:
            headers["chatgpt-account-id"] = account_id
        if conduit_token:
            headers["x-conduit-token"] = conduit_token

        raw_lines: List[bytes] = []
        fallback_needed = False
        try:
            async with self._session.post(
                f"{BASE_URL}/backend-api/f/conversation",
                headers=headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=120),
            ) as resp:
                if resp.status == 500:
                    fallback_needed = True
                elif resp.status == 429:
                    # 上游限速：解析冷却秒数后以结构化异常抛出，
                    # 由 client.py 重试循环做账号级退避。
                    err_text = await resp.text()
                    cooldown = _parse_cooldown(err_text)
                    logger.warning(
                        "AItianhu2: /f/conversation 429 限流，冷却 %ds；body=%r",
                        cooldown, err_text[:200],
                    )
                    raise RateLimitError(
                        "429 rate limit",
                        cooldown=cooldown,
                        body=err_text,
                    )
                else:
                    resp.raise_for_status()
                    async for line in resp.content:
                        raw_lines.append(line)
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            logger.warning(
                "AItianhu2: /f/conversation 连接失败，回退到旧端点: %s", exc,
            )
            fallback_needed = True

        if fallback_needed:
            raw_lines.clear()
            legacy_headers = {
                **build_headers(device_id),
                "Authorization": f"Bearer {api_key}",
                "accept": "text/event-stream",
                "openai-sentinel-chat-requirements-token": chat_token,
            }
            if account_id:
                legacy_headers["chatgpt-account-id"] = account_id
            async with self._session.post(
                f"{BASE_URL}/backend-api/conversation",
                headers=legacy_headers,
                json=body,
                timeout=aiohttp.ClientTimeout(total=180),
            ) as resp:
                if resp.status == 429:
                    err_text = await resp.text()
                    cooldown = _parse_cooldown(err_text)
                    logger.warning(
                        "AItianhu2: /conversation 429 限流，冷却 %ds；body=%r",
                        cooldown, err_text[:200],
                    )
                    raise RateLimitError(
                        "429 rate limit",
                        cooldown=cooldown,
                        body=err_text,
                    )
                resp.raise_for_status()
                async for line in resp.content:
                    raw_lines.append(line)

        return parse_sse_lines(raw_lines)

    async def resolve_image(
        self,
        asset_pointer: str,
        conversation_id: str = "",
        device_id: str = "",
        *,
        account_id: str = "",
    ) -> Dict[str, Any]:
        """解析 sediment:// -> 下载图像并保存。

        Args:
            asset_pointer: 图像资产指针。
            conversation_id: 会话 ID。
            device_id: 设备标识。
            account_id: 动态 ``chatgpt-account-id``（可选）。

        Returns:
            {"local_path": str} 或 {"local_path": asset_pointer}（失败时）。
        """
        if not asset_pointer or not asset_pointer.startswith("sediment://"):
            return {"local_path": asset_pointer}

        file_id = asset_pointer.replace("sediment://", "")
        h = {
            "accept": "*/*",
            "referer": f"{BASE_URL}/c/{conversation_id}",
            "user-agent": USER_AGENT,
        }
        if account_id:
            h["chatgpt-account-id"] = account_id
        if device_id:
            h["oai-device-id"] = device_id

        async with self._session.get(
            f"{BASE_URL}/backend-api/files/download/{file_id}",
            headers=h,
            params={"conversation_id": conversation_id, "inline": "false"},
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("download_url"):
                    dl_url = data["download_url"]
                    if not dl_url.startswith("http"):
                        dl_url = BASE_URL + ("" if dl_url.startswith("/") else "/") + dl_url
                    async with self._session.get(
                        dl_url,
                        headers={"accept": "*/*", "user-agent": USER_AGENT},
                        timeout=aiohttp.ClientTimeout(total=60),
                    ) as resp2:
                        if resp2.status == 200:
                            content = await resp2.read()
                            fname = (
                                f"image_{hashlib.md5(file_id.encode()).hexdigest()[:12]}.png"
                            )
                            fpath = str(
                                Path(__file__).parent.parent.parent.parent.parent
                                / "generated"
                                / fname
                            )
                            os.makedirs(os.path.dirname(fpath), exist_ok=True)
                            Path(fpath).write_bytes(content)
                            return {
                                "local_path": fpath,
                                "size_bytes": len(content),
                            }

        return {"local_path": asset_pointer}

    async def cleanup(
        self,
        device_id: str,
        api_key: str,
        conversation_id: str,
        *,
        account_id: str = "",
    ) -> None:
        """对话清理：DELETE 优先，降级 PATCH hide。

        Args:
            device_id: 设备标识。
            api_key: API key。
            conversation_id: 会话 ID。
            account_id: 动态 ``chatgpt-account-id``（可选）。
        """
        if not conversation_id:
            return
        headers = {
            **build_headers(device_id),
            "Authorization": f"Bearer {api_key}",
        }
        if account_id:
            headers["chatgpt-account-id"] = account_id
        try:
            async with self._session.delete(
                f"{BASE_URL}/backend-api/conversation/{conversation_id}",
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status in (200, 204):
                    return
        except Exception as exc:
            logger.debug("AItianhu2 删除对话失败，尝试隐藏: %s", exc)
        try:
            async with self._session.patch(
                f"{BASE_URL}/backend-api/conversation/{conversation_id}",
                headers=headers,
                json={"is_visible": False},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                _ = resp.status
        except Exception as exc:
            logger.debug("AItianhu2 隐藏对话失败: %s", exc)


# ---------------------------------------------------------------------------
# v1 delta 状态机（1:1 还原上游 main.py:969-1197 / JS chunk Yte + Qte + dj）
# ---------------------------------------------------------------------------

_DELTA_SHORT_KEYS = [
    ("channel", "c"),
    ("path", "p"),
    ("op", "o"),
    ("value", "v"),
]


class _V1DeltaAccumulator:
    """按 channel 维护累积状态对象，逐条 apply v1 delta 事件。

    支持：
    * 短键 (``c``/``p``/``o``/``v``) 与长键 (``channel``/``path``/``op``/``value``)
      双向规范化
    * 字段继承：后续 delta 省略字段时从前一条继承
    * 完整 JSONPatch 操作：add / replace / append / patch / truncate / remove
    * 多通道并行（多个 message 在不同 channel 同时拼装）
    """

    def __init__(self) -> None:
        self._prev_by_channel: Dict[int, Any] = {}
        self._prev_delta: Dict[str, Any] = {
            "channel": 0,
            "op": "add",
            "path": "",
            "value": None,
        }

    def apply(self, raw: Any) -> Any:
        decoded = self._decode(raw)
        ch = decoded.get("channel", 0)
        prev = self._prev_by_channel.get(ch)
        result = self._apply_delta(prev, decoded)
        self._prev_by_channel[ch] = result
        return result

    # ---- 解码 --------------------------------------------------------

    def _decode(self, raw: Any) -> Dict[str, Any]:
        d = dict(raw) if isinstance(raw, dict) else {}
        for long_key, short_key in _DELTA_SHORT_KEYS:
            if short_key not in d and long_key not in d:
                if long_key in self._prev_delta:
                    d[short_key] = self._prev_delta[long_key]
        normalized: Dict[str, Any] = {}
        for long_key, short_key in _DELTA_SHORT_KEYS:
            if short_key in d:
                normalized[long_key] = d[short_key]
            elif long_key in d:
                normalized[long_key] = d[long_key]
        if normalized.get("op") == "patch" and isinstance(normalized.get("value"), list):
            normalized["value"] = [self._normalize_sub(v) for v in normalized["value"]]
        self._prev_delta = normalized
        return normalized

    @staticmethod
    def _normalize_sub(d: Any) -> Any:
        if not isinstance(d, dict):
            return d
        out: Dict[str, Any] = {}
        for long_key, short_key in _DELTA_SHORT_KEYS:
            if short_key in d:
                out[long_key] = d[short_key]
            elif long_key in d:
                out[long_key] = d[long_key]
        return out

    # ---- 路径解析 ----------------------------------------------------

    @staticmethod
    def _parse_path(path: str) -> List[Any]:
        if not path:
            return []
        if path.startswith("/"):
            path = path[1:]
        segments: List[Any] = []
        for seg in path.split("/"):
            seg = seg.replace("~1", "/").replace("~0", "~")
            if seg.isdigit():
                segments.append(int(seg))
            else:
                segments.append(seg)
        return segments

    # ---- 应用 delta --------------------------------------------------

    def _apply_delta(self, obj: Any, delta: Dict[str, Any]) -> Any:
        path = delta.get("path", "")
        op = delta.get("op", "add")
        value = delta.get("value")
        segments = self._parse_path(path)
        if not segments:
            return self._apply_op(obj, op, value)

        if obj is None:
            obj = {} if not isinstance(segments[0], int) else []

        target = obj
        for i, seg in enumerate(segments[:-1]):
            if isinstance(target, list):
                while len(target) <= seg:
                    target.append(None)
                if target[seg] is None:
                    next_seg = segments[i + 1]
                    target[seg] = [] if isinstance(next_seg, int) else {}
                target = target[seg]
            elif isinstance(target, dict):
                if seg not in target or target[seg] is None:
                    next_seg = segments[i + 1]
                    target[seg] = [] if isinstance(next_seg, int) else {}
                target = target[seg]
            else:
                return obj

        last = segments[-1]
        target = self._ensure_container(target, last)
        self._apply_op_at(target, last, op, value)
        return obj

    @staticmethod
    def _ensure_container(target: Any, key: Any) -> Any:
        if isinstance(target, list):
            while len(target) <= key:
                target.append(None)
        return target

    def _apply_op(self, obj: Any, op: str, value: Any) -> Any:
        if op in ("add", "replace"):
            return value
        if op == "append":
            if isinstance(obj, str) and isinstance(value, str):
                return obj + value
            if isinstance(obj, list):
                return obj + (value if isinstance(value, list) else [value])
            if isinstance(obj, dict) and isinstance(value, dict):
                obj.update(value)
                return obj
            return value
        if op == "patch":
            if isinstance(value, list):
                for sub in value:
                    obj = self._apply_delta(obj, sub)
            return obj
        if op == "truncate":
            if isinstance(obj, (str, list)):
                return obj[:value]
            return obj
        if op == "remove":
            return None
        return obj

    def _apply_op_at(self, target: Any, key: Any, op: str, value: Any) -> None:
        if op == "add":
            if isinstance(target, list):
                target.insert(key, value)
            else:
                target[key] = value
        elif op == "replace":
            target[key] = value
        elif op == "remove":
            if isinstance(target, list):
                if key < len(target):
                    target.pop(key)
            else:
                target.pop(key, None)
        elif op == "append":
            cur = (
                target[key]
                if isinstance(target, dict)
                else (target[key] if key < len(target) else None)
            )
            if isinstance(cur, str) and isinstance(value, str):
                target[key] = cur + value
            elif isinstance(cur, list):
                target[key] = cur + (value if isinstance(value, list) else [value])
            elif isinstance(cur, dict) and isinstance(value, dict):
                cur.update(value)
            else:
                target[key] = value
        elif op == "patch":
            if isinstance(value, list):
                cur = target[key]
                for sub in value:
                    cur = self._apply_delta(cur, sub)
                target[key] = cur
        elif op == "truncate":
            cur = target[key]
            if isinstance(cur, (str, list)):
                target[key] = cur[:value]

    # ---- 提取 --------------------------------------------------------

    def extract(self) -> Dict[str, Any]:
        """累积结果：
        * ``text``         —— 所有 channel 中 assistant/tool 消息的文本拼接
        * ``image_assets`` —— 图像资产列表
        * ``message_id``   —— 首个消息 ID
        """
        text = ""
        image_assets: List[Dict[str, Any]] = []
        msg_id: Optional[str] = None

        for _, obj in sorted(self._prev_by_channel.items()):
            if not isinstance(obj, dict):
                continue
            msg = obj.get("message", obj)
            if not isinstance(msg, dict):
                continue
            if msg.get("id") and not msg_id:
                msg_id = msg["id"]
            role = msg.get("author", {}).get("role", "")
            if role not in ("assistant", "tool"):
                continue
            content = msg.get("content", {})
            if not isinstance(content, dict):
                continue
            parts = content.get("parts", [])
            for part in parts:
                if isinstance(part, str) and part:
                    text += part
                elif isinstance(part, dict):
                    if part.get("content_type") == "image_asset_pointer":
                        image_assets.append({
                            "asset_pointer": part.get("asset_pointer"),
                            "width": part.get("width"),
                            "height": part.get("height"),
                            "size_bytes": part.get("size_bytes"),
                            "metadata": part.get("metadata", {}),
                        })
        return {
            "text": text,
            "image_assets": image_assets,
            "message_id": msg_id,
        }


# ---------------------------------------------------------------------------
# SSE 入口
# ---------------------------------------------------------------------------


def parse_sse_lines(raw_lines: List[bytes]) -> Dict[str, Any]:
    """解析 SSE 响应行。

    使用 v1 delta 状态机累积完整响应对象（1:1 还原上游 ``main.py::_parse_sse``）。
    同时保留对旧格式 ``/conversation`` 回退端点的处理——旧端点返回完整消息
    对象而非 JSONPatch delta。

    Args:
        raw_lines: 原始 SSE 行字节列表。

    Returns:
        {"text", "image_assets", "conversation_id", "message_id", "title"}
    """
    acc = _V1DeltaAccumulator()
    conversation_id: Optional[str] = None
    title: Optional[str] = None
    delta_started = False
    legacy_message_seen = False

    for raw in raw_lines:
        line = raw.decode("utf-8", errors="replace").strip()
        if not line or line.startswith("event:"):
            continue
        if line.startswith("data: "):
            ds = line[6:]
        elif line.startswith("data:"):
            ds = line[5:]
        else:
            continue
        if ds.strip() == "[DONE]":
            break
        try:
            data = json.loads(ds)
        except json.JSONDecodeError:
            continue

        if isinstance(data, str):
            if data in ("v1", "v2"):
                delta_started = True
            continue

        if not isinstance(data, dict):
            continue

        et = data.get("type")
        if et == "title_generation":
            title = data.get("title")
            continue
        if et in ("conversation_detail_metadata", "server_ste_metadata"):
            conversation_id = data.get("conversation_id", conversation_id)
            continue
        if et in (
            "resume_conversation_token",
            "message_marker",
            "message_stream_complete",
        ):
            cid = data.get("conversation_id")
            if cid:
                conversation_id = cid
            continue
        if data.get("conversation_id") and not delta_started:
            conversation_id = data["conversation_id"]

        # v1 delta 事件：短键 o/p/v/c 或长键 op/path/value/channel 任一出现
        # 即交给状态机。包含仅有 `v` 的情形——继承由 _decode 处理。
        if any(
            k in data
            for k in ("o", "op", "p", "path", "v", "value", "c", "channel")
        ):
            acc.apply(data)
            continue

        # 旧格式 /conversation 回退：完整消息对象
        if "message" in data and isinstance(data["message"], dict):
            legacy_message_seen = True
            msg = data["message"]
            role = msg.get("author", {}).get("role", "")
            if msg.get("id") and role in ("assistant", "tool"):
                # 通过状态机统一处理，复用路径解析 + 文本拼接逻辑
                acc.apply({
                    "op": "add",
                    "path": "",
                    "value": {"message": msg},
                })
            if role == "assistant":
                conversation_id = data.get("conversation_id", conversation_id)

    result = acc.extract()

    # 旧格式若从未看到 message 事件，至少保留 conversation_id/title
    if legacy_message_seen and not result.get("message_id"):
        result["message_id"] = None

    result["conversation_id"] = conversation_id
    result["title"] = title
    return result
