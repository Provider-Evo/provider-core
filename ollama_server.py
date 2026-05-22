"""
Ollama API 服务器模块 - 负责处理外界用户请求
版本: 1.0.0

核心特性:
- 集成 Nous 风格 XML 函数调用提示词系统
- 公平请求调度器 (FIFO) - 等待最久的请求优先响应
- 动态模型发现 - 通过 Ollama 服务器自动获取模型列表
- 完整适配 OpenAI/Anthropic 格式

工作流:
- 向 ollama_client 发送请求时: 使用 NousXML fncall 格式
- 向外部用户响应时: 保持 OpenAI/Anthropic 兼容格式
- 模型发现: 每 24 小时自动刷新服务器列表, /v1/models 动态变化
"""

import asyncio
import json
import os
import re
import sys
import time
import uuid
from asyncio import Event, Lock
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import *

import uvicorn
from fastapi import *
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import *

import logging

from script.ollama.ollama_client import *
from script.ollama.ollama_util import *

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("ollama_server")


# ==================== 调度器异常 ====================


class SchedulerError(Exception):
    """调度器基础异常"""

    pass


class QueueFullError(SchedulerError):
    """队列已满异常 - 应返回 HTTP 429"""

    def __init__(
        self,
        scheduler_name: str,
        queue_depth: int,
        max_queue: int,
    ) -> None:
        self.scheduler_name = scheduler_name
        self.queue_depth = queue_depth
        self.max_queue = max_queue
        super().__init__(
            f"调度器 '{scheduler_name}' 队列已满: "
            f"{queue_depth}/{max_queue}"
        )


class SlotTimeoutError(SchedulerError):
    """槽位等待超时异常 - 应返回 HTTP 504"""

    def __init__(
        self,
        scheduler_name: str,
        waited_seconds: float,
        timeout: float,
    ) -> None:
        self.scheduler_name = scheduler_name
        self.waited_seconds = waited_seconds
        self.timeout = timeout
        super().__init__(
            f"调度器 '{scheduler_name}' 等待超时: "
            f"已等待 {waited_seconds:.1f}s, "
            f"超时阈值 {timeout:.1f}s"
        )


class SchedulerShutdownError(SchedulerError):
    """调度器已关闭异常 - 应返回 HTTP 503"""

    def __init__(self, scheduler_name: str) -> None:
        self.scheduler_name = scheduler_name
        super().__init__(
            f"调度器 '{scheduler_name}' 已关闭，"
            f"不再接受新请求"
        )


# ==================== 请求槽位 ====================


@dataclass
class RequestSlot:
    """请求处理槽位"""

    request_id: str
    scheduler_name: str
    enqueued_at: float
    acquired_at: float
    _released: bool = field(default=False, repr=False)
    _release_callback: Any = field(
        default=None, repr=False
    )

    @property
    def wait_duration(self) -> float:
        """等待时长（秒）"""
        return self.acquired_at - self.enqueued_at

    async def release(self) -> None:
        """释放槽位"""
        if self._released:
            return
        self._released = True
        if self._release_callback is not None:
            await self._release_callback(self)

    def __del__(self) -> None:
        if not self._released:
            logger.warning(
                "RequestSlot %s 未被正确释放 "
                "(scheduler=%s)",
                self.request_id,
                self.scheduler_name,
            )


# ==================== FIFO 等待条目 ====================


@dataclass
class _WaiterEntry:
    """队列中等待处理的请求条目"""

    request_id: str
    event: Event
    enqueued_at: float
    cancelled: bool = False


# ==================== 公平请求调度器 ====================


class FairRequestScheduler:
    """公平请求调度器 (FIFO)"""

    def __init__(
        self,
        name: str,
        max_concurrent: int = 20,
        max_queue_size: int = 200,
        default_timeout: float = 120.0,
    ) -> None:
        self._name = name
        self._max_concurrent = max_concurrent
        self._max_queue_size = max_queue_size
        self._default_timeout = default_timeout
        self._active_count: int = 0
        self._waiters: Deque[_WaiterEntry] = deque()
        self._lock = Lock()
        self._shutdown = False
        self._total_processed: int = 0
        self._total_rejected: int = 0
        self._total_timed_out: int = 0
        self._total_wait_time: float = 0.0
        self._max_wait_time: float = 0.0
        self._peak_active: int = 0
        self._peak_queue: int = 0

        logger.info(
            "调度器 '%s' 初始化: "
            "max_concurrent=%d, max_queue=%d, timeout=%ss",
            name,
            max_concurrent,
            max_queue_size,
            default_timeout,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def queue_depth(self) -> int:
        return sum(
            1 for w in self._waiters if not w.cancelled
        )

    async def acquire_slot(
        self,
        request_id: str,
        timeout: Optional[float] = None,
    ) -> RequestSlot:
        """获取处理槽位"""
        if timeout is None:
            timeout = self._default_timeout

        enqueued_at = time.monotonic()

        async with self._lock:
            if self._shutdown:
                raise SchedulerShutdownError(self._name)

            if self._active_count < self._max_concurrent:
                self._active_count += 1
                if self._active_count > self._peak_active:
                    self._peak_active = self._active_count
                return RequestSlot(
                    request_id=request_id,
                    scheduler_name=self._name,
                    enqueued_at=enqueued_at,
                    acquired_at=time.monotonic(),
                    _release_callback=self._on_slot_released,
                )

            current_queue = self.queue_depth
            if current_queue >= self._max_queue_size:
                self._total_rejected += 1
                raise QueueFullError(
                    self._name,
                    current_queue,
                    self._max_queue_size,
                )

            waiter = _WaiterEntry(
                request_id=request_id,
                event=Event(),
                enqueued_at=enqueued_at,
            )
            self._waiters.append(waiter)
            queue_size = self.queue_depth
            if queue_size > self._peak_queue:
                self._peak_queue = queue_size

        try:
            await asyncio.wait_for(
                waiter.event.wait(), timeout=timeout
            )
        except asyncio.TimeoutError:
            waiter.cancelled = True
            async with self._lock:
                self._total_timed_out += 1
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    pass
            waited = time.monotonic() - enqueued_at
            raise SlotTimeoutError(
                self._name, waited, timeout
            )
        except asyncio.CancelledError:
            waiter.cancelled = True
            async with self._lock:
                try:
                    self._waiters.remove(waiter)
                except ValueError:
                    pass
            raise

        if waiter.cancelled:
            async with self._lock:
                self._active_count -= 1
                await self._dispatch_next_locked()
            raise asyncio.CancelledError()

        if self._shutdown:
            async with self._lock:
                self._active_count -= 1
            raise SchedulerShutdownError(self._name)

        acquired_at = time.monotonic()
        wait_duration = acquired_at - enqueued_at
        self._total_wait_time += wait_duration
        if wait_duration > self._max_wait_time:
            self._max_wait_time = wait_duration

        return RequestSlot(
            request_id=request_id,
            scheduler_name=self._name,
            enqueued_at=enqueued_at,
            acquired_at=acquired_at,
            _release_callback=self._on_slot_released,
        )

    @asynccontextmanager
    async def acquire(
        self,
        request_id: str,
        timeout: Optional[float] = None,
    ):
        """上下文管理器方式获取槽位"""
        slot = await self.acquire_slot(request_id, timeout)
        try:
            yield slot
        finally:
            await slot.release()

    async def _on_slot_released(
        self, slot: RequestSlot
    ) -> None:
        """槽位释放回调"""
        async with self._lock:
            self._active_count -= 1
            self._total_processed += 1
            await self._dispatch_next_locked()

    async def _dispatch_next_locked(self) -> None:
        """分派下一个等待的请求（必须在持锁状态下调用）"""
        while (
            self._waiters
            and self._active_count < self._max_concurrent
        ):
            waiter = self._waiters.popleft()
            if waiter.cancelled:
                continue
            self._active_count += 1
            if self._active_count > self._peak_active:
                self._peak_active = self._active_count
            waiter.event.set()
            break

    async def shutdown(
        self, drain_timeout: float = 10.0
    ) -> int:
        """优雅关闭调度器"""
        self._shutdown = True
        cancelled_count = 0
        async with self._lock:
            while self._waiters:
                waiter = self._waiters.popleft()
                if not waiter.cancelled:
                    waiter.cancelled = True
                    waiter.event.set()
                    cancelled_count += 1

        deadline = time.monotonic() + drain_timeout
        while (
            self._active_count > 0
            and time.monotonic() < deadline
        ):
            await asyncio.sleep(0.1)

        if self._active_count > 0:
            logger.warning(
                "调度器 '%s' 关闭时仍有 %d 个活跃请求",
                self._name,
                self._active_count,
            )

        logger.info(
            "调度器 '%s' 已关闭: 取消 %d 个排队请求",
            self._name,
            cancelled_count,
        )
        return cancelled_count

    def get_metrics(self) -> Dict[str, Any]:
        """获取调度器指标"""
        avg_wait = (
            self._total_wait_time / self._total_processed
            if self._total_processed > 0
            else 0.0
        )
        return {
            "name": self._name,
            "max_concurrent": self._max_concurrent,
            "max_queue_size": self._max_queue_size,
            "default_timeout_seconds": self._default_timeout,
            "current": {
                "active_requests": self._active_count,
                "queue_depth": self.queue_depth,
                "utilization": (
                    self._active_count
                    / self._max_concurrent
                    if self._max_concurrent > 0
                    else 0.0
                ),
            },
            "totals": {
                "processed": self._total_processed,
                "rejected_queue_full": self._total_rejected,
                "timed_out": self._total_timed_out,
            },
            "wait_time": {
                "average_seconds": round(avg_wait, 3),
                "max_seconds": round(
                    self._max_wait_time, 3
                ),
            },
            "peaks": {
                "max_active": self._peak_active,
                "max_queue_depth": self._peak_queue,
            },
            "shutdown": self._shutdown,
        }


# ==================== 调度器配置 ====================


class SchedulerConfig:
    """调度器配置"""

    CHAT_MAX_CONCURRENT: int = int(
        os.environ.get("SCHED_CHAT_CONCURRENT", "50")
    )
    CHAT_MAX_QUEUE: int = int(
        os.environ.get("SCHED_CHAT_QUEUE", "500")
    )
    CHAT_TIMEOUT: float = float(
        os.environ.get("SCHED_CHAT_TIMEOUT", "120")
    )

    AUX_MAX_CONCURRENT: int = int(
        os.environ.get("SCHED_AUX_CONCURRENT", "20")
    )
    AUX_MAX_QUEUE: int = int(
        os.environ.get("SCHED_AUX_QUEUE", "200")
    )
    AUX_TIMEOUT: float = float(
        os.environ.get("SCHED_AUX_TIMEOUT", "300")
    )


# ==================== 全局请求指标 ====================


class GlobalRequestMetrics:
    """全局请求指标追踪"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._total_requests: int = 0
        self._active_requests: int = 0
        self._peak_active: int = 0
        self._total_duration: float = 0.0
        self._max_duration: float = 0.0
        self._status_counts: Dict[int, int] = {}
        self._endpoint_counts: Dict[str, int] = {}
        self._start_time: float = time.monotonic()

    async def record_request_start(
        self, endpoint: str
    ) -> float:
        """记录请求开始"""
        async with self._lock:
            self._total_requests += 1
            self._active_requests += 1
            if self._active_requests > self._peak_active:
                self._peak_active = self._active_requests
            self._endpoint_counts[endpoint] = (
                self._endpoint_counts.get(endpoint, 0) + 1
            )
        return time.monotonic()

    async def record_request_end(
        self, start_time: float, status_code: int
    ) -> None:
        """记录请求结束"""
        duration = time.monotonic() - start_time
        async with self._lock:
            self._active_requests -= 1
            self._total_duration += duration
            if duration > self._max_duration:
                self._max_duration = duration
            self._status_counts[status_code] = (
                self._status_counts.get(status_code, 0) + 1
            )

    def get_metrics(self) -> Dict[str, Any]:
        """获取全局指标"""
        uptime = time.monotonic() - self._start_time
        avg_duration = (
            self._total_duration / self._total_requests
            if self._total_requests > 0
            else 0.0
        )
        rps = (
            self._total_requests / uptime
            if uptime > 0
            else 0.0
        )
        return {
            "uptime_seconds": round(uptime, 1),
            "total_requests": self._total_requests,
            "active_requests": self._active_requests,
            "peak_active_requests": self._peak_active,
            "requests_per_second": round(rps, 2),
            "duration": {
                "average_seconds": round(avg_duration, 3),
                "max_seconds": round(
                    self._max_duration, 3
                ),
            },
            "status_codes": dict(self._status_counts),
            "endpoints": dict(self._endpoint_counts),
        }


# ==================== 错误响应辅助函数 ====================


def _raise_scheduler_error_openai(
    exc: SchedulerError,
) -> None:
    """将调度器异常转换为 OpenAI 风格的 HTTP 异常"""
    if isinstance(exc, QueueFullError):
        raise HTTPException(
            status_code=429,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=(
                        f"Server is at capacity. Queue full: "
                        f"{exc.queue_depth}/{exc.max_queue}."
                    ),
                    type="rate_limit_error",
                    code="queue_full",
                )
            ).model_dump(),
        )
    elif isinstance(exc, SlotTimeoutError):
        raise HTTPException(
            status_code=504,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=(
                        f"Request timed out after "
                        f"{exc.waited_seconds:.1f}s."
                    ),
                    type="timeout_error",
                    code="slot_timeout",
                )
            ).model_dump(),
        )
    elif isinstance(exc, SchedulerShutdownError):
        raise HTTPException(
            status_code=503,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=(
                        "Server is shutting down. "
                        "Please retry later."
                    ),
                    type="service_unavailable",
                    code="server_shutdown",
                )
            ).model_dump(),
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=f"Scheduler error: {str(exc)}",
                    type="server_error",
                    code="scheduler_error",
                )
            ).model_dump(),
        )


def _raise_scheduler_error_anthropic(
    exc: SchedulerError,
) -> None:
    """将调度器异常转换为 Anthropic 风格的 HTTP 异常"""
    if isinstance(exc, QueueFullError):
        raise HTTPException(
            status_code=429,
            detail=AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="rate_limit_error",
                    message=(
                        f"Server is at capacity. Queue full: "
                        f"{exc.queue_depth}/{exc.max_queue}."
                    ),
                )
            ).model_dump(),
        )
    elif isinstance(exc, SlotTimeoutError):
        raise HTTPException(
            status_code=504,
            detail=AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="timeout_error",
                    message=(
                        f"Request timed out after "
                        f"{exc.waited_seconds:.1f}s."
                    ),
                )
            ).model_dump(),
        )
    elif isinstance(exc, SchedulerShutdownError):
        raise HTTPException(
            status_code=503,
            detail=AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="overloaded_error",
                    message=(
                        "Server is shutting down. "
                        "Please retry later."
                    ),
                )
            ).model_dump(),
        )
    else:
        raise HTTPException(
            status_code=500,
            detail=AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="api_error",
                    message=f"Scheduler error: {str(exc)}",
                )
            ).model_dump(),
        )


# ==================== Ollama API 服务器 ====================


class OllamaAPIServer:
    """Ollama API 服务器"""

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug
        self.client: Optional[AsyncOllamaClient] = None
        self._initialized = False

        # 处理器
        self.tool_processor = ToolCallProcessor()
        self.reasoning_processor = (
            ReasoningContentProcessor()
        )
        self.file_extractor = MessageFileExtractor()
        self.message_converter = (
            AnthropicMessageConverter()
        )
        self.fncall_processor = (
            QwenFnCallPromptProcessor()
        )

        # 存储
        self.batch_store = MessageBatchStore()
        self.file_store = AnthropicFileStore()

        # 调度器
        self.chat_scheduler = FairRequestScheduler(
            name="chat",
            max_concurrent=SchedulerConfig.CHAT_MAX_CONCURRENT,
            max_queue_size=SchedulerConfig.CHAT_MAX_QUEUE,
            default_timeout=SchedulerConfig.CHAT_TIMEOUT,
        )
        self.aux_scheduler = FairRequestScheduler(
            name="auxiliary",
            max_concurrent=SchedulerConfig.AUX_MAX_CONCURRENT,
            max_queue_size=SchedulerConfig.AUX_MAX_QUEUE,
            default_timeout=SchedulerConfig.AUX_TIMEOUT,
        )

        # 全局指标
        self.metrics = GlobalRequestMetrics()

    def _log_debug(self, message: str) -> None:
        """调试日志"""
        if self.debug:
            logger.debug("[Server] %s", message)

    def _format_tool_calls_for_response(
        self,
        tool_calls: Optional[List[Any]],
    ) -> Optional[List[ToolCall]]:
        """格式化工具调用以符合 OpenAI 规范"""
        if not tool_calls:
            return None
        formatted: List[ToolCall] = []
        for tc in tool_calls:
            if isinstance(tc, ToolCall):
                formatted.append(tc)
                continue
            if isinstance(tc, dict):
                tool_call = tc.copy()
            elif hasattr(tc, "model_dump"):
                tool_call = tc.model_dump()
            elif hasattr(tc, "__dict__"):
                tool_call = dict(tc.__dict__)
            else:
                continue
            tc_id = tool_call.get(
                "id"
            ) or f"call_{uuid.uuid4().hex[:24]}"
            func = tool_call.get("function", {})
            func_name = func.get("name", "")
            func_args = func.get("arguments")
            if func_args is not None and not isinstance(
                func_args, str
            ):
                func_args = json.dumps(
                    func_args, ensure_ascii=False
                )
            elif func_args is None:
                func_args = "{}"
            formatted.append(
                ToolCall(
                    id=tc_id,
                    type="function",
                    function=FunctionCall(
                        name=func_name,
                        arguments=func_args,
                    ),
                )
            )
        return formatted if formatted else None

    def _format_tool_calls_for_stream(
        self,
        tool_calls: Optional[List[Any]],
    ) -> Optional[List[ToolCallChunk]]:
        """格式化流式工具调用"""
        if not tool_calls:
            return None
        formatted: List[ToolCallChunk] = []
        for i, tc in enumerate(tool_calls):
            if isinstance(tc, ToolCallChunk):
                formatted.append(tc)
                continue
            if isinstance(tc, ToolCall):
                formatted.append(
                    ToolCallChunk(
                        index=i,
                        id=tc.id,
                        type=tc.type,
                        function=tc.function,
                    )
                )
                continue
            if isinstance(tc, dict):
                tool_call = tc.copy()
            elif hasattr(tc, "model_dump"):
                tool_call = tc.model_dump()
            elif hasattr(tc, "__dict__"):
                tool_call = dict(tc.__dict__)
            else:
                continue
            tc_id = tool_call.get(
                "id"
            ) or f"call_{uuid.uuid4().hex[:24]}"
            func = tool_call.get("function", {})
            func_name = func.get("name", "")
            func_args = func.get("arguments")
            if func_args is not None and not isinstance(
                func_args, str
            ):
                func_args = json.dumps(
                    func_args, ensure_ascii=False
                )
            elif func_args is None:
                func_args = "{}"
            formatted.append(
                ToolCallChunk(
                    index=i,
                    id=tc_id,
                    type="function",
                    function=FunctionCall(
                        name=func_name,
                        arguments=func_args,
                    ),
                )
            )
        return formatted if formatted else None

    async def initialize(self) -> None:
        """初始化服务器"""
        if self._initialized:
            return
        try:
            self.client = AsyncOllamaClient(
                debug=self.debug
            )
            await self.client.ensure_initialized()
            self._initialized = True
            logger.info(
                "Ollama API 服务器初始化完成，"
                "监听端口: %d",
                ServerConfig.PORT,
            )
        except Exception as e:
            logger.error("服务器初始化失败: %s", e)
            raise

    async def shutdown(self) -> None:
        """关闭服务器"""
        try:
            logger.info("正在关闭调度器...")
            shutdown_tasks = [
                self.chat_scheduler.shutdown(
                    drain_timeout=15.0
                ),
                self.aux_scheduler.shutdown(
                    drain_timeout=15.0
                ),
            ]
            results = await asyncio.gather(
                *shutdown_tasks, return_exceptions=True
            )
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        "调度器关闭异常: %s", result
                    )

            if self.client:
                await self.client.close()
            self._initialized = False
            logger.info("Ollama API 服务器已关闭")
        except Exception as e:
            logger.error("服务关闭异常: %s", e)

    def _extract_images_from_messages(
        self, messages: List[ChatMessage]
    ) -> List[str]:
        """从消息中提取 base64 图像数据

        Ollama 的图像传递方式是在消息的 images 字段中
        提供 base64 编码的图像数据（不含 data URI 前缀）。

        Args:
            messages: 消息列表

        Returns:
            base64 编码的图像列表
        """
        images: List[str] = []
        for msg in messages:
            if msg.content is None:
                continue
            if isinstance(msg.content, list):
                for part in msg.content:
                    if (
                        part.type == "image_url"
                        and part.image_url
                    ):
                        url = part.image_url.url
                        b64 = FileUtils.extract_base64_image(
                            url
                        )
                        if b64:
                            images.append(b64)
        return images

    def _extract_images_from_anthropic_messages(
        self, messages: List[AnthropicMessage]
    ) -> List[str]:
        """从 Anthropic 消息中提取 base64 图像数据"""
        images: List[str] = []
        for msg in messages:
            if isinstance(msg.content, str):
                continue
            for block in msg.content:
                if (
                    block.type == "image"
                    and block.source
                ):
                    source = block.source
                    if isinstance(
                        source, AnthropicImageSource
                    ):
                        if (
                            source.type == "base64"
                            and source.data
                        ):
                            images.append(source.data)
        return images

    def get_scheduler_metrics(self) -> Dict[str, Any]:
        """获取所有调度器的指标"""
        return {
            "schedulers": {
                "chat": self.chat_scheduler.get_metrics(),
                "auxiliary": self.aux_scheduler.get_metrics(),
            },
            "global": self.metrics.get_metrics(),
        }

    async def chat_completion(
        self, request: ChatCompletionRequest
    ) -> ChatCompletionResponse:
        """聊天补全 - 使用 NousXML fncall 格式"""
        completion_id = (
            IDGenerator.generate_completion_id()
        )
        created_time = int(time.time())
        system_fingerprint = (
            IDGenerator.generate_system_fingerprint()
        )
        model = request.model

        # 构建 NousXML fncall 格式 prompt
        prompt = MessageBuilder.build_prompt_from_messages(
            request.messages, request.tools
        )

        # 提取图像
        images = self._extract_images_from_messages(
            request.messages
        )

        # 构建停止词
        stop_words: Optional[List[str]] = None
        if request.tools:
            stop_words = list(FN_STOP_WORDS)
        if request.stop:
            if isinstance(request.stop, str):
                stop_words = (stop_words or []) + [
                    request.stop
                ]
            elif isinstance(request.stop, list):
                stop_words = (
                    stop_words or []
                ) + request.stop

        self._log_debug(
            f"处理非流式请求: model={model}, "
            f"images={len(images)}, "
            f"has_tools={bool(request.tools)}"
        )

        try:
            result = await self.client.chat_completion(
                message=prompt,
                model=model,
                images=images if images else None,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=stop_words,
            )

            raw_content = result.get("text", "")
            usage_data = result.get("usage", {})

            tool_calls: Optional[List[ToolCall]] = None
            reasoning_content: Optional[str] = None
            formal_content: Optional[str] = None

            if request.tools:
                (
                    reasoning_content,
                    formal_content,
                    parsed_tool_calls,
                ) = QwenFnCallPromptProcessor.postprocess_qwen_response(
                    raw_content
                )
                if parsed_tool_calls:
                    tool_calls = (
                        self._format_tool_calls_for_response(
                            parsed_tool_calls
                        )
                    )
            else:
                reasoning_content, formal_content = (
                    self.reasoning_processor.extract_reasoning(
                        raw_content
                    )
                )

            finish_reason = "stop"
            if tool_calls:
                finish_reason = "tool_calls"

            prompt_tokens = usage_data.get(
                "prompt_tokens", len(prompt) // 3
            )
            completion_tokens = usage_data.get(
                "completion_tokens",
                len(formal_content or "") // 3,
            )

            response_message = (
                ChatCompletionMessageResponse(
                    role="assistant",
                    content=formal_content,
                    reasoning_content=reasoning_content,
                    tool_calls=(
                        tool_calls if tool_calls else None
                    ),
                )
            )

            return ChatCompletionResponse(
                id=completion_id,
                created=created_time,
                model=model,
                choices=[
                    ChatCompletionChoice(
                        index=0,
                        message=response_message,
                        finish_reason=finish_reason,
                    )
                ],
                usage=ChatCompletionUsage(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens
                    + completion_tokens,
                ),
                system_fingerprint=system_fingerprint,
            )

        except Exception as e:
            logger.error("聊天补全错误: %s", e)
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        message=str(e),
                        type="server_error",
                        code="internal_error",
                    )
                ).model_dump(),
            )

    async def chat_completion_stream(
        self,
        request: ChatCompletionRequest,
        disconnect_event: Optional[Event] = None,
    ) -> AsyncGenerator[str, None]:
        """聊天补全流 - 使用 NousXML fncall 格式"""
        completion_id = (
            IDGenerator.generate_completion_id()
        )
        created_time = int(time.time())
        system_fingerprint = (
            IDGenerator.generate_system_fingerprint()
        )
        model = request.model

        prompt = MessageBuilder.build_prompt_from_messages(
            request.messages, request.tools
        )
        images = self._extract_images_from_messages(
            request.messages
        )

        stop_words: Optional[List[str]] = None
        if request.tools:
            stop_words = list(FN_STOP_WORDS)
        if request.stop:
            if isinstance(request.stop, str):
                stop_words = (stop_words or []) + [
                    request.stop
                ]
            elif isinstance(request.stop, list):
                stop_words = (
                    stop_words or []
                ) + request.stop

        self._log_debug(
            f"处理流式请求: model={model}, "
            f"images={len(images)}, "
            f"has_tools={bool(request.tools)}"
        )

        try:
            # 初始块
            initial_chunk = ChatCompletionChunk(
                id=completion_id,
                created=created_time,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(
                            role="assistant"
                        ),
                        finish_reason=None,
                    )
                ],
                system_fingerprint=system_fingerprint,
            )
            yield (
                f"data: {initial_chunk.model_dump_json()}"
                f"\n\n"
            )

            full_content = ""
            in_think_block = False
            think_content = ""
            completion_tokens = 0
            real_usage = None
            has_tools = bool(request.tools)

            # fncall 流式状态
            fncall_detected = False
            displayable_buffer = ""

            async for chunk in self.client.chat_stream(
                message=prompt,
                model=model,
                images=images if images else None,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=stop_words,
            ):
                if (
                    disconnect_event
                    and disconnect_event.is_set()
                ):
                    break

                if isinstance(chunk, dict):
                    if "usage" in chunk:
                        real_usage = chunk["usage"]
                    continue

                if not chunk:
                    continue

                full_content += chunk

                if has_tools:
                    if not fncall_detected:
                        displayable_buffer += chunk
                        if QwenFnCallPromptProcessor.detect_fncall_in_stream(
                            displayable_buffer
                        ):
                            fncall_detected = True
                            display_text, _ = (
                                QwenFnCallPromptProcessor.split_stream_content(
                                    displayable_buffer
                                )
                            )
                            if display_text.strip():
                                stream_result = (
                                    self._process_stream_chunk(
                                        chunk=display_text,
                                        in_think_block=in_think_block,
                                        think_content=think_content,
                                        completion_id=completion_id,
                                        created_time=created_time,
                                        model=model,
                                        system_fingerprint=system_fingerprint,
                                    )
                                )
                                in_think_block = (
                                    stream_result[
                                        "in_think_block"
                                    ]
                                )
                                think_content = (
                                    stream_result[
                                        "think_content"
                                    ]
                                )
                                completion_tokens += (
                                    stream_result[
                                        "tokens_added"
                                    ]
                                )
                                for oc in stream_result[
                                    "chunks"
                                ]:
                                    yield oc
                            displayable_buffer = ""
                        else:
                            safe_text = ""
                            has_partial = False
                            for marker in [
                                FN_NAME,
                                FN_ARGS,
                                FN_RESULT,
                                FN_EXIT,
                            ]:
                                for i in range(
                                    1, len(marker)
                                ):
                                    prefix = marker[:i]
                                    if displayable_buffer.endswith(
                                        prefix
                                    ):
                                        safe_text = displayable_buffer[
                                            : -len(prefix)
                                        ]
                                        displayable_buffer = prefix
                                        has_partial = True
                                        break
                                if has_partial:
                                    break
                            if not has_partial:
                                safe_text = (
                                    displayable_buffer
                                )
                                displayable_buffer = ""
                            if safe_text:
                                stream_result = self._process_stream_chunk(
                                    chunk=safe_text,
                                    in_think_block=in_think_block,
                                    think_content=think_content,
                                    completion_id=completion_id,
                                    created_time=created_time,
                                    model=model,
                                    system_fingerprint=system_fingerprint,
                                )
                                in_think_block = (
                                    stream_result[
                                        "in_think_block"
                                    ]
                                )
                                think_content = (
                                    stream_result[
                                        "think_content"
                                    ]
                                )
                                completion_tokens += (
                                    stream_result[
                                        "tokens_added"
                                    ]
                                )
                                for oc in stream_result[
                                    "chunks"
                                ]:
                                    yield oc
                    else:
                        pass  # fncall 已检测到，缓冲中
                else:
                    stream_result = (
                        self._process_stream_chunk(
                            chunk=chunk,
                            in_think_block=in_think_block,
                            think_content=think_content,
                            completion_id=completion_id,
                            created_time=created_time,
                            model=model,
                            system_fingerprint=system_fingerprint,
                        )
                    )
                    in_think_block = stream_result[
                        "in_think_block"
                    ]
                    think_content = stream_result[
                        "think_content"
                    ]
                    completion_tokens += stream_result[
                        "tokens_added"
                    ]
                    for oc in stream_result["chunks"]:
                        yield oc

            # 输出剩余 buffer
            if (
                displayable_buffer
                and not fncall_detected
            ):
                stream_result = (
                    self._process_stream_chunk(
                        chunk=displayable_buffer,
                        in_think_block=in_think_block,
                        think_content=think_content,
                        completion_id=completion_id,
                        created_time=created_time,
                        model=model,
                        system_fingerprint=system_fingerprint,
                    )
                )
                completion_tokens += stream_result[
                    "tokens_added"
                ]
                for oc in stream_result["chunks"]:
                    yield oc

            finish_reason = "stop"
            if has_tools and full_content:
                _, _, parsed_tool_calls = (
                    QwenFnCallPromptProcessor.postprocess_qwen_response(
                        full_content
                    )
                )
                if parsed_tool_calls:
                    finish_reason = "tool_calls"
                    formatted_tool_calls = (
                        self._format_tool_calls_for_stream(
                            parsed_tool_calls
                        )
                    )
                    if formatted_tool_calls:
                        for tc in formatted_tool_calls:
                            tool_chunk_data = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created_time,
                                "model": model,
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": {
                                            "tool_calls": [
                                                tc.model_dump()
                                            ]
                                        },
                                        "finish_reason": None,
                                        "logprobs": None,
                                    }
                                ],
                                "system_fingerprint": system_fingerprint,
                            }
                            yield (
                                f"data: "
                                f"{json.dumps(tool_chunk_data)}"
                                f"\n\n"
                            )

            if real_usage:
                usage = ChatCompletionUsage(
                    prompt_tokens=real_usage.get(
                        "prompt_tokens",
                        len(prompt) // 3,
                    ),
                    completion_tokens=real_usage.get(
                        "completion_tokens",
                        completion_tokens,
                    ),
                    total_tokens=real_usage.get(
                        "total_tokens",
                        len(prompt) // 3
                        + completion_tokens,
                    ),
                )
            else:
                usage = ChatCompletionUsage(
                    prompt_tokens=len(prompt) // 3,
                    completion_tokens=completion_tokens,
                    total_tokens=len(prompt) // 3
                    + completion_tokens,
                )

            final_chunk = ChatCompletionChunk(
                id=completion_id,
                created=created_time,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(),
                        finish_reason=finish_reason,
                    )
                ],
                usage=usage,
                system_fingerprint=system_fingerprint,
            )
            yield (
                f"data: {final_chunk.model_dump_json()}\n\n"
            )
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error("流式聊天错误: %s", e)
            error_chunk = {
                "error": {
                    "message": str(e),
                    "type": "server_error",
                    "code": "stream_error",
                }
            }
            yield (
                f"data: {json.dumps(error_chunk)}\n\n"
            )
            yield "data: [DONE]\n\n"

    def _process_stream_chunk(
        self,
        chunk: str,
        in_think_block: bool,
        think_content: str,
        completion_id: str,
        created_time: int,
        model: str,
        system_fingerprint: str,
    ) -> Dict[str, Any]:
        """处理流式块"""
        result: Dict[str, Any] = {
            "in_think_block": in_think_block,
            "think_content": think_content,
            "tokens_added": 0,
            "chunks": [],
        }

        def create_chunk(
            content: Optional[str] = None,
            reasoning_content: Optional[str] = None,
        ) -> str:
            chunk_obj = ChatCompletionChunk(
                id=completion_id,
                created=created_time,
                model=model,
                choices=[
                    ChatCompletionChunkChoice(
                        index=0,
                        delta=ChatCompletionChunkDelta(
                            content=content,
                            reasoning_content=reasoning_content,
                        ),
                        finish_reason=None,
                    )
                ],
                system_fingerprint=system_fingerprint,
            )
            return (
                f"data: {chunk_obj.model_dump_json()}\n\n"
            )

        if "<think>" in chunk and not in_think_block:
            result["in_think_block"] = True
            before_think = chunk.split("<think>")[0]
            if before_think:
                result["chunks"].append(
                    create_chunk(content=before_think)
                )
            after_think = (
                chunk.split("<think>")[1]
                if len(chunk.split("<think>")) > 1
                else ""
            )
            if "</think>" in after_think:
                think_part = after_think.split("</think>")[
                    0
                ]
                after_close = (
                    after_think.split("</think>")[1]
                    if len(
                        after_think.split("</think>")
                    )
                    > 1
                    else ""
                )
                result["in_think_block"] = False
                if think_part:
                    result["chunks"].append(
                        create_chunk(
                            reasoning_content=think_part
                        )
                    )
                if after_close:
                    result["chunks"].append(
                        create_chunk(content=after_close)
                    )
            else:
                result["think_content"] = after_think
            return result

        if in_think_block:
            if "</think>" in chunk:
                think_part = chunk.split("</think>")[0]
                after_close = (
                    chunk.split("</think>")[1]
                    if len(chunk.split("</think>")) > 1
                    else ""
                )
                result["in_think_block"] = False
                full_think = think_content + think_part
                if full_think:
                    result["chunks"].append(
                        create_chunk(
                            reasoning_content=full_think
                        )
                    )
                result["think_content"] = ""
                if after_close:
                    result["chunks"].append(
                        create_chunk(content=after_close)
                    )
            else:
                result["think_content"] = (
                    think_content + chunk
                )
            return result

        result["tokens_added"] = len(chunk) // 3
        result["chunks"].append(
            create_chunk(content=chunk)
        )
        return result

    def _filter_think_tags(self, text: str) -> str:
        """过滤 <think>/<\/think> 标签"""
        if not text:
            return text
        result = re.sub(
            r"<think>.*?</think>",
            "",
            text,
            flags=re.DOTALL,
        )
        result = result.replace("<think>", "").replace(
            "</think>", ""
        )
        return result

    async def anthropic_messages(
        self, request: AnthropicMessagesRequest
    ) -> AnthropicMessagesResponse:
        """Anthropic 消息处理"""
        message_id = (
            IDGenerator.generate_anthropic_message_id()
        )
        model = request.model

        prompt = self.message_converter.anthropic_to_prompt(
            messages=request.messages,
            system=request.system,
            tools=request.tools,
        )

        images = (
            self._extract_images_from_anthropic_messages(
                request.messages
            )
        )

        stop_words: Optional[List[str]] = None
        if request.tools:
            stop_words = list(FN_STOP_WORDS)
        if request.stop_sequences:
            stop_words = (
                stop_words or []
            ) + request.stop_sequences

        try:
            result = await self.client.chat_completion(
                message=prompt,
                model=model,
                images=images if images else None,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=stop_words,
            )

            raw_content = result.get("text", "")
            usage_data = result.get("usage", {})

            if request.tools:
                stop_reason, content_blocks = (
                    QwenFnCallPromptProcessor.postprocess_qwen_response_to_anthropic(
                        raw_content
                    )
                )
            else:
                _, formal_content = (
                    self.reasoning_processor.extract_reasoning(
                        raw_content
                    )
                )
                if formal_content is None:
                    formal_content = raw_content
                content_blocks = [
                    AnthropicTextBlock(
                        text=formal_content
                    )
                ]
                stop_reason = (
                    AnthropicStopReason.END_TURN.value
                )

            input_tokens = usage_data.get(
                "prompt_tokens", len(prompt) // 3
            )
            output_tokens = usage_data.get(
                "completion_tokens",
                len(raw_content) // 3,
            )

            return AnthropicMessagesResponse(
                id=message_id,
                content=content_blocks,
                model=request.model,
                stop_reason=stop_reason,
                stop_sequence=None,
                usage=AnthropicUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                ),
            )

        except Exception as e:
            logger.error("Anthropic Messages 错误: %s", e)
            raise HTTPException(
                status_code=500,
                detail=AnthropicErrorResponse(
                    error=AnthropicErrorDetail(
                        type="api_error",
                        message=str(e),
                    )
                ).model_dump(),
            )

    async def anthropic_messages_stream(
        self,
        request: AnthropicMessagesRequest,
        disconnect_event: Optional[Event] = None,
    ) -> AsyncGenerator[str, None]:
        """Anthropic 消息流处理"""
        message_id = (
            IDGenerator.generate_anthropic_message_id()
        )
        model = request.model

        prompt = self.message_converter.anthropic_to_prompt(
            messages=request.messages,
            system=request.system,
            tools=request.tools,
        )

        images = (
            self._extract_images_from_anthropic_messages(
                request.messages
            )
        )

        stop_words: Optional[List[str]] = None
        if request.tools:
            stop_words = list(FN_STOP_WORDS)
        if request.stop_sequences:
            stop_words = (
                stop_words or []
            ) + request.stop_sequences

        try:
            # message_start
            message_start = {
                "type": "message_start",
                "message": {
                    "id": message_id,
                    "type": "message",
                    "role": "assistant",
                    "content": [],
                    "model": request.model,
                    "stop_reason": None,
                    "stop_sequence": None,
                    "usage": {
                        "input_tokens": len(prompt) // 3,
                        "output_tokens": 0,
                    },
                },
            }
            yield (
                f"event: message_start\n"
                f"data: {json.dumps(message_start)}\n\n"
            )

            # content_block_start
            content_block_start = {
                "type": "content_block_start",
                "index": 0,
                "content_block": {
                    "type": "text",
                    "text": "",
                },
            }
            yield (
                f"event: content_block_start\n"
                f"data: {json.dumps(content_block_start)}"
                f"\n\n"
            )

            full_content = ""
            output_tokens = 0
            has_tools = bool(request.tools)
            fncall_detected = False
            displayable_buffer = ""

            async for chunk in self.client.chat_stream(
                message=prompt,
                model=model,
                images=images if images else None,
                temperature=request.temperature,
                top_p=request.top_p,
                max_tokens=request.max_tokens,
                stop=stop_words,
            ):
                if (
                    disconnect_event
                    and disconnect_event.is_set()
                ):
                    break
                if isinstance(chunk, dict):
                    continue
                if not chunk:
                    continue

                full_content += chunk

                if has_tools and not fncall_detected:
                    displayable_buffer += chunk
                    if QwenFnCallPromptProcessor.detect_fncall_in_stream(
                        displayable_buffer
                    ):
                        fncall_detected = True
                        display_text, _ = (
                            QwenFnCallPromptProcessor.split_stream_content(
                                displayable_buffer
                            )
                        )
                        filtered = self._filter_think_tags(
                            display_text
                        )
                        if filtered.strip():
                            output_tokens += (
                                len(filtered) // 3
                            )
                            delta_event = {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {
                                    "type": "text_delta",
                                    "text": filtered,
                                },
                            }
                            yield (
                                f"event: content_block_delta\n"
                                f"data: "
                                f"{json.dumps(delta_event)}"
                                f"\n\n"
                            )
                        displayable_buffer = ""
                    else:
                        safe_text = ""
                        has_partial = False
                        for marker in [
                            FN_NAME,
                            FN_ARGS,
                            FN_RESULT,
                            FN_EXIT,
                        ]:
                            for i in range(1, len(marker)):
                                prefix = marker[:i]
                                if displayable_buffer.endswith(
                                    prefix
                                ):
                                    safe_text = displayable_buffer[
                                        : -len(prefix)
                                    ]
                                    displayable_buffer = (
                                        prefix
                                    )
                                    has_partial = True
                                    break
                            if has_partial:
                                break
                        if not has_partial:
                            safe_text = displayable_buffer
                            displayable_buffer = ""
                        filtered = self._filter_think_tags(
                            safe_text
                        )
                        if filtered:
                            output_tokens += (
                                len(filtered) // 3
                            )
                            delta_event = {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {
                                    "type": "text_delta",
                                    "text": filtered,
                                },
                            }
                            yield (
                                f"event: content_block_delta\n"
                                f"data: "
                                f"{json.dumps(delta_event)}"
                                f"\n\n"
                            )
                elif has_tools and fncall_detected:
                    pass
                else:
                    filtered = self._filter_think_tags(chunk)
                    if filtered:
                        output_tokens += (
                            len(filtered) // 3
                        )
                        delta_event = {
                            "type": "content_block_delta",
                            "index": 0,
                            "delta": {
                                "type": "text_delta",
                                "text": filtered,
                            },
                        }
                        yield (
                            f"event: content_block_delta\n"
                            f"data: "
                            f"{json.dumps(delta_event)}\n\n"
                        )

            # 输出剩余 buffer
            if (
                displayable_buffer
                and not fncall_detected
            ):
                filtered = self._filter_think_tags(
                    displayable_buffer
                )
                if filtered:
                    output_tokens += len(filtered) // 3
                    delta_event = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {
                            "type": "text_delta",
                            "text": filtered,
                        },
                    }
                    yield (
                        f"event: content_block_delta\n"
                        f"data: "
                        f"{json.dumps(delta_event)}\n\n"
                    )

            # content_block_stop
            yield (
                f"event: content_block_stop\n"
                f'data: {{"type":"content_block_stop",'
                f'"index":0}}\n\n'
            )

            stop_reason = "end_turn"
            if has_tools and full_content:
                _, _, parsed_tool_calls = (
                    QwenFnCallPromptProcessor.postprocess_qwen_response(
                        full_content
                    )
                )
                if parsed_tool_calls:
                    stop_reason = "tool_use"
                    for i, tc in enumerate(
                        parsed_tool_calls, start=1
                    ):
                        try:
                            args = tc.function.arguments
                            if isinstance(args, str):
                                try:
                                    args_dict = (
                                        json.loads(args)
                                    )
                                except json.JSONDecodeError:
                                    args_dict = {
                                        "raw": args
                                    }
                            else:
                                args_dict = (
                                    args
                                    if isinstance(
                                        args, dict
                                    )
                                    else {"value": args}
                                )

                            tool_id = f"toolu_{uuid.uuid4().hex[:24]}"
                            tool_start = {
                                "type": "content_block_start",
                                "index": i,
                                "content_block": {
                                    "type": "tool_use",
                                    "id": tool_id,
                                    "name": tc.function.name,
                                    "input": {},
                                },
                            }
                            yield (
                                f"event: content_block_start\n"
                                f"data: "
                                f"{json.dumps(tool_start)}"
                                f"\n\n"
                            )
                            input_json = json.dumps(
                                args_dict,
                                ensure_ascii=False,
                            )
                            tool_delta = {
                                "type": "content_block_delta",
                                "index": i,
                                "delta": {
                                    "type": "input_json_delta",
                                    "partial_json": input_json,
                                },
                            }
                            yield (
                                f"event: content_block_delta\n"
                                f"data: "
                                f"{json.dumps(tool_delta)}"
                                f"\n\n"
                            )
                            tool_stop = {
                                "type": "content_block_stop",
                                "index": i,
                            }
                            yield (
                                f"event: content_block_stop\n"
                                f"data: "
                                f"{json.dumps(tool_stop)}"
                                f"\n\n"
                            )
                        except Exception as e:
                            logger.warning(
                                "流式 Anthropic 工具处理失败: %s",
                                e,
                            )
                            continue

            message_delta = {
                "type": "message_delta",
                "delta": {
                    "stop_reason": stop_reason,
                    "stop_sequence": None,
                },
                "usage": {
                    "output_tokens": output_tokens
                },
            }
            yield (
                f"event: message_delta\n"
                f"data: {json.dumps(message_delta)}\n\n"
            )

            message_stop = {"type": "message_stop"}
            yield (
                f"event: message_stop\n"
                f"data: {json.dumps(message_stop)}\n\n"
            )

        except Exception as e:
            logger.error("Anthropic 流式错误: %s", e)
            error_event = {
                "type": "error",
                "error": {
                    "type": "api_error",
                    "message": str(e),
                },
            }
            yield (
                f"event: error\n"
                f"data: {json.dumps(error_event)}\n\n"
            )

    async def create_embedding(
        self, request: EmbeddingRequest
    ) -> EmbeddingResponse:
        """创建嵌入向量"""
        try:
            if isinstance(request.input, str):
                texts = [request.input]
            else:
                texts = request.input

            embeddings = await self.client.get_embeddings(
                text=texts,
                model=request.model,
            )

            data: List[EmbeddingData] = []
            total_tokens = 0
            for i, embedding in enumerate(embeddings):
                data.append(
                    EmbeddingData(
                        embedding=embedding, index=i
                    )
                )
                if i < len(texts):
                    total_tokens += len(texts[i]) // 3

            return EmbeddingResponse(
                data=data,
                model=request.model,
                usage=EmbeddingUsage(
                    prompt_tokens=total_tokens,
                    total_tokens=total_tokens,
                ),
            )
        except Exception as e:
            logger.error("嵌入向量错误: %s", e)
            raise HTTPException(
                status_code=500,
                detail=ErrorResponse(
                    error=ErrorDetail(
                        message=str(e),
                        type="server_error",
                        code="embedding_error",
                    )
                ).model_dump(),
            )

    def list_models(self) -> ModelsResponse:
        """列出模型 - 从 Ollama 服务器动态获取"""
        created_time = int(time.time())
        models: List[ModelInfo] = []

        if self.client:
            available = (
                self.client.get_available_models()
            )
            for model_id in available:
                model_detail = (
                    self.client.get_model_info(model_id)
                )
                caps = {}
                if model_detail:
                    caps = model_detail.get(
                        "capabilities", {}
                    )

                is_vision = caps.get("vision", False)
                has_tools = caps.get("tools", False)

                family = ""
                param_size = ""
                if model_detail:
                    family = model_detail.get("family", "")
                    param_size = model_detail.get(
                        "parameter_size", ""
                    )

                server_count = len(
                    model_detail.get("servers", [])
                    if model_detail
                    else []
                )

                description = (
                    f"{family} {param_size}".strip()
                    if family or param_size
                    else None
                )
                if server_count > 0:
                    description = (
                        f"{description or model_id} "
                        f"({server_count} servers)"
                    )

                info: Dict[str, Any] = {
                    "id": model_id,
                    "name": model_id,
                    "meta": {
                        "capabilities": {
                            "chat": True,
                            "vision": is_vision,
                            "tools": has_tools,
                            "embedding": caps.get(
                                "embedding", False
                            ),
                        },
                    },
                }
                if description:
                    info["description"] = description

                models.append(
                    ModelInfo(
                        id=model_id,
                        object="model",
                        created=created_time,
                        owned_by="ollama",
                        info=info,
                        root=model_id,
                        parent=None,
                    )
                )

        return ModelsResponse(data=models)

    def list_anthropic_models(
        self,
    ) -> AnthropicModelsResponse:
        """列出 Anthropic 兼容模型"""
        created_at = datetime.now(
            timezone.utc
        ).isoformat()
        models_data: List[AnthropicModelInfo] = []

        if self.client:
            available = (
                self.client.get_available_models()
            )
            for model_id in available:
                models_data.append(
                    AnthropicModelInfo(
                        id=model_id,
                        display_name=model_id,
                        created_at=created_at,
                    )
                )

        return AnthropicModelsResponse(
            data=models_data,
            has_more=False,
            first_id=(
                models_data[0].id
                if models_data
                else None
            ),
            last_id=(
                models_data[-1].id
                if models_data
                else None
            ),
        )

    async def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        try:
            server_status = (
                await self.client.get_server_status()
            )
            return {
                "status": "running",
                "initialized": self._initialized,
                "available_models": (
                    self.client.get_available_models()
                    if self.client
                    else []
                ),
                "fncall_format": "nous_xml",
                "fncall_markers": {
                    "function": FN_NAME,
                    "args": FN_ARGS,
                    "result": FN_RESULT,
                    "return": FN_EXIT,
                },
                "scheduler": self.get_scheduler_metrics(),
                "features": [
                    "chat_completions",
                    "streaming",
                    "tool_calls",
                    "reasoning_content",
                    "embeddings",
                    "anthropic_messages",
                    "dynamic_model_discovery",
                    "track_and_stop_selection",
                    "checkpoint_resume",
                    "fair_request_scheduling",
                ],
                "servers": server_status,
            }
        except Exception as e:
            logger.error("获取状态错误: %s", e)
            return {"status": "error", "error": str(e)}


# ==================== FastAPI 应用 ====================


server = OllamaAPIServer(debug=ServerConfig.DEBUG)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("正在启动 Ollama API 服务器...")
    await server.initialize()
    yield
    logger.info("正在关闭 Ollama API 服务器...")
    await server.shutdown()


app = FastAPI(
    title="Ollama API Server",
    description=(
        "兼容 OpenAI API 和 Anthropic API 格式的 "
        "Ollama AI 服务 "
        "(NousXML FnCall 格式 + FIFO 公平调度 + "
        "动态模型发现)"
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# ==================== 请求追踪中间件 ====================


@app.middleware("http")
async def request_tracking_middleware(
    request: Request, call_next
):
    """请求追踪中间件"""
    endpoint = f"{request.method} {request.url.path}"
    start_time = await server.metrics.record_request_start(
        endpoint
    )
    try:
        response = await call_next(request)
        await server.metrics.record_request_end(
            start_time, response.status_code
        )
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        response.headers["X-Request-Id"] = request_id
        return response
    except Exception as e:
        await server.metrics.record_request_end(
            start_time, 500
        )
        raise


# ==================== 依赖项 ====================


def get_anthropic_version(
    anthropic_version: Optional[str] = Header(
        None, alias="anthropic-version"
    ),
) -> Optional[str]:
    return anthropic_version


def get_anthropic_beta(
    anthropic_beta: Optional[str] = Header(
        None, alias="anthropic-beta"
    ),
) -> Optional[str]:
    return anthropic_beta


# ==================== 基础路由 ====================


@app.get("/")
async def root():
    """根路由"""
    return {
        "message": "Ollama API Server",
        "version": "1.0.0",
        "docs": "/docs",
        "openai_compatible": True,
        "anthropic_compatible": True,
        "fncall_format": "nous_xml",
        "scheduling": "fifo_fair_queue",
        "model_discovery": "dynamic_24h_refresh",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": int(time.time()),
        "schedulers": {
            "chat": {
                "active": server.chat_scheduler.active_count,
                "queued": server.chat_scheduler.queue_depth,
            },
            "auxiliary": {
                "active": server.aux_scheduler.active_count,
                "queued": server.aux_scheduler.queue_depth,
            },
        },
    }


@app.get("/v1/models", response_model=ModelsResponse)
async def list_models():
    """列出模型 - 动态获取自 Ollama 服务器"""
    return server.list_models()


@app.get("/v1/models/{model_id}", response_model=ModelInfo)
async def get_model(model_id: str):
    """获取模型信息"""
    if server.client:
        info = server.client.get_model_info(model_id)
        if info:
            caps = info.get("capabilities", {})
            return ModelInfo(
                id=model_id,
                object="model",
                created=int(time.time()),
                owned_by="ollama",
                info={
                    "id": model_id,
                    "meta": {
                        "capabilities": {
                            "chat": True,
                            "vision": caps.get(
                                "vision", False
                            ),
                            "tools": caps.get(
                                "tools", False
                            ),
                        },
                    },
                },
                root=model_id,
                parent=None,
            )

    raise HTTPException(
        status_code=404,
        detail=ErrorResponse(
            error=ErrorDetail(
                message=f"Model {model_id} not found",
                type="invalid_request_error",
                code="model_not_found",
            )
        ).model_dump(),
    )


# ==================== 聊天补全路由 ====================


@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    raw_request: Request,
    authorization: Optional[str] = Header(None),
):
    """聊天补全"""
    if not request.messages:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message="messages is required",
                    type="invalid_request_error",
                    param="messages",
                    code="missing_required_parameter",
                )
            ).model_dump(),
        )

    request_id = f"chat_{uuid.uuid4().hex[:16]}"

    try:
        if request.stream:
            try:
                slot = (
                    await server.chat_scheduler.acquire_slot(
                        request_id
                    )
                )
            except SchedulerError as exc:
                _raise_scheduler_error_openai(exc)

            disconnect_event = Event()

            async def scheduled_stream():
                try:
                    async for chunk in (
                        server.chat_completion_stream(
                            request, disconnect_event
                        )
                    ):
                        if (
                            await raw_request.is_disconnected()
                        ):
                            disconnect_event.set()
                            break
                        yield chunk
                except asyncio.CancelledError:
                    disconnect_event.set()
                    raise
                finally:
                    await slot.release()

            return StreamingResponse(
                scheduled_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Content-Type": (
                        "text/event-stream; charset=utf-8"
                    ),
                },
            )
        else:
            try:
                async with server.chat_scheduler.acquire(
                    request_id
                ) as slot:
                    response = (
                        await server.chat_completion(
                            request
                        )
                    )
                    return JSONResponse(
                        content=response.model_dump(
                            exclude_none=True
                        ),
                    )
            except SchedulerError as exc:
                _raise_scheduler_error_openai(exc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("聊天补全异常: %s", e)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=f"Internal server error: {str(e)}",
                    type="server_error",
                    code="internal_error",
                )
            ).model_dump(),
        )


# ==================== 嵌入向量路由 ====================


@app.post(
    "/v1/embeddings", response_model=EmbeddingResponse
)
async def create_embedding(
    request: EmbeddingRequest,
    authorization: Optional[str] = Header(None),
):
    """创建嵌入向量"""
    if not request.input:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message="input is required",
                    type="invalid_request_error",
                    param="input",
                    code="missing_required_parameter",
                )
            ).model_dump(),
        )

    request_id = f"emb_{uuid.uuid4().hex[:16]}"
    try:
        async with server.aux_scheduler.acquire(
            request_id
        ) as slot:
            return await server.create_embedding(request)
    except SchedulerError as exc:
        _raise_scheduler_error_openai(exc)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("嵌入向量异常: %s", e)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=f"Embedding error: {str(e)}",
                    type="server_error",
                    code="embedding_error",
                )
            ).model_dump(),
        )


# ==================== Anthropic API 路由 ====================


@app.post("/v1/messages")
async def anthropic_messages(
    request: AnthropicMessagesRequest,
    raw_request: Request,
    anthropic_version: Optional[str] = Depends(
        get_anthropic_version
    ),
    anthropic_beta: Optional[str] = Depends(
        get_anthropic_beta
    ),
    x_api_key: Optional[str] = Header(
        None, alias="X-Api-Key"
    ),
):
    """Anthropic 消息"""
    if not request.messages:
        raise HTTPException(
            status_code=400,
            detail=AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="invalid_request_error",
                    message="messages is required",
                )
            ).model_dump(),
        )

    request_id = f"anth_{uuid.uuid4().hex[:16]}"

    try:
        if request.stream:
            try:
                slot = (
                    await server.chat_scheduler.acquire_slot(
                        request_id
                    )
                )
            except SchedulerError as exc:
                _raise_scheduler_error_anthropic(exc)

            disconnect_event = Event()

            async def scheduled_stream():
                try:
                    async for chunk in (
                        server.anthropic_messages_stream(
                            request, disconnect_event
                        )
                    ):
                        if (
                            await raw_request.is_disconnected()
                        ):
                            disconnect_event.set()
                            break
                        yield chunk
                except asyncio.CancelledError:
                    disconnect_event.set()
                    raise
                finally:
                    await slot.release()

            return StreamingResponse(
                scheduled_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "Content-Type": (
                        "text/event-stream; charset=utf-8"
                    ),
                },
            )
        else:
            try:
                async with server.chat_scheduler.acquire(
                    request_id
                ) as slot:
                    response = (
                        await server.anthropic_messages(
                            request
                        )
                    )
                    return JSONResponse(
                        content=response.model_dump(
                            exclude_none=True
                        ),
                    )
            except SchedulerError as exc:
                _raise_scheduler_error_anthropic(exc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Anthropic Messages 异常: %s", e)
        raise HTTPException(
            status_code=500,
            detail=AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="api_error",
                    message=(
                        f"Internal server error: {str(e)}"
                    ),
                )
            ).model_dump(),
        )


# ==================== Anthropic 模型路由 ====================


@app.get(
    "/v1/models/anthropic",
    response_model=AnthropicModelsResponse,
)
async def list_anthropic_models(
    anthropic_version: Optional[str] = Depends(
        get_anthropic_version
    ),
):
    """列出 Anthropic 兼容模型"""
    return server.list_anthropic_models()


# ==================== 状态和监控路由 ====================


@app.get("/v1/status")
async def get_status():
    """获取服务状态"""
    return await server.get_status()


@app.get("/v1/metrics")
async def get_metrics():
    """获取性能指标"""
    return server.get_scheduler_metrics()


@app.post("/v1/servers/refresh")
async def refresh_servers():
    """强制刷新服务器列表"""
    try:
        if server.client:
            await server.client.force_refresh_servers()
        return {
            "status": "ok",
            "message": "服务器列表已刷新",
            "available_models": (
                server.client.get_available_models()
                if server.client
                else []
            ),
        }
    except Exception as e:
        logger.error("强制刷新失败: %s", e)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error=ErrorDetail(
                    message=str(e),
                    type="server_error",
                    code="refresh_error",
                )
            ).model_dump(),
        )


# ==================== 异常处理器 ====================


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request, exc: HTTPException
):
    """HTTP 异常处理器"""
    return JSONResponse(
        status_code=exc.status_code,
        content=(
            exc.detail
            if isinstance(exc.detail, dict)
            else {"error": {"message": str(exc.detail)}}
        ),
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request, exc: Exception
):
    """通用异常处理器"""
    logger.error("未处理的异常: %s", exc)
    anthropic_version = request.headers.get(
        "anthropic-version"
    )
    if anthropic_version:
        return JSONResponse(
            status_code=500,
            content=AnthropicErrorResponse(
                error=AnthropicErrorDetail(
                    type="api_error",
                    message="Internal server error",
                )
            ).model_dump(),
        )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                message="Internal server error",
                type="server_error",
                code="internal_error",
            )
        ).model_dump(),
    )


# ==================== 主函数 ====================


def main() -> None:
    """主函数"""
    logger.info(
        "启动 Ollama API 服务器: "
        "http://%s:%d",
        ServerConfig.HOST,
        ServerConfig.PORT,
    )
    logger.info(
        "API 文档: http://%s:%d/docs",
        ServerConfig.HOST,
        ServerConfig.PORT,
    )
    logger.info("支持 OpenAI API 和 Anthropic API 格式")
    logger.info(
        "FnCall 格式: NousXML "
        "(%s/%s/%s/%s)",
        FN_NAME,
        FN_ARGS,
        FN_RESULT,
        FN_EXIT,
    )
    logger.info("模型发现: 动态 (每 24 小时自动刷新)")
    logger.info(
        "调度器配置: chat=%d/%d, aux=%d/%d",
        SchedulerConfig.CHAT_MAX_CONCURRENT,
        SchedulerConfig.CHAT_MAX_QUEUE,
        SchedulerConfig.AUX_MAX_CONCURRENT,
        SchedulerConfig.AUX_MAX_QUEUE,
    )
    logger.info(
        "调度策略: FIFO 公平队列 - "
        "等待最久的请求优先响应"
    )

    uvicorn.run(
        app,
        host=ServerConfig.HOST,
        port=ServerConfig.PORT,
        log_level="info",
        access_log=True,
        loop=(
            "uvloop"
            if sys.platform != "win32"
            else "asyncio"
        ),
    )


if __name__ == "__main__":
    main()
