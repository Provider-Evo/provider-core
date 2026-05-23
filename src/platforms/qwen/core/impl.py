"""Qwen 适配器实现（公开类 :class:`QwenAdapter`）。

本模块承接 :class:`QwenAdapter` 的完整实现逻辑；通过 :mod:`.client`
执行实际的网络请求与多模态操作。:mod:`src.platforms.qwen.util` 从本
模块导入并对外重新暴露 :class:`QwenAdapter`。

依赖方向：``core/adapter_impl`` → ``core/client``、``core/constants``
（仅 ``core/`` 内部）。
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Union

import aiohttp

from src.core.candidate import Candidate
from src.logger import get_logger
from src.platforms.base import PlatformAdapter
from .constants import (
    CAPS,
    MODELS,
    MODELS_PERSIST_PATH,
)

logger = get_logger(__name__)


class QwenAdapter(PlatformAdapter):
    """Qwen 平台适配器。

    实现非阻塞初始化：:meth:`init` 立即返回；后台 ``Task`` 完成登录等
    耗时操作。
    """

    # ====================================================================
    # 构造与元数据
    # ====================================================================
    def __init__(self) -> None:
        """初始化适配器内部状态。"""
        self._client: Any = None
        self._init_task: Any = None
        self._bg_task: Any = None

    @property
    def name(self) -> str:
        """平台标识名。

        Returns:
            ``"qwen"``。
        """
        return "qwen"

    @property
    def supported_models(self) -> List[str]:
        """支持的模型列表（内置 + 客户端/持久化合并去重）。"""
        # 1) 客户端内存
        client_models = self._read_client_models()
        if client_models:
            return self._merge_models(MODELS, client_models)
        # 2) 持久化文件
        persisted = self._read_persisted_models()
        if persisted:
            return self._merge_models(MODELS, persisted)
        # 3) 内置回退
        return list(MODELS)

    @property
    def default_capabilities(self) -> Dict[str, bool]:
        """默认能力字典。"""
        return dict(CAPS)

    # ----------------------------------------------------------- 内部辅助
    def _read_client_models(self) -> List[str]:
        """从客户端读取动态模型列表（失败返回空列表）。"""
        client = self._client
        if client is None or not hasattr(client, "get_models"):
            return []
        try:
            models = client.get_models() or []
            return list(models)
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取客户端模型失败: %s", exc)
            return []

    @staticmethod
    def _read_persisted_models() -> List[str]:
        """从 ``MODELS_PERSIST_PATH`` 读取模型列表（失败返回空列表）。"""
        try:
            path = Path(MODELS_PERSIST_PATH)
            if not path.exists():
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("读取持久化模型失败: %s", exc)
            return []
        if isinstance(data, dict):
            return [str(m) for m in (data.get("models") or [])]
        if isinstance(data, list):
            return [str(m) for m in data]
        return []

    @staticmethod
    def _merge_models(base: List[str], extra: List[str]) -> List[str]:
        """合并两个模型列表，保序去重。"""
        merged: List[str] = []
        seen: set = set()
        for m in list(base) + list(extra):
            if not m or m in seen:
                continue
            seen.add(m)
            merged.append(m)
        return merged

    # ====================================================================
    # 生命周期
    # ====================================================================
    async def init(self, session: aiohttp.ClientSession) -> None:
        """初始化适配器；立即返回，后台完成耗时操作。

        Args:
            session: 共享的 :class:`aiohttp.ClientSession`。
        """
        from .client import QwenClient  # noqa: PLC0415

        self._client = QwenClient()
        self._init_task = asyncio.ensure_future(
            self._client.init_immediate(session)
        )
        self._bg_task = asyncio.ensure_future(
            self._client.background_setup()
        )

    async def close(self) -> None:
        """关闭适配器，取消后台任务，释放资源。"""
        for task in (self._init_task, self._bg_task):
            if task is None or task.done():
                continue
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("Qwen 后台任务已取消")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Qwen 后台任务关闭异常: %s", exc)
        if self._client is not None:
            await self._client.close()

    # ====================================================================
    # 候选项
    # ====================================================================
    async def candidates(self) -> List[Candidate]:
        """返回当前可用候选项列表。"""
        if self._client is None:
            return []
        return await self._client.candidates()

    async def ensure_candidates(self, count: int) -> int:
        """确保候选项数量；返回当前实际可用数量。"""
        if self._client is None:
            return 0
        return await self._client.ensure_candidates(count)

    # ====================================================================
    # 聊天补全
    # ====================================================================
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
        """聊天补全，完全委托给 :class:`QwenClient`。

        Yields:
            ``str``（文本增量）或 ``dict``（``thinking`` / ``usage`` /
            ``tool_calls``）。
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

    # ====================================================================
    # 媒体生成（公共：抓取 SSE tool_calls）
    # ====================================================================
    async def create_image(
        self,
        candidate: Candidate,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """图片生成：通过聊天通道抓取 ``qwen.image_gen`` 事件。"""
        del kw
        return await self._gather_media(
            candidate=candidate,
            prompt=prompt,
            model=model,
            target_name="qwen.image_gen",
            extractor=self._extract_image,
            empty_value={"created": int(time.time()), "data": []},
            upload_files=None,
        )

    async def edit_image(
        self,
        candidate: Candidate,
        image: bytes,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """图片编辑：上传原图后抓取 ``qwen.image_gen`` 事件。"""
        if not image:
            return {"created": int(time.time()), "data": []}
        filename = kw.get("filename") or "image.png"
        return await self._gather_media(
            candidate=candidate,
            prompt=prompt,
            model=model,
            target_name="qwen.image_gen",
            extractor=self._extract_image,
            empty_value={"created": int(time.time()), "data": []},
            upload_files=[(image, filename)],
        )

    async def create_video(
        self,
        candidate: Candidate,
        prompt: str,
        model: str,
        **kw: Any,
    ) -> Dict[str, Any]:
        """视频生成：通过聊天通道抓取 ``qwen.video_gen`` 事件。"""
        del kw
        return await self._gather_media(
            candidate=candidate,
            prompt=prompt,
            model=model,
            target_name="qwen.video_gen",
            extractor=self._extract_video,
            empty_value={"created": int(time.time()), "data": []},
            upload_files=None,
        )

    # ------------------------------------------------------------ 媒体抓取
    async def _gather_media(
        self,
        *,
        candidate: Candidate,
        prompt: str,
        model: str,
        target_name: str,
        extractor: Callable[[Dict[str, Any]], Dict[str, str]],
        empty_value: Dict[str, Any],
        upload_files: Any,
    ) -> Dict[str, Any]:
        """通用 SSE ``tool_calls`` 收集器。

        Args:
            candidate: 候选项。
            prompt: 用户提示。
            model: 模型名称。
            target_name: 关心的 ``function.name``（如 ``qwen.image_gen``）。
            extractor: ``arguments dict`` → 标准化条目的回调。
            empty_value: 客户端未初始化或无结果时的默认返回。
            upload_files: 透传给 ``client.complete`` 的可选上传文件列表。

        Returns:
            包含 ``created`` 与 ``data`` 的字典。
        """
        if self._client is None:
            return empty_value
        target_model = self._resolve_model(candidate, model)
        items: List[Dict[str, str]] = []

        complete_kw: Dict[str, Any] = {}
        if upload_files is not None:
            complete_kw["upload_files"] = upload_files

        async for chunk in self._client.complete(
            candidate,
            [{"role": "user", "content": prompt}],
            target_model,
            stream=True,
            thinking=False,
            search=False,
            **complete_kw,
        ):
            if not (isinstance(chunk, dict) and "tool_calls" in chunk):
                continue
            for call in self._iter_tool_calls(chunk, target_name):
                args = self._parse_call_arguments(call)
                if args is None:
                    continue
                entry = extractor(args)
                if entry:
                    items.append(entry)

        return {
            "created": int(time.time()),
            "data": [
                {k: v for k, v in item.items() if v}
                for item in items
                if item.get("url")
            ],
        }

    def _resolve_model(self, candidate: Candidate, model: str) -> str:
        """根据候选项与传入模型挑选最终 model 名。"""
        if model:
            return model
        candidate_models = getattr(candidate, "models", []) or []
        if candidate_models:
            return candidate_models[0]
        return self.supported_models[0]

    @staticmethod
    def _iter_tool_calls(
        chunk: Dict[str, Any],
        target_name: str,
    ) -> List[Dict[str, Any]]:
        """从单个 chunk 中筛选指定 name 的 tool_call。"""
        calls = chunk.get("tool_calls") or []
        if not isinstance(calls, list):
            return []
        result: List[Dict[str, Any]] = []
        for call in calls:
            if not isinstance(call, dict):
                continue
            fn = call.get("function") or {}
            if not isinstance(fn, dict):
                continue
            if fn.get("name") == target_name:
                result.append(call)
        return result

    @staticmethod
    def _parse_call_arguments(call: Dict[str, Any]) -> Any:
        """解析 ``call.function.arguments``，失败返回 ``None``。"""
        fn = call.get("function") or {}
        args_raw = fn.get("arguments", "")
        if not args_raw:
            return {}
        try:
            args = json.loads(args_raw)
        except (json.JSONDecodeError, ValueError):
            return None
        return args if isinstance(args, dict) else None

    @staticmethod
    def _extract_image(args: Dict[str, Any]) -> Dict[str, str]:
        """从 image_gen ``arguments`` 提取标准化条目。"""
        return {
            "url": args.get("url") or "",
            "local": args.get("local_path") or "",
        }

    @staticmethod
    def _extract_video(args: Dict[str, Any]) -> Dict[str, str]:
        """从 video_gen ``arguments`` 提取标准化条目。"""
        url = args.get("url") or ""
        return {"url": url} if url else {}

    # ====================================================================
    # TTS
    # ====================================================================
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
            WAV 格式音频字节；失败返回空字节串。
        """
        del voice, kw
        if self._client is None:
            return b""
        token = candidate.meta.get("token", "")
        if not token:
            return b""
        target_model = self._resolve_model(candidate, model)
        audio_path = await self._client.synthesize_tts(
            input_text, token, model=target_model
        )
        if not audio_path:
            return b""
        try:
            return Path(audio_path).read_bytes()
        except OSError as exc:
            logger.warning("读取 TTS 音频失败 %s: %s", audio_path, exc)
            return b""

    # ====================================================================
    # 代理控制
    # ====================================================================
    def set_proxy_enabled(self, enabled: bool, *, auto: bool = False) -> None:
        """设置 Qwen 平台的代理覆盖开关。

        只有在全局配置允许的情况下才会真正生效。
        """
        if not self.is_proxy_allowed():
            return
        if self._client is not None:
            self._client.set_proxy_enabled(enabled, auto=auto)

    def is_proxy_allowed(self) -> bool:
        """返回 Qwen 平台是否被允许使用代理切换。"""
        from src.core.config import get_config  # noqa: PLC0415

        cfg = get_config()
        return self.name in cfg.platforms_proxy.enabled_platforms_set

    def is_proxy_enabled(self) -> bool:
        """返回 Qwen 平台当前是否启用代理覆盖。"""
        if not self.is_proxy_allowed():
            return False
        if self._client is not None:
            return self._client.is_proxy_enabled()
        return False

    # ====================================================================
    # 类型注解辅助（仅用于静态检查；运行时无用）
    # ====================================================================
    if False:  # pragma: no cover - typing only
        _typing_callable = Callable[..., Awaitable[Any]]
