from __future__ import annotations

"""Qwen 平台适配器实现。

PlatformAdapter 接口实现，负责初始化、候选项管理、聊天补全、多模态与生命周期。
网络请求下沉至 ``.client``。

依赖方向：core/adaptercore -> core/client, core/constants（仅 core 内部）
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Union

import aiohttp

from src.core.dispatch.candidate import Candidate
from src.logger import get_logger
from src.platforms.base import PlatformAdapter
from src.platforms.qwen.core.constants import CAPS, MODELS, MODELS_PERSIST_PATH

logger = get_logger(__name__)


class QwenAdapter(PlatformAdapter):
    """Qwen 平台适配器。

    实现非阻塞初始化：init() 立即返回，后台 Task 完成登录等耗时操作。
    """

    def __init__(self) -> None:
        """初始化适配器内部状态。"""
        self._client: Any = None
        self._init_task: Any = None
        self._bg_task: Any = None

    @property
    def name(self) -> str:
        """平台标识名。

        Returns:
            平台名字符串。
        """
        return "qwen"

    @property
    def supported_models(self) -> List[str]:
        """支持的模型列表（内置 + 持久化合并去重）。"""

        def _merge(base: List[str], extra: List[str]) -> List[str]:
            merged: List[str] = []
            seen: set = set()
            for m in list(base) + list(extra):
                if not m:
                    continue
                if m in seen:
                    continue
                seen.add(m)
                merged.append(m)
            return merged

        # 优先使用客户端内存中的模型
        if getattr(self, "_client", None) and hasattr(self._client, "get_models"):
            try:
                models = self._client.get_models()
                if models:
                    return _merge(MODELS, models)
            except Exception as exc:
                logger.warning("读取客户端模型失败: %s", exc)
        # 回退读取持久化文件
        try:
            path = Path(MODELS_PERSIST_PATH)
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                persisted: List[str] = []
                if isinstance(data, dict):
                    persisted = data.get("models", []) or []
                elif isinstance(data, list):
                    persisted = data
                if persisted:
                    return _merge(MODELS, [str(m) for m in persisted])
        except Exception as exc:
            logger.warning("读取持久化模型失败: %s", exc)
        return list(MODELS)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """默认能力字典。

        Returns:
            能力字典。
        """
        return dict(CAPS)

    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器——立即返回，后台完成耗时操作。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        from src.platforms.qwen.core.client import QwenClient

        self._client = QwenClient()
        self._init_task = asyncio.ensure_future(
            self._client.init_immediate(session)
        )
        self._bg_task = asyncio.ensure_future(
            self._client.background_setup()
        )

    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项列表。

        Returns:
            候选项列表。
        """
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量。

        Args:
            count: 期望数量。

        Returns:
            当前实际可用数量。
        """
        if self._client is None:
            return 0
        return await self._client.ensure_candidates(count)

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
        """聊天补全，完全委托给 client。

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名。
            stream: 是否流式。
            thinking: 是否启用 thinking 模式。
            search: 是否启用搜索。
            **kw: 额外参数。

        Yields:
            str（文本增量）或 dict（thinking/usage/tool_calls）。
        """
        async for chunk in self._client.complete(
            candidate,
            messages,
            model,
            stream,
            thinking=thinking,
            search=search,
            **kw,
        ):
            yield chunk

    async def create_image(
        self,
        candidate: Candidate,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """图片生成：通过聊天通道抓取 tool_calls 事件。

        Args:
            candidate: 候选项。
            prompt: 图片描述。
            model: 模型名称。
            **kw: 额外参数。

        Returns:
            包含 created 和 data 的图片结果字典。
        """
        if self._client is None:
            return {"created": int(time.time()), "data": []}

        target_model = model or (
            candidate.models[0]
            if getattr(candidate, "models", [])
            else self.supported_models[0]
        )
        images: List[Dict[str, str]] = []

        async for chunk in self._client.complete(
            candidate,
            [{"role": "user", "content": prompt}],
            target_model,
            stream=True,
            thinking=False,
            search=False,
        ):
            if not (isinstance(chunk, dict) and "tool_calls" in chunk):
                continue
            calls = chunk.get("tool_calls") or []
            if not isinstance(calls, list):
                continue
            for call in calls:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                if fn.get("name") != "qwen.image_gen":
                    continue
                args_raw = fn.get("arguments", "")
                try:
                    args = json.loads(args_raw) if args_raw else {}
                except Exception:
                    args = {}
                if not isinstance(args, dict):
                    continue
                images.append(
                    {
                        "url": args.get("url") or "",
                        "local": args.get("local_path") or "",
                    }
                )

        return {
            "created": int(time.time()),
            "data": [
                {k: v for k, v in item.items() if v}
                for item in images
                if item.get("url")
            ],
        }

    async def edit_image(
        self,
        candidate: Candidate,
        image: bytes,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """图片编辑：上传原图并通过聊天通道抓取编辑后的 tool_calls 事件。

        Args:
            candidate: 候选项。
            image: 原始图片字节数据。
            prompt: 编辑描述。
            model: 模型名称。
            **kw: 额外参数（filename）。

        Returns:
            包含 created 和 data 的图片结果字典。
        """
        if self._client is None:
            return {"created": int(time.time()), "data": []}
        if not image:
            return {"created": int(time.time()), "data": []}

        target_model = model or (
            candidate.models[0]
            if getattr(candidate, "models", [])
            else self.supported_models[0]
        )
        filename = kw.get("filename") or "image.png"
        images: List[Dict[str, str]] = []

        async for chunk in self._client.complete(
            candidate,
            [{"role": "user", "content": prompt}],
            target_model,
            stream=True,
            thinking=False,
            search=False,
            upload_files=[(image, filename)],
        ):
            if not (isinstance(chunk, dict) and "tool_calls" in chunk):
                continue
            calls = chunk.get("tool_calls") or []
            if not isinstance(calls, list):
                continue
            for call in calls:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                if fn.get("name") != "qwen.image_gen":
                    continue
                args_raw = fn.get("arguments", "")
                try:
                    args = json.loads(args_raw) if args_raw else {}
                except Exception:
                    args = {}
                if not isinstance(args, dict):
                    continue
                images.append(
                    {
                        "url": args.get("url") or "",
                        "local": args.get("local_path") or "",
                    }
                )

        return {
            "created": int(time.time()),
            "data": [
                {k: v for k, v in item.items() if v}
                for item in images
                if item.get("url")
            ],
        }

    async def create_video(
        self,
        candidate: Candidate,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """视频生成：通过聊天通道抓取 tool_calls 事件。

        Args:
            candidate: 候选项。
            prompt: 视频描述。
            model: 模型名称。
            **kw: 额外参数。

        Returns:
            包含 created 和 data 的视频结果字典。
        """
        if self._client is None:
            return {"created": int(time.time()), "data": []}

        target_model = model or (
            candidate.models[0]
            if getattr(candidate, "models", [])
            else self.supported_models[0]
        )
        videos: List[Dict[str, str]] = []

        async for chunk in self._client.complete(
            candidate,
            [{"role": "user", "content": prompt}],
            target_model,
            stream=True,
            thinking=False,
            search=False,
        ):
            if not (isinstance(chunk, dict) and "tool_calls" in chunk):
                continue
            calls = chunk.get("tool_calls") or []
            if not isinstance(calls, list):
                continue
            for call in calls:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") or {}
                if not isinstance(fn, dict):
                    continue
                if fn.get("name") != "qwen.video_gen":
                    continue
                args_raw = fn.get("arguments", "")
                try:
                    args = json.loads(args_raw) if args_raw else {}
                except Exception:
                    args = {}
                if not isinstance(args, dict):
                    continue
                url = args.get("url") or ""
                if url:
                    videos.append({"url": url})

        return {
            "created": int(time.time()),
            "data": videos,
        }

    async def create_speech(
        self,
        candidate: Candidate,
        input_text: str,
        model: str,
        voice: str,
        **kw: Any,
    ) -> bytes:
        """TTS：委托客户端合成并返回 WAV 字节。

        Args:
            candidate: 候选项。
            input_text: 待合成文本。
            model: 模型名称。
            voice: 音色名称（当前平台暂不使用）。
            **kw: 额外参数。

        Returns:
            WAV 格式音频字节，失败返回空字节串。
        """
        if self._client is None:
            return b""

        token = candidate.meta.get("token", "")
        if not token:
            return b""

        target_model = model or (
            candidate.models[0]
            if getattr(candidate, "models", [])
            else self.supported_models[0]
        )

        audio_path = await self._client.synthesize_tts(
            input_text,
            token,
            model=target_model,
        )
        if not audio_path:
            return b""

        try:
            return Path(audio_path).read_bytes()
        except Exception:
            return b""

    async def close(self) -> None:
        """关闭适配器，取消后台任务，释放资源。"""
        for task in (self._init_task, self._bg_task):
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug("Qwen 后台任务已取消")
                except Exception as exc:
                    logger.warning("Qwen 后台任务关闭异常: %s", exc)
        if self._client is not None:
            await self._client.close()

    def set_proxy_enabled(self, enabled: bool) -> None:
        """设置 Qwen 平台的代理覆盖开关。

        只有在配置中允许的平台才能真正生效。

        Args:
            enabled: True 强制使用代理，False 强制不使用。
        """
        if not self.is_proxy_allowed():
            return
        if self._client is not None:
            self._client.set_proxy_enabled(enabled)

    def is_proxy_allowed(self) -> bool:
        """返回 Qwen 平台是否被允许使用代理切换。"""
        from src.core.config import get_config
        cfg = get_config()
        return cfg.platforms_proxy.is_platform_enabled(self.name)

    def is_proxy_enabled(self) -> bool:
        """返回 Qwen 平台当前是否启用代理覆盖。

        Returns:
            是否启用代理。
        """
        if not self.is_proxy_allowed():
            return False
        if self._client is not None:
            return self._client.is_proxy_enabled()
        return False


# 通用别名，供 adapter.py / util.py 统一导出
Adapter = QwenAdapter
