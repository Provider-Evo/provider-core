from __future__ import annotations

# Qwen HTTP 客户端（完整多模态实现）——mixin 组合入口
#
# QwenClient 由四个 mixin 模块组合而成：
#   - AuthMixin:    登录、Token 校验、设置同步、Cookie 刷新
#   - UploadMixin:  OSS STS 上传、文件上传、图片下载
#   - MediaMixin:   视频生成（i2v）、TTS 语音合成
#   - LogsMixin:    缓冲日志聚合（重登/重试/登录失败）
#
# 本文件保留核心方法：初始化、候选项管理、持久化、对话管理、聊天补全。

import asyncio
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import aiohttp

from src.core.dispatch.candidate import Candidate, make_id
from src.core.models_cache import ModelsCache
from src.core.proxy_selector import ProxySelector
from src.logger import get_logger
from src.platforms.qwen.accounts import ACCOUNTS, Account
from src.platforms.qwen.core.auth import AuthMixin
from src.platforms.qwen.core.constants import (
    CAPS,
    MODELS,
    PROXY_SELECTOR_PERSIST_PATH,
    SMART_PROXY_ENABLED,
)
from src.platforms.qwen.core.logs import LogsMixin
from src.platforms.qwen.core.media import MediaMixin
from src.platforms.qwen.core.shared import (
    BASE_URL,
    CHAT_PATH,
    COOKIE_REFRESH_INTERVAL,
    DELETE_CHAT_PATH,
    MODELS_PATH,
    NEW_CHAT_PATH,
    PERSIST_INTERVAL,
    PERSIST_PATH,
    SSE_TIMEOUT,
    TASK_TIMERS_PATH,
    USER_AGENT,
    build_headers,
    build_new_chat_payload,
    build_payload,
    build_stop_headers,
    build_stop_payload,
    extract_model_ids,
    generate_cookies,
    generate_fingerprint,
    parse_sse_event,
)
from src.platforms.qwen.core.upload import UploadMixin

logger = get_logger(__name__)

MAX_RETRIES: int = 3
SETTINGS_TIMEOUT: int = 15


class WAFBlockedError(Exception):
    """Qwen 请求被 WAF 拦截时抛出。"""
    pass


class QwenClient(AuthMixin, UploadMixin, MediaMixin, LogsMixin):
    """Qwen HTTP 客户端（完整多模态实现）。

    支持能力：
    - 文本聊天（t2t，含 thinking / search 模式）
    - 视觉理解（vision，OpenAI image_url 格式自动转换）
    - 图片生成（T2I，chat_type=t2i，SSE phase=image_gen_tool 解析）
    - 视频生成（i2v，任务轮询 + CDN 下载）
    - TTS 语音合成（替换内容 + /api/v2/tts/completions，PCM→WAV）
    - 文件上传（OSS STS PUT，支持图片/音频/视频/文档）
    - 停止生成（stop_generation）
    - 对话删除（delete_chat，后台清理）
    """

    def __init__(self) -> None:
        """初始化客户端内部状态。"""
        self._session: Optional[aiohttp.ClientSession] = None
        self._account_states: Dict[str, Account] = {}
        self._candidates: List[Candidate] = []
        self._models: List[str] = list(MODELS)
        self._fp: str = ""
        self._cookies: Dict[str, Any] = {}
        self._bg_tasks: List[asyncio.Task] = []
        self._closing: bool = False
        self._active_chats: Dict[str, str] = {}
        self._models_cache = ModelsCache("qwen", MODELS, fetch_enabled=False)
        self._proxy_override: Optional[bool] = None
        self._proxy_selector = ProxySelector(Path(PROXY_SELECTOR_PERSIST_PATH))
        self._relogin_log_buffer: List[str] = []
        self._relogin_flush_task: Optional[asyncio.Task] = None
        self._retry_log_buffer: List[str] = []
        self._retry_log_flush_task: Optional[asyncio.Task] = None
        self._login_fail_buffer: List[Tuple[str, str]] = []  # (username_prefix, error_msg)
        self._login_fail_flush_task: Optional[asyncio.Task] = None

    def get_models(self) -> List[str]:
        """返回当前模型列表副本。"""
        return list(self._models)

    # =========================================================================
    # 代理切换
    # =========================================================================

    def set_proxy_enabled(self, enabled: bool) -> None:
        """设置此平台的代理覆盖开关。

        Args:
            enabled: True 强制使用代理，False 强制不使用。
        """
        if enabled:
            self._proxy_override = True
        else:
            self._proxy_override = False

    def is_proxy_enabled(self) -> bool:
        """返回此平台当前是否启用代理。"""
        if self._proxy_override is None:
            return False
        return bool(self._proxy_override)

    def _get_proxy_kwarg(self) -> Optional[str]:
        """获取应传递给 session.request 的 proxy 值。

        优先级层次：
        0. proxy_enabled = False → 全局禁用（绝对）
        1. proxy_urls → 由 monkey-patch 层处理（此处不涉及）
        2. platforms_proxy.enabled_platforms → 平台白名单检查
        3. SMART_PROXY_ENABLED → 智能选择器（proxy vs direct）
        """
        from src.core.config import get_config

        cfg = get_config()

        # Level 0: global kill switch
        if not cfg.proxy.proxy_enabled:
            return None

        # Explicit override (set by manual toggle)
        if self._proxy_override is True:
            if not cfg.platforms_proxy.is_platform_enabled("qwen"):
                return None
            from src.core.server import get_proxy_server
            return get_proxy_server()

        if self._proxy_override is False:
            return None

        # _proxy_override is None: smart selector or fallback to monkey-patch
        if SMART_PROXY_ENABLED:
            if self._proxy_selector.select():
                from src.core.server import get_proxy_server
                return get_proxy_server()
            return None

        # SMART_PROXY_ENABLED is False: no override → monkey-patch decides
        return None

    # =========================================================================
    # 规范接口
    # =========================================================================

    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化——不阻塞。

        Args:
            session: 共享的 aiohttp ClientSession。
        """
        self._session = session
        self._fp = generate_fingerprint()
        self._cookies = generate_cookies(self._fp)

        for acc in ACCOUNTS:
            self._account_states[acc.username] = Account(
                username=acc.username,
                password=acc.password,
            )

        # 先加载模型缓存（与内置合并）
        await self._models_cache.load()
        self._models = self._models_cache.models

        self._load_persist()
        self._rebuild_candidates()

        logger.debug(
            "Qwen 客户端立即初始化完成，初始候选项: %d 个",
            len(self._candidates),
        )

    async def background_setup(self) -> None:
        """后台完善——在后台 Task 中执行。"""
        # Phase 1: 快速初始登录（验证持久化 token，登录过期账号）
        await self._initial_login_pass()

        # Phase 2: 启动后台循环
        self._bg_tasks.append(
            asyncio.ensure_future(self._login_poll_loop())
        )

        # 模型定时刷新：立即一次，之后每 24h
        self._bg_tasks.append(
            asyncio.ensure_future(
                self._models_cache.start_refresh_loop(
                    self.fetch_remote_models,
                    interval=24 * 60 * 60,
                    on_update=self._on_models_update,
                )
            )
        )

        self._bg_tasks.append(
            asyncio.ensure_future(self._bg_cookie_refresh())
        )
        self._bg_tasks.append(
            asyncio.ensure_future(self._bg_persist())
        )
        logger.debug("Qwen 后台任务已启动")

    def update_models(self, models: List[str]) -> None:
        """更新模型列表并刷新候选项（合并内置 + 传入，去重）。"""
        merged: List[str] = []
        seen = set()
        for m in list(MODELS) + list(models):
            if not m:
                continue
            if m in seen:
                continue
            seen.add(m)
            merged.append(m)
        self._models = merged
        for cand in self._candidates:
            cand.models = list(merged)
        if self._account_states:
            self._rebuild_candidates()

    async def close(self) -> None:
        """关闭客户端：停止后台任务，保存持久化。"""
        self._closing = True
        if hasattr(self, '_relogin_flush_task') and self._relogin_flush_task and not self._relogin_flush_task.done():
            self._relogin_flush_task.cancel()
            self._relogin_flush_task = None
        if hasattr(self, '_flush_relogin_buffer_now'):
            self._flush_relogin_buffer_now()
        if hasattr(self, '_retry_log_flush_task') and self._retry_log_flush_task and not self._retry_log_flush_task.done():
            self._retry_log_flush_task.cancel()
            self._retry_log_flush_task = None
        if hasattr(self, '_flush_retry_log_buffer_now'):
            self._flush_retry_log_buffer_now()
        if hasattr(self, '_login_fail_flush_task') and self._login_fail_flush_task and not self._login_fail_flush_task.done():
            self._login_fail_flush_task.cancel()
            self._login_fail_flush_task = None
        if hasattr(self, '_flush_login_fail_buffer_now'):
            self._flush_login_fail_buffer_now()
        for task in self._bg_tasks:
            task.cancel()
        for task in self._bg_tasks:
            try:
                await task
            except asyncio.CancelledError:
                logger.debug("Qwen 后台任务已取消")
        self._bg_tasks.clear()
        self._save_persist()
        logger.info("Qwen 客户端已关闭")

    # =========================================================================
    # 候选项管理
    # =========================================================================

    def _rebuild_candidates(self) -> None:
        """根据当前账号状态重建候选项列表（无锁）。"""
        self._candidates = [
            Candidate(
                id=make_id("qwen", acc.username[:12]),
                platform="qwen",
                resource_id=acc.username[:12],
                models=list(self._models),
                context_length=acc.context_length,
                meta={
                    "email": acc.username,
                    "token": acc.token,
                    "user_id": acc.user_id,
                },
                **CAPS,
            )
            for acc in self._account_states.values()
            if acc.is_login and acc.token
        ]

    async def candidates(self) -> List[Candidate]:
        """返回当前候选项列表。

        Returns:
            候选项列表副本。
        """
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        """返回当前可用候选项数量。

        Args:
            count: 期望数量（未使用）。

        Returns:
            实际可用候选项数量。
        """
        return len(self._candidates)

    # =========================================================================
    # 持久化
    # =========================================================================

    def _load_persist(self) -> None:
        """从磁盘加载账号状态和 Cookie（同步，毫秒级）。"""
        if not os.path.exists(PERSIST_PATH):
            return
        try:
            data = json.loads(
                Path(PERSIST_PATH).read_text(encoding="utf-8")
            )
            valid_usernames = set(self._account_states.keys())
            for username, info in data.get("accounts", {}).items():
                if username not in valid_usernames:
                    continue
                acc = self._account_states[username]
                acc.token = info.get("token", "")
                acc.user_id = info.get("user_id", "")
                acc.password_hash = info.get("password_hash", "")
                acc.token_expires = float(info.get("token_expires", 0))
                acc.memory_disabled = bool(info.get("memory_disabled", False))
                acc.context_length = info.get("context_length")
                # 如果有有效token，标记为已登录
                if acc.token and acc.token_expires > time.time():
                    acc.is_login = True

            saved_cookies = data.get("cookies", {})
            if (
                saved_cookies.get("ssxmod_itna")
                and time.time() - saved_cookies.get("timestamp", 0)
                < COOKIE_REFRESH_INTERVAL
            ):
                self._cookies = saved_cookies
                logger.debug("Qwen: 从持久化恢复 Cookie")

            loaded = sum(
                1 for acc in self._account_states.values() if acc.token
            )
            logger.debug("Qwen: 从持久化恢复 %d 个账号 token", loaded)
        except Exception as e:
            logger.warning("Qwen 持久化加载失败: %s", e)

    def _load_task_timers(self) -> Dict[str, float]:
        """从磁盘加载后台任务的上次执行时间戳。

        Returns:
            任务名到时间戳的字典，加载失败返回空字典。
        """
        try:
            if Path(TASK_TIMERS_PATH).exists():
                data = json.loads(
                    Path(TASK_TIMERS_PATH).read_text(encoding="utf-8")
                )
                return {k: float(v) for k, v in data.items()}
        except Exception as e:
            logger.debug("Qwen 任务计时器加载失败: %s", e)
        return {}

    def _save_task_timers(self, timers: Dict[str, float]) -> None:
        """将后台任务的上次执行时间戳保存到磁盘。

        Args:
            timers: 任务名到时间戳的字典。
        """
        try:
            Path(TASK_TIMERS_PATH).parent.mkdir(
                parents=True, exist_ok=True
            )
            Path(TASK_TIMERS_PATH).write_text(
                json.dumps(timers, indent=2), encoding="utf-8"
            )
        except Exception as e:
            logger.debug("Qwen 任务计时器保存失败: %s", e)

    # =========================================================================
    # 模型刷新（ModelsCache）
    # =========================================================================

    async def refresh_models(self) -> None:
        """主动刷新远端模型（调用 ModelsCache）。"""
        await self._models_cache._do_refresh(  # type: ignore[attr-defined]
            self.fetch_remote_models,
            on_update=self._on_models_update,
        )

    async def _on_models_update(self, models: List[str]) -> None:
        """模型更新回调：更新本地列表并刷新候选。"""
        self._models = list(models)
        for cand in self._candidates:
            cand.models = list(models)
        if self._account_states:
            self._rebuild_candidates()

    def _save_persist(self) -> None:
        """保存账号状态和 Cookie 到磁盘（同步写文件）。"""
        try:
            Path(PERSIST_PATH).parent.mkdir(parents=True, exist_ok=True)
            accounts_data: Dict[str, Any] = {}
            for username, acc in self._account_states.items():
                accounts_data[username] = {
                    "token": acc.token,
                    "user_id": acc.user_id,
                    "password_hash": acc.password_hash,
                    "token_expires": acc.token_expires,
                    "memory_disabled": acc.memory_disabled,
                    "context_length": acc.context_length,
                }
            content = json.dumps(
                {
                    "accounts": accounts_data,
                    "cookies": {
                        **self._cookies,
                        "timestamp": time.time(),
                    },
                    "updated": time.time(),
                },
                indent=2,
                ensure_ascii=False,
            )
            tmp = PERSIST_PATH + ".tmp"
            Path(tmp).write_text(content, encoding="utf-8")
            for attempt in range(3):
                try:
                    os.replace(tmp, PERSIST_PATH)
                    return
                except PermissionError:
                    if attempt < 2:
                        time.sleep(0.1 * (attempt + 1))
            Path(PERSIST_PATH).write_text(content, encoding="utf-8")
            try:
                os.remove(tmp)
            except OSError as exc:
                logger.debug("清理临时持久化文件失败: %s", exc)
        except Exception as e:
            logger.warning("Qwen 持久化保存失败: %s", e)

    async def _bg_persist(self) -> None:
        """后台定期持久化任务。"""
        while not self._closing:
            await asyncio.sleep(PERSIST_INTERVAL)
            if not self._closing:
                self._save_persist()

    # =========================================================================
    # 远程模型列表获取
    # =========================================================================

    async def fetch_remote_models(self) -> List[str]:
        """获取远程模型列表。

        Returns:
            模型 ID 列表，失败返回空列表。
        """
        token = self._get_any_valid_token()
        if not token:
            logger.warning("Qwen 模型同步: 无可用 Token，跳过")
            return []

        endpoints = [
            "{}{}".format(BASE_URL, MODELS_PATH),
            "{}/api/v1/models".format(BASE_URL),
        ]
        headers = {
            "Authorization": "Bearer {}".format(token),
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
            "Origin": BASE_URL,
            "Referer": "{}/".format(BASE_URL),
            "source": "web",
        }

        for endpoint in endpoints:
            try:
                async with self._session.get(
                    endpoint,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status != 200:
                        continue
                    raw = await resp.json(content_type=None)
                    remote_models = extract_model_ids(raw)
                    if remote_models:
                        logger.debug(
                            "Qwen 远程模型获取成功: %d 个", len(remote_models)
                        )
                        return remote_models
            except Exception as e:
                logger.debug("Qwen 模型端点 %s 失败: %s", endpoint, e)

        logger.warning("Qwen 远程模型获取失败：所有端点均不可用")
        return []

    def _get_any_valid_token(self) -> Optional[str]:
        """获取任意一个有效 token。

        Returns:
            有效 token 或 None。
        """
        for acc in self._account_states.values():
            if acc.token:
                return acc.token
        return None

    def _get_any_valid_user_id(self) -> str:
        """获取任意一个有效 user_id。

        Returns:
            user_id 字符串，无则返回空字符串。
        """
        for acc in self._account_states.values():
            if acc.token and acc.user_id:
                return acc.user_id
        return ""

    # =========================================================================
    # 对话管理
    # =========================================================================

    async def _create_chat(
        self,
        token: str,
        model: str,
        chat_type: str = "t2t",
    ) -> str:
        """创建新对话，返回对话 ID。

        Args:
            token: Bearer 令牌。
            model: 模型名称。
            chat_type: 聊天类型（t2t/t2i/i2v）。

        Returns:
            对话 ID 字符串。

        Raises:
            Exception: 创建失败。
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
            timeout=aiohttp.ClientTimeout(total=SETTINGS_TIMEOUT),
        ) as resp:
            if resp.status != 200:
                err = await resp.text()
                raise Exception(
                    "Qwen 创建对话失败 HTTP {}: {}".format(
                        resp.status, err[:200]
                    )
                )
            data = await resp.json()
            if not data.get("success"):
                raise Exception("Qwen 创建对话失败: {}".format(data))
            chat_id = data.get("data", {}).get("id")
            if not chat_id:
                raise Exception(
                    "Qwen 创建对话响应缺少 chat_id: {}".format(data)
                )
            return chat_id

    async def stop_generation(self, chat_id: str, token: str) -> bool:
        """向 Qwen 发送停止生成指令。

        Args:
            chat_id: 需要停止的对话 ID。
            token: Bearer 令牌。

        Returns:
            True 表示停止指令发送成功，False 表示失败。
        """
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
                timeout=aiohttp.ClientTimeout(connect=5, total=15),
            ) as resp:
                if resp.status in (200, 204):
                    self._active_chats = {
                        k: v
                        for k, v in self._active_chats.items()
                        if v != chat_id
                    }
                    return True
                logger.warning(
                    "Qwen 停止生成失败: HTTP %d", resp.status
                )
                return False
        except Exception as e:
            logger.warning("Qwen 停止生成异常: %s", e)
            return False

    async def delete_chat(self, chat_id: str, token: str) -> bool:
        """删除指定对话。

        Args:
            chat_id: 需要删除的对话 ID。
            token: Bearer 令牌。

        Returns:
            True 表示删除成功，False 表示失败。
        """
        if not chat_id or not token:
            return False

        url = "{}{}".format(
            BASE_URL,
            DELETE_CHAT_PATH.format(chat_id=chat_id),
        )
        headers = build_headers(token, cookies=self._cookies)

        try:
            async with self._session.delete(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(connect=5, total=15),
            ) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    async def _cleanup_chat(self, chat_id: str, token: str) -> None:
        """后台异步清理对话。

        Args:
            chat_id: 对话 ID。
            token: Bearer 令牌。
        """
        try:
            await self.delete_chat(chat_id, token)
        except Exception as e:
            logger.debug("Qwen 对话清理异常: %s", e)

    # =========================================================================
    # 聊天补全（核心，支持全模态）
    # =========================================================================

    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        tts: bool = False,
        upload_files: Optional[List[Tuple[bytes, str]]] = None,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行聊天补全，含重试。

        支持参数：
        - thinking: 启用 Thinking 模式（深度推理）
        - search: 启用联网搜索
        - tts: 启用 TTS 语音合成（完整响应后合成）
        - upload_files: [(file_data, filename), ...] 上传文件并附加到消息

        Args:
            candidate: 候选项。
            messages: OpenAI 格式消息列表（支持 image_url 多模态）。
            model: 模型名称。
            stream: 是否流式（Qwen 内部始终流式）。
            thinking: 是否启用 Thinking 模式。
            search: 是否启用搜索。
            tts: 是否启用 TTS。
            upload_files: 需要上传的文件列表 [(bytes, filename)]。
            **kw: 额外参数。

        Yields:
            str（文本增量）、
            dict（{"thinking": ...} / {"usage": ...} /
                  {"tool_calls": [...]}）。
        """
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async for chunk in self._do_request(
                    candidate,
                    messages,
                    model,
                    thinking=thinking,
                    search=search,
                    tts=tts,
                    upload_files=upload_files,
                ):
                    yield chunk
                return
            except WAFBlockedError:
                logger.warning(
                    "Qwen: 检测到 WAF 拦截（第 %d/%d 次重试）",
                    attempt + 1, MAX_RETRIES,
                )
                last_exc = None  # 清除 last_exc，让重试继续
                self._log_retry(
                    f"WAF 重试 {attempt + 1}/{MAX_RETRIES}"
                )
            except Exception as e:
                last_exc = e
                self._log_retry(
                    f"{attempt + 1}/{MAX_RETRIES}: {e}"
                )
        self._flush_retry_log_buffer_now()
        if last_exc:
            raise last_exc

    async def _do_request(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        *,
        thinking: bool = False,
        search: bool = False,
        tts: bool = False,
        upload_files: Optional[List[Tuple[bytes, str]]] = None,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        """执行单次 SSE 聊天请求（完整多模态）。

        流程：
        1. 预处理上传文件（OSS STS 上传）
        2. 提取消息中的 image_url 并转换为文件对象
        3. 创建新对话
        4. 发送 SSE 请求
        5. 有状态解析 SSE 流（thinking_summary 累积、媒体事件转 tool_calls）
        6. 可选 TTS 合成
        7. 后台清理对话

        Args:
            candidate: 候选项。
            messages: 消息列表。
            model: 模型名称。
            thinking: 是否 Thinking 模式。
            search: 是否搜索。
            tts: 是否 TTS。
            upload_files: 需要上传的文件列表。

        Yields:
            str 或 dict。
        """
        token = candidate.meta.get("token", "")
        user_id = candidate.meta.get("user_id", "")
        if not token:
            raise Exception("Qwen: 候选项缺少 token")

        # 思考模式配置：按调用方参数决定是否开启，若上游返回思考标记仍会解析
        if thinking:
            thinking_enabled = True
            auto_thinking = False
            thinking_mode = "Thinking"
            thinking_format = "raw"
        else:
            thinking_enabled = False
            auto_thinking = False
            thinking_mode = "Fast"
            thinking_format = "summary"

        # 预处理文件上传
        file_objects: List[Dict[str, Any]] = []
        if upload_files:
            for file_data, filename in upload_files:
                try:
                    fo = await self.upload_file(
                        file_data, filename, token, user_id
                    )
                    file_objects.append(fo)
                except Exception as e:
                    logger.warning("文件上传失败 %s: %s", filename, e)

        # 检测消息中的 base64 data URI 图片并上传
        base64_images = self._extract_base64_images(messages)
        if base64_images:
            for data_uri in base64_images:
                try:
                    fo = await self.upload_file_from_base64(
                        data_uri, token, user_id
                    )
                    file_objects.append(fo)
                except Exception as e:
                    logger.warning("Base64 图片上传失败: %s", e)

        # 创建新对话
        chat_id = await self._create_chat(token, model, "t2t")
        self._active_chats[candidate.id] = chat_id

        try:
            # 构建载荷
            payload = build_payload(
                messages=messages,
                model=model,
                chat_id=chat_id,
                files=file_objects,
                thinking_enabled=thinking_enabled,
                auto_thinking=auto_thinking,
                thinking_mode=thinking_mode,
                thinking_format=thinking_format,
                auto_search=search,
                stream=True,
            )

            headers = build_headers(
                token,
                chat_id=chat_id,
                include_sse=True,
                fingerprint=self._fp,
                cookies=self._cookies,
            )
            url = "{}{}?chat_id={}".format(BASE_URL, CHAT_PATH, chat_id)

            post_kw: Dict[str, Any] = {
                "json": payload,
                "headers": headers,
                "ssl": False,
                "timeout": aiohttp.ClientTimeout(
                    connect=10, total=SSE_TIMEOUT
                ),
            }
            # Smart proxy selector: always ask for proxy decision.
            # When override is set or SMART_PROXY_ENABLED is True,
            # _get_proxy_kwarg() returns the proxy URL or None.
            # When neither applies, "proxy" key is omitted so the
            # global monkey-patch decides (Level 1: URL patterns).
            proxy_kw = self._get_proxy_kwarg()
            _used_smart_proxy: Optional[bool] = (proxy_kw is not None)
            if proxy_kw is not None or self._proxy_override is not None:
                post_kw["proxy"] = proxy_kw

            _request_start = time.time()
            _request_failed = True  # assume failure; cleared on success

            async with self._session.post(url, **post_kw) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    # 检测 token 过期或未授权错误
                    if resp.status == 401 or "Token has expired" in err or "unauthorized" in err.lower():
                        email = candidate.meta.get("email", "")
                        if email and email in self._account_states:
                            acc = self._account_states[email]
                            logger.warning("账号 [%s***] token 已过期，反应式清除", email[:6])
                            acc.is_login = False
                            acc.token = ""
                            self._rebuild_candidates()
                            self._save_persist()
                        raise Exception(
                            "Qwen token已过期: {}".format(err[:200])
                        )
                    raise Exception(
                        "Qwen HTTP {}: {}".format(resp.status, err[:300])
                    )

                # 检查 Content-Type，防止 WAF 拦截页面被当作 SSE 处理
                ct = resp.headers.get("Content-Type", "")
                if "text/html" in ct:
                    err = await resp.text()
                    raise WAFBlockedError(
                        "Qwen 返回 HTML 页面（可能被 WAF 拦截）: {}".format(
                            err[:300]
                        )
                    )

                # 有状态解析变量
                emitted_count = 0
                response_id: Optional[str] = None
                full_text_parts: List[str] = []
                thinking_parts: List[str] = []

                # 预读缓冲区，确保流式数据正确接收
                buffer = await resp.content.readany()

                # 处理初始缓冲中的数据
                if buffer:
                    lines = buffer.split(b"\n")
                    remaining = lines[-1]

                    for line_bytes in lines[:-1]:
                        line_str = line_bytes.decode(
                            "utf-8", errors="replace"
                        ).strip()
                        if not line_str or not line_str.startswith("data:"):
                            continue
                        data_str = line_str[5:].lstrip()
                        if not data_str or data_str == "[DONE]":
                            continue

                        event = parse_sse_event(data_str)
                        if event is None:
                            continue

                        evt_type = event.get("type", "")
                        if evt_type == "error":
                            raise Exception(
                                "Qwen 服务器错误: {}".format(
                                    event.get("message", "")
                                )
                            )
                        elif evt_type == "response_created":
                            response_id = event.get("response_id")
                        elif evt_type == "answer":
                            text_chunk = (
                                event["content"]
                                .replace("<think>", "")
                                .replace("</think>", "")
                            )
                            if text_chunk:
                                full_text_parts.append(text_chunk)
                                yield text_chunk
                        elif evt_type == "usage":
                            yield {"usage": event.get("data", {})}
                        elif evt_type == "thinking_summary":
                            status = event.get("status", "")
                            extra = event.get("extra", {})
                            if status == "typing" and extra:
                                titles = extra.get(
                                    "summary_title", {}
                                ).get("content", [])
                                thoughts = extra.get(
                                    "summary_thought", {}
                                ).get("content", [])
                                count = max(len(titles), len(thoughts))
                                for i in range(emitted_count, count):
                                    t = (
                                        titles[i]
                                        if i < len(titles)
                                        else ""
                                    )
                                    th = (
                                        thoughts[i]
                                        if i < len(thoughts)
                                        else ""
                                    )
                                    piece = (
                                        "{}: {}".format(t, th)
                                        if t
                                        else th
                                    )
                                    thinking_parts.append(piece)
                                    yield {"thinking": piece}
                                emitted_count = count

                    buffer = remaining

                async for raw in resp.content.iter_any():
                    if not raw:
                        continue
                    buffer += raw
                    lines = buffer.split(b"\n")
                    buffer = lines[-1]

                    for line_bytes in lines[:-1]:
                        line_str = line_bytes.decode(
                            "utf-8", errors="replace"
                        ).strip()
                        if not line_str or not line_str.startswith("data:"):
                            continue
                        data_str = line_str[5:].lstrip()
                        if not data_str or data_str == "[DONE]":
                            continue

                        event = parse_sse_event(data_str)
                        if event is None:
                            continue

                        evt_type = event.get("type", "")

                        if evt_type == "error":
                            raise Exception(
                                "Qwen 服务器错误: {}".format(
                                    event.get("message", "")
                                )
                            )

                        elif evt_type == "response_created":
                            response_id = event.get("response_id")

                        elif evt_type == "answer":
                            text_chunk = (
                                event["content"]
                                .replace("<think>", "")
                                .replace("</think>", "")
                            )
                            if text_chunk:
                                full_text_parts.append(text_chunk)
                                yield text_chunk

                        elif evt_type == "thinking_summary":
                            status = event.get("status", "")
                            extra = event.get("extra", {})
                            if status == "typing" and extra:
                                titles = extra.get(
                                    "summary_title", {}
                                ).get("content", [])
                                thoughts = extra.get(
                                    "summary_thought", {}
                                ).get("content", [])
                                count = max(len(titles), len(thoughts))
                                for i in range(emitted_count, count):
                                    t = (
                                        titles[i]
                                        if i < len(titles)
                                        else ""
                                    )
                                    th = (
                                        thoughts[i]
                                        if i < len(thoughts)
                                        else ""
                                    )
                                    piece = (
                                        "{}: {}".format(t, th)
                                        if t
                                        else th
                                    )
                                    thinking_parts.append(piece)
                                    yield {"thinking": piece}
                                emitted_count = count

                        elif evt_type == "image_gen_tool":
                            # 图片生成结果统一映射到 tool_calls
                            calls: List[Dict[str, Any]] = []
                            for img_url in event.get("urls", []):
                                local_path = await self.download_image(
                                    img_url
                                )
                                args = {"url": img_url}
                                if local_path:
                                    args["local_path"] = local_path
                                calls.append(
                                    {
                                        "id": "call_{}".format(
                                            uuid.uuid4().hex[:12]
                                        ),
                                        "type": "function",
                                        "function": {
                                            "name": "qwen.image_gen",
                                            "arguments": json.dumps(
                                                args,
                                                ensure_ascii=False,
                                            ),
                                        },
                                    }
                                )
                            if calls:
                                yield {"tool_calls": calls}

                        elif evt_type == "image_gen":
                            # 直接图片内容统一映射到 tool_calls
                            img_url = event.get("content", "")
                            if img_url:
                                local_path = await self.download_image(
                                    img_url
                                )
                                args = {"url": img_url}
                                if local_path:
                                    args["local_path"] = local_path
                                yield {
                                    "tool_calls": [
                                        {
                                            "id": "call_{}".format(
                                                uuid.uuid4().hex[:12]
                                            ),
                                            "type": "function",
                                            "function": {
                                                "name": "qwen.image_gen",
                                                "arguments": json.dumps(
                                                    args,
                                                    ensure_ascii=False,
                                                ),
                                            },
                                        }
                                    ]
                                }

                        elif evt_type == "video_gen":
                            # 视频生成结果统一映射到 tool_calls
                            video_url = event.get("content", "")
                            if video_url:
                                yield {
                                    "tool_calls": [
                                        {
                                            "id": "call_{}".format(
                                                uuid.uuid4().hex[:12]
                                            ),
                                            "type": "function",
                                            "function": {
                                                "name": "qwen.video_gen",
                                                "arguments": json.dumps(
                                                    {"url": video_url},
                                                    ensure_ascii=False,
                                                ),
                                            },
                                        }
                                    ]
                                }

                        elif evt_type == "usage":
                            yield {"usage": event.get("data", {})}

                        elif evt_type == "other":
                            content = (
                                event.get("content", "")
                                .replace("<think>", "")
                                .replace("</think>", "")
                            )
                            if content:
                                full_text_parts.append(content)
                                yield content

                        # 附带 usage
                        if "usage" in event and evt_type != "usage":
                            yield {"usage": event["usage"]}

                # TTS 合成（可选），不向上 yield audio_path
                if tts and response_id:
                    await self.request_tts(chat_id, response_id, token)

                _request_failed = False

        except (aiohttp.ClientPayloadError, aiohttp.http_exceptions.PayloadEncodingError) as e:
            # 传输中断（如 TransferEncodingError、ContentEncodingError 等），
            # 已 yield 的数据已发出，不向上抛出，避免重试循环
            logger.warning("Qwen 流式响应被截断，已收集部分数据: %s", e)
            _request_failed = False  # partial success: data was already emitted
            if _used_smart_proxy is not None and SMART_PROXY_ENABLED:
                latency_ms = (time.time() - _request_start) * 1000
                self._proxy_selector.record(
                    _used_smart_proxy, True, latency_ms
                )
                _used_smart_proxy = None  # prevent double-recording in finally
        except Exception as e:
            # 其他未知异常，记录日志后向上传播
            logger.error("Qwen _do_request 未知异常: %s", e, exc_info=True)
            if _used_smart_proxy is not None and SMART_PROXY_ENABLED:
                self._proxy_selector.record(_used_smart_proxy, False)
                _used_smart_proxy = None  # prevent double-recording in finally
            raise
        finally:
            # Record proxy outcome for smart selector learning
            if _used_smart_proxy is not None and SMART_PROXY_ENABLED:
                if not _request_failed:
                    latency_ms = (time.time() - _request_start) * 1000
                    self._proxy_selector.record(
                        _used_smart_proxy, True, latency_ms
                    )
                else:
                    self._proxy_selector.record(_used_smart_proxy, False)
            self._active_chats.pop(candidate.id, None)
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))

    async def stop_candidate_generation(
        self, candidate: Candidate
    ) -> bool:
        """停止指定候选项当前的生成任务。

        Args:
            candidate: 候选项对象。

        Returns:
            True 表示成功，False 表示无活跃对话或停止失败。
        """
        chat_id = self._active_chats.get(candidate.id)
        if not chat_id:
            return False
        token = candidate.meta.get("token", "")
        return await self.stop_generation(chat_id, token)
