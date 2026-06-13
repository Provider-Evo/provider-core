from __future__ import annotations

# Qwen HTTP 客户端（完整多模态实现）
import asyncio
import base64
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple, Union

import aiohttp

from src.core.candidate import Candidate, make_id
from src.core.models_cache import ModelsCache
from src.logger import get_logger
from src.platforms.qwen.accounts import ACCOUNTS, Account
from src.platforms.qwen.core.constants import CAPS, MODELS
from src.platforms.qwen.core.shared import (
    AUTH_CHECK_PATH,
    BASE_URL,
    CHAT_PATH,
    COOKIE_REFRESH_INTERVAL,
    DEFAULT_FULL_SETTINGS,
    DELETE_CHAT_PATH,
    EXTENSION_TO_MIME,
    GENERATED_IMAGE_DIR,
    GENERATED_VIDEO_DIR,
    LOGIN_BATCH,
    LOGIN_CONCURRENCY,
    MODELS_PATH,
    NEW_CHAT_PATH,
    PERSIST_INTERVAL,
    PERSIST_PATH,
    SETTINGS_PATH,
    SIGNIN_PATH,
    SSE_TIMEOUT,
    STS_TOKEN_PATHS,
    STOP_CHAT_PATH,
    TASK_STATUS_PATH,
    TTS_DIR,
    TTS_PATH,
    TTS_TIMEOUT,
    UPLOAD_TEMP_DIR,
    USER_AGENT,
    VIDEO_CDN_BASE,
    VIDEO_TASK_MAX_POLL_TIME,
    VIDEO_TASK_POLL_INTERVAL,
    build_cdn_video_url,
    build_file_object,
    build_headers,
    build_i2v_payload,
    build_login_headers,
    build_new_chat_payload,
    build_payload,
    build_replace_content_payload,
    build_stop_headers,
    build_stop_payload,
    build_tts_payload,
    extract_model_ids,
    generate_cookies,
    generate_fingerprint,
    get_file_category,
    get_mime_type,
    hash_password,
    parse_sse_event,
    save_image_file,
    save_video_file,
    save_wav_file,
)

logger = get_logger(__name__)

MAX_RETRIES: int = 3
LOGIN_TIMEOUT: int = 30
SETTINGS_TIMEOUT: int = 15
OSS_UPLOAD_TIMEOUT: int = 120
HTTP_TIMEOUT: int = 30

_PROXY_AUTO_EXPIRY = 86400


class WAFBlockedError(Exception):
    """Qwen 请求被 WAF 拦截时抛出。"""
    pass


class QwenClient:
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
        self._proxy_auto_enabled_at: Optional[float] = None

    def get_models(self) -> List[str]:
        """返回当前模型列表副本。"""
        return list(self._models)

    # =========================================================================
    # 代理切换
    # =========================================================================

    def set_proxy_enabled(self, enabled: bool, *, auto: bool = False) -> None:
        """设置此平台的代理覆盖开关。

        Args:
            enabled: True 强制使用代理，False 强制不使用。
            auto: 是否为自动启用（用于 24 小时过期逻辑）。
        """
        if enabled:
            self._proxy_override = True
            if auto:
                self._proxy_auto_enabled_at = time.time()
        else:
            self._proxy_override = False
            self._proxy_auto_enabled_at = None

    def _check_proxy_expiry(self) -> None:
        """检查自动代理是否已过期，过期则清除状态。"""
        if self._proxy_auto_enabled_at is not None:
            if time.time() - self._proxy_auto_enabled_at > _PROXY_AUTO_EXPIRY:
                self._proxy_override = None
                self._proxy_auto_enabled_at = None

    def is_proxy_enabled(self) -> bool:
        """返回此平台当前是否启用代理。"""
        if self._proxy_override is None:
            return False
        if self._proxy_override:
            self._check_proxy_expiry()
        return bool(self._proxy_override)

    def _get_proxy_kwarg(self) -> Optional[str]:
        """获取应传递给 session.request 的 proxy 值。"""
        self._check_proxy_expiry()
        if self._proxy_override is True:
            from src.core.config import get_config
            cfg = get_config()
            if not cfg.platforms_proxy.is_platform_enabled("qwen"):
                return None
            from src.core.proxy import get_proxy_server
            return get_proxy_server()
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

        logger.info(
            "Qwen 客户端立即初始化完成，初始候选项: %d 个",
            len(self._candidates),
        )

    async def background_setup(self) -> None:
        """后台完善——在后台 Task 中执行。"""
        await self._bg_login()

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
        logger.info("Qwen 后台任务已启动")

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
                logger.info("Qwen: 从持久化恢复 Cookie")

            loaded = sum(
                1 for acc in self._account_states.values() if acc.token
            )
            logger.debug("Qwen: 从持久化恢复 %d 个账号 token", loaded)

            proxy_state = data.get("proxy", {})
            if proxy_state:
                from src.core.config import get_config
                cfg = get_config()
                if cfg.platforms_proxy.is_platform_enabled("qwen"):
                    self._proxy_override = proxy_state.get("enabled")
                    auto_at = proxy_state.get("auto_enabled_at")
                    if auto_at is not None:
                        self._proxy_auto_enabled_at = float(auto_at)
                        if time.time() - self._proxy_auto_enabled_at > _PROXY_AUTO_EXPIRY:
                            self._proxy_override = None
                            self._proxy_auto_enabled_at = None
        except Exception as e:
            logger.warning("Qwen 持久化加载失败: %s", e)

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
                    "proxy": {
                        "enabled": self._proxy_override,
                        "auto_enabled_at": self._proxy_auto_enabled_at,
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
    # 登录与 Token 管理
    # =========================================================================

    async def _bg_login(self) -> None:
        """并发批量登录所有账号。"""
        sem = asyncio.Semaphore(LOGIN_CONCURRENCY)

        async def _do_one(acc: Account) -> None:
            async with sem:
                if self._closing:
                    return
                # is_login=False 的账号尝试重新登录
                if not acc.is_login:
                    acc.token = ""  # 清除旧 token
                elif acc.token and await self._validate_token(acc):
                    return
                try:
                    await self._login(acc)
                except Exception as e:
                    logger.error(
                        "Qwen 登录失败 [%s***]: %s", acc.username[:6], e
                    )

        accounts_list = list(self._account_states.values())
        for i in range(0, len(accounts_list), LOGIN_BATCH):
            if self._closing:
                break
            batch = accounts_list[i: i + LOGIN_BATCH]
            await asyncio.gather(
                *[_do_one(acc) for acc in batch],
                return_exceptions=True,
            )

        logged = sum(
            1 for acc in self._account_states.values() if acc.token
        )
        logger.info("Qwen 登录完成: %d/%d", logged, len(self._account_states))
        self._save_persist()

    async def _validate_token(self, acc: Account) -> bool:
        """验证账号 token 是否仍然有效。

        Args:
            acc: 账号对象。

        Returns:
            有效返回 True，否则 False。
        """
        if not acc.token:
            return False
        try:
            headers = {
                "authorization": "Bearer {}".format(acc.token),
                "content-type": "application/json;charset=UTF-8",
                "source": "web",
                "user-agent": USER_AGENT,
                "origin": BASE_URL,
                "referer": "{}/".format(BASE_URL),
                "accept": "application/json",
            }
            url = "{}{}".format(BASE_URL, AUTH_CHECK_PATH)
            async with self._session.get(
                url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def _login(self, acc: Account) -> None:
        """登录单个账号，成功后立即重建候选项。

        Args:
            acc: 账号对象。

        Raises:
            Exception: 重试耗尽后仍失败。
        """
        pwd_hash = acc.password_hash or hash_password(acc.password)
        headers = build_login_headers()
        payload = {"email": acc.username, "password": pwd_hash}

        # Ensure cookies are set on the session before login
        if self._session and self._cookies:
            from yarl import URL
            self._session.cookie_jar.update_cookies(
                self._cookies,
                response_url=URL(BASE_URL),
            )

        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                url = "{}{}".format(BASE_URL, SIGNIN_PATH)
                async with self._session.post(
                    url,
                    headers=headers,
                    json=payload,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=LOGIN_TIMEOUT),
                ) as resp:
                    if resp.status != 200:
                        err = await resp.text()
                        # WAF detection: if response is HTML, the endpoint is blocked
                        content_type = resp.headers.get("Content-Type", "")
                        if "text/html" in content_type or err.strip().startswith("<!"):
                            last_exc = Exception(
                                "登录接口被 WAF 拦截 (HTTP {})。请检查 IP 是否可用或启用代理。".format(resp.status)
                            )
                        else:
                            last_exc = Exception(
                                "HTTP {}: {}".format(resp.status, err[:200])
                            )
                        continue

                    data = await resp.json()
                    token = data.get("token", "")
                    if not token:
                        last_exc = Exception("响应中缺少 token")
                        continue

                    acc.token = token
                    acc.user_id = data.get("id", "")
                    acc.password_hash = pwd_hash
                    acc.token_expires = float(data.get("expires_at", 0))
                    acc.memory_disabled = False
                    acc.is_login = True

                    asyncio.ensure_future(self._update_settings(acc))
                    self._rebuild_candidates()
                    return
            except Exception as e:
                last_exc = e

        if last_exc:
            raise last_exc

    async def _update_settings(self, acc: Account) -> None:
        """同步用户设置（关闭记忆功能等）。

        Args:
            acc: 账号对象。
        """
        if not acc.token or acc.memory_disabled:
            return
        headers = build_headers(acc.token, cookies=self._cookies)
        url = "{}{}".format(BASE_URL, SETTINGS_PATH)
        try:
            async with self._session.post(
                url,
                headers=headers,
                json=DEFAULT_FULL_SETTINGS,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=SETTINGS_TIMEOUT),
            ) as resp:
                if resp.status == 200:
                    acc.memory_disabled = True
                else:
                    err = await resp.text()
                    logger.warning(
                        "Qwen 设置同步失败 [%s***]: HTTP %d: %s",
                        acc.username[:6],
                        resp.status,
                        err[:200],
                    )
        except Exception as e:
            logger.warning(
                "Qwen 设置同步异常 [%s***]: %s", acc.username[:6], e
            )

    # =========================================================================
    # Cookie 后台刷新
    # =========================================================================

    async def _bg_cookie_refresh(self) -> None:
        """后台定期刷新指纹和 Cookie。"""
        while not self._closing:
            await asyncio.sleep(COOKIE_REFRESH_INTERVAL)
            if not self._closing:
                self._fp = generate_fingerprint()
                self._cookies = generate_cookies(self._fp)
                logger.debug("Qwen: Cookie 已刷新")

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
                        logger.info(
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
    # 文件上传（OSS STS）
    # =========================================================================

    async def _get_sts_credentials(
        self,
        token: str,
        filename: str,
        filesize: int,
        filetype: str,
    ) -> Dict[str, Any]:
        """获取 OSS STS 临时上传凭据。

        Args:
            token: Bearer 令牌。
            filename: 文件名。
            filesize: 文件大小（字节）。
            filetype: 文件类型（image/video/audio/file）。

        Returns:
            STS 凭据字典（含 access_key_id/secret/security_token/file_url/file_path）。

        Raises:
            Exception: 所有 STS 端点均失败。
        """
        headers = {
            "authorization": "Bearer {}".format(token),
            "content-type": "application/json;charset=UTF-8",
            "source": "web",
            "user-agent": USER_AGENT,
            "origin": BASE_URL,
            "referer": "{}/".format(BASE_URL),
            "accept": "application/json",
        }
        payload = {
            "filename": filename,
            "filesize": filesize,
            "filetype": filetype,
        }

        last_err: Optional[Exception] = None
        for path in STS_TOKEN_PATHS:
            url = "{}{}".format(BASE_URL, path)
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status != 200:
                        last_err = Exception(
                            "HTTP {}: {}".format(
                                resp.status,
                                (await resp.text())[:200],
                            )
                        )
                        continue
                    data = await resp.json()
                    creds = data.get("data", data)
                    if all(
                        k in creds
                        for k in (
                            "access_key_id",
                            "access_key_secret",
                            "security_token",
                        )
                    ):
                        return creds
                    last_err = Exception("STS 凭据格式异常: {}".format(data))
            except Exception as e:
                last_err = e

        raise Exception(
            "所有 STS 端点均失败: {}".format(last_err)
        )

    async def _upload_to_oss(
        self,
        file_data: bytes,
        filename: str,
        content_type: str,
        creds: Dict[str, Any],
    ) -> str:
        """使用 OSS STS 临时凭据 PUT 上传文件。

        Args:
            file_data: 文件字节数据。
            filename: 文件名（用于 MIME 推断）。
            content_type: 文件 MIME 类型。
            creds: STS 凭据字典。

        Returns:
            上传成功后的 OSS 文件 URL。

        Raises:
            Exception: OSS PUT 失败。
        """
        from urllib.parse import urlparse

        file_url = creds.get("file_url", "")
        obj_key = creds.get("file_path", "")
        security_token = creds.get("security_token", "")
        access_key_id = creds.get("access_key_id", "")
        access_key_secret = creds.get("access_key_secret", "")

        parsed = urlparse(file_url)
        bucket_host = parsed.netloc
        bucket_name = bucket_host.split(".")[0]
        resource = "/{}/{}".format(bucket_name, obj_key)

        from datetime import datetime, timezone
        gmt_date = datetime.now(timezone.utc).strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        oss_headers = {"x-oss-security-token": security_token}
        from src.platforms.qwen.core.shared import build_oss_authorization
        auth = build_oss_authorization(
            "PUT",
            content_type,
            gmt_date,
            oss_headers,
            resource,
            access_key_id,
            access_key_secret,
        )

        headers = {
            "Host": bucket_host,
            "Date": gmt_date,
            "Content-Type": content_type,
            "Content-Length": str(len(file_data)),
            "Authorization": auth,
            "x-oss-security-token": security_token,
            "User-Agent": USER_AGENT,
        }
        oss_url = "https://{}/{}".format(bucket_host, obj_key)

        async with self._session.put(
            oss_url,
            data=file_data,
            headers=headers,
            ssl=False,
            timeout=aiohttp.ClientTimeout(total=OSS_UPLOAD_TIMEOUT),
        ) as resp:
            if resp.status not in (200, 201):
                err = await resp.text()
                raise Exception(
                    "OSS PUT {} {}: {}".format(resp.status, oss_url, err[:300])
                )
        return file_url

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """完整文件上传流程：获取 STS 凭据 -> OSS PUT -> 构建文件对象。

        支持图片、视频、音频、文档的上传。
        单文件最大 500MB（视频），其他类型 20MB。

        Args:
            file_data: 文件字节数据。
            filename: 文件名（含扩展名，用于 MIME 推断）。
            token: Bearer 令牌。
            user_id: 用户 ID（用于文件对象构建）。

        Returns:
            Qwen API 文件对象字典，可直接用于 messages.files 字段。

        Raises:
            Exception: 文件过大、STS 获取失败或 OSS 上传失败。
        """
        content_type = get_mime_type(filename)
        file_type, _ = get_file_category(content_type)
        file_size = len(file_data)

        # 文件大小检查
        max_sizes = {
            "video": 500 * 1024 * 1024,
            "audio": 100 * 1024 * 1024,
            "image": 20 * 1024 * 1024,
            "file": 20 * 1024 * 1024,
        }
        max_size = max_sizes.get(file_type, 20 * 1024 * 1024)
        if file_size > max_size:
            raise Exception(
                "文件过大: {} ({} bytes > {} bytes)".format(
                    filename, file_size, max_size
                )
            )
        if file_size == 0:
            raise Exception("文件为空: {}".format(filename))

        # 获取 STS 凭据（带重试）
        creds: Optional[Dict[str, Any]] = None
        last_exc: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                creds = await self._get_sts_credentials(
                    token, filename, file_size, file_type
                )
                break
            except Exception as e:
                last_exc = e

        if creds is None:
            raise Exception(
                "获取 STS 凭据失败: {}".format(last_exc)
            )

        # OSS PUT 上传（带重试）
        file_url = ""
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                file_url = await self._upload_to_oss(
                    file_data, filename, content_type, creds
                )
                break
            except Exception as e:
                last_exc = e

        if not file_url:
            file_url = creds.get("file_url", "")
            logger.warning("OSS 上传失败，使用预签名 URL: %s", last_exc)

        file_id = creds.get("file_id", str(uuid.uuid4()))
        return build_file_object(
            file_id=file_id,
            file_url=file_url,
            filename=filename,
            size=file_size,
            content_type=content_type,
            user_id=user_id,
        )

    async def upload_file_from_path(
        self,
        file_path: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """从本地路径上传文件。

        Args:
            file_path: 本地文件路径。
            token: Bearer 令牌。
            user_id: 用户 ID。

        Returns:
            Qwen API 文件对象字典。

        Raises:
            Exception: 文件不存在或上传失败。
        """
        if not os.path.exists(file_path):
            raise Exception("文件不存在: {}".format(file_path))
        filename = os.path.basename(file_path)
        file_data = Path(file_path).read_bytes()
        return await self.upload_file(file_data, filename, token, user_id)

    async def upload_file_from_base64(
        self,
        data_uri: str,
        token: str,
        user_id: str,
    ) -> Dict[str, Any]:
        """从 Base64 数据 URI 上传文件。

        支持 data:{mime};base64,{data} 格式。

        Args:
            data_uri: Base64 数据 URI 字符串。
            token: Bearer 令牌。
            user_id: 用户 ID。

        Returns:
            Qwen API 文件对象字典。

        Raises:
            Exception: 格式错误或上传失败。
        """
        if not data_uri.startswith("data:") or ";base64," not in data_uri:
            raise Exception("无效的 Base64 数据 URI")

        header, encoded = data_uri.split(";base64,", 1)
        mime_type = header.split("data:", 1)[1]

        # 推断扩展名
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "video/mp4": ".mp4",
            "application/pdf": ".pdf",
        }
        ext = ext_map.get(mime_type, ".bin")
        filename = "upload_{}{}".format(uuid.uuid4().hex[:8], ext)

        # 解码 Base64
        padding = 4 - len(encoded) % 4
        if padding != 4:
            encoded += "=" * padding
        file_data = base64.b64decode(encoded)

        return await self.upload_file(file_data, filename, token, user_id)

    def _extract_base64_images(
        self, messages: List[Dict[str, Any]]
    ) -> List[str]:
        """从消息中提取所有 base64 data URI 图片。

        Args:
            messages: OpenAI 格式消息列表。

        Returns:
            base64 data URI 列表。
        """
        uris: List[str] = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "image_url":
                        img_url_obj = part.get("image_url", {})
                        img_url = (
                            img_url_obj.get("url", "")
                            if isinstance(img_url_obj, dict)
                            else str(img_url_obj)
                        )
                        if img_url.startswith("data:"):
                            uris.append(img_url)
        return uris

    # =========================================================================
    # 图片下载
    # =========================================================================

    async def download_image(
        self,
        image_url: str,
        save_dir: str = GENERATED_IMAGE_DIR,
    ) -> Optional[str]:
        """下载生成的图片并保存到本地。

        Args:
            image_url: 图片 CDN URL。
            save_dir: 保存目录。

        Returns:
            本地文件路径，失败返回 None。
        """
        try:
            headers = {
                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Connection": "keep-alive",
                "Origin": BASE_URL,
                "Referer": "{}/".format(BASE_URL),
                "User-Agent": USER_AGENT,
            }
            async with self._session.get(
                image_url,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status != 200:
                    return None
                image_data = await resp.read()
                ct = resp.headers.get("Content-Type", "image/png")
                return save_image_file(image_data, ct, save_dir)
        except Exception as e:
            logger.debug("图片下载失败: %s", e)
            return None

    # =========================================================================
    # 视频生成（i2v）
    # =========================================================================

    async def _poll_task_status(
        self,
        task_id: str,
        token: str,
        chat_id: str,
    ) -> Dict[str, Any]:
        """轮询异步任务状态（视频生成等）。

        Args:
            task_id: 任务 ID。
            token: Bearer 令牌。
            chat_id: 对话 ID（用于 Referer）。

        Returns:
            任务成功完成后的状态字典。

        Raises:
            Exception: 任务失败或轮询超时。
        """
        url = "{}{}".format(
            BASE_URL,
            TASK_STATUS_PATH.format(task_id=task_id),
        )
        headers = build_headers(
            token,
            chat_id=chat_id,
            include_sse=False,
            cookies=self._cookies,
        )

        start = time.time()
        while time.time() - start < VIDEO_TASK_MAX_POLL_TIME:
            try:
                async with self._session.get(
                    url,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        ts = data.get("task_status", "")
                        logger.debug("任务 %s: %s", task_id, ts)
                        if ts == "succeeded":
                            return data
                        if ts == "failed":
                            raise Exception(
                                "任务失败: {}".format(
                                    data.get("message", "未知")
                                )
                            )
            except Exception as e:
                if "任务失败" in str(e):
                    raise
                logger.debug("轮询异常: %s", e)
            await asyncio.sleep(VIDEO_TASK_POLL_INTERVAL)

        raise Exception(
            "任务轮询超时 ({}s)".format(VIDEO_TASK_MAX_POLL_TIME)
        )

    async def generate_video(
        self,
        prompt: str,
        image_url: str,
        token: str,
        user_id: str,
        model: str = "qwen-max-latest",
        size: str = "16:9",
        image_name: str = "source.png",
        download: bool = True,
    ) -> Dict[str, Any]:
        """图片到视频生成（i2v）完整流程。

        流程：创建 i2v 对话 -> 提交任务 -> 轮询状态 -> 构建 CDN URL -> 可选下载。

        Args:
            prompt: 视频生成描述。
            image_url: 参考图片 URL（已上传到 OSS）。
            token: Bearer 令牌。
            user_id: 用户 ID。
            model: 模型名称。
            size: 视频尺寸（16:9/9:16/1:1）。
            image_name: 参考图片文件名。
            download: 是否下载视频到本地。

        Returns:
            包含 success/video_url/local_path/task_id/error 的结果字典。
        """
        # 创建 i2v 对话
        try:
            chat_id = await self._create_chat(token, model, "i2v")
        except Exception as e:
            return {
                "success": False,
                "error": "创建 i2v 对话失败: {}".format(e),
            }

        payload = build_i2v_payload(
            prompt=prompt,
            chat_id=chat_id,
            model=model,
            image_url=image_url,
            image_name=image_name,
            size=size,
        )
        headers = build_headers(token, chat_id=chat_id, cookies=self._cookies)
        url = "{}{}?chat_id={}".format(BASE_URL, CHAT_PATH, chat_id)

        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=SSE_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    asyncio.ensure_future(
                        self._cleanup_chat(chat_id, token)
                    )
                    return {
                        "success": False,
                        "error": "HTTP {}: {}".format(
                            resp.status, err[:300]
                        ),
                    }

                data = await resp.json()
                if not data.get("success"):
                    asyncio.ensure_future(
                        self._cleanup_chat(chat_id, token)
                    )
                    return {"success": False, "error": str(data)}

                result_data = data.get("data", {})
                message_id = result_data.get("message_id", "")
                task_id = ""

                messages = result_data.get("messages", [])
                if messages:
                    wanx = messages[0].get("extra", {}).get("wanx", {})
                    task_id = wanx.get("task_id", "")

                if not task_id:
                    asyncio.ensure_future(
                        self._cleanup_chat(chat_id, token)
                    )
                    return {
                        "success": False,
                        "error": "响应中未找到 task_id",
                    }
        except Exception as e:
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return {"success": False, "error": str(e)}

        # 轮询任务状态
        try:
            task_result = await self._poll_task_status(
                task_id, token, chat_id
            )
        except Exception as e:
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e),
            }

        # 构建 CDN URL
        video_url = task_result.get("content") or build_cdn_video_url(
            user_id=user_id,
            video_type="i2v",
            message_id=message_id,
            task_id=task_id,
            token=token,
        )

        result: Dict[str, Any] = {
            "success": True,
            "task_id": task_id,
            "message_id": message_id,
            "chat_id": chat_id,
            "video_url": video_url,
            "size": size,
        }

        # 可选下载
        if download and video_url:
            try:
                dl_headers = {
                    "Accept": "*/*",
                    "Origin": BASE_URL,
                    "Referer": "{}/".format(BASE_URL),
                    "User-Agent": USER_AGENT,
                }
                async with self._session.get(
                    video_url,
                    headers=dl_headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=SSE_TIMEOUT),
                ) as resp:
                    if resp.status == 200:
                        video_data = await resp.read()
                        local_path = save_video_file(video_data)
                        if local_path:
                            result["local_path"] = local_path
                            logger.info(
                                "视频已下载: %s", local_path
                            )
            except Exception as e:
                logger.debug("视频下载失败: %s", e)

        asyncio.ensure_future(self._cleanup_chat(chat_id, token))
        return result

    # =========================================================================
    # TTS 语音合成
    # =========================================================================

    async def _replace_message_content(
        self,
        chat_id: str,
        response_id: str,
        new_content: str,
        origin_content: str,
        token: str,
    ) -> bool:
        """替换消息内容（TTS 前置步骤）。

        TTS 流程需要先用目标文本替换助手消息内容，再请求 TTS。

        Args:
            chat_id: 对话 ID。
            response_id: 助手消息 ID。
            new_content: 新内容（TTS 目标文本）。
            origin_content: 原始内容（用于 token 估算）。
            token: Bearer 令牌。

        Returns:
            True 表示替换成功，False 表示失败。
        """
        url = "{}/api/v2/chats/{}/messages/{}".format(
            BASE_URL, chat_id, response_id
        )
        headers = build_headers(token, chat_id=chat_id, cookies=self._cookies)
        payload = build_replace_content_payload(new_content, origin_content)

        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(1.0 * (2 ** (attempt - 1)))
            try:
                async with self._session.post(
                    url,
                    json=payload,
                    headers=headers,
                    ssl=False,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        return True
                    err = await resp.text()
                    logger.warning(
                        "内容替换失败 HTTP %d: %s", resp.status, err[:200]
                    )
            except Exception as e:
                logger.warning("内容替换异常: %s", e)

        return False

    async def request_tts(
        self,
        chat_id: str,
        response_id: str,
        token: str,
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """请求 TTS 语音合成，将响应 PCM 数据保存为 WAV 文件。

        通过 /api/v2/tts/completions SSE 接口接收 Base64 PCM 音频片段，
        拼接后封装为 WAV 文件。

        Args:
            chat_id: 对话 ID。
            response_id: 助手消息 ID（被 TTS 合成的消息）。
            token: Bearer 令牌。
            save_dir: WAV 文件保存目录。

        Returns:
            WAV 文件路径，失败返回 None。
        """
        headers = build_headers(
            token,
            chat_id=chat_id,
            include_sse=True,
            cookies=self._cookies,
        )
        headers["Accept"] = "*/*"
        payload = build_tts_payload(chat_id, response_id)
        url = "{}{}" "?chat_id={}".format(BASE_URL, TTS_PATH, chat_id)

        chunks: List[str] = []
        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=TTS_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    logger.warning(
                        "TTS 请求失败 HTTP %d", resp.status
                    )
                    return None

                buf = b""
                async for raw in resp.content.iter_any():
                    if not raw:
                        continue
                    buf += raw
                    lines = buf.split(b"\n")
                    buf = lines[-1]

                    for lb in lines[:-1]:
                        ls = lb.decode("utf-8", errors="replace").strip()
                        if not ls or not ls.startswith("data:"):
                            continue
                        ds = ls[5:].lstrip()
                        if not ds or ds == "[DONE]":
                            continue
                        try:
                            d = json.loads(ds)
                            if "choices" in d and d["choices"]:
                                delta = d["choices"][0].get("delta", {})
                                tts_data = delta.get("tts")
                                if tts_data and tts_data.strip():
                                    chunks.append(tts_data)
                                if delta.get("status") == "finished":
                                    break
                        except (json.JSONDecodeError, KeyError):
                            continue
        except Exception as e:
            logger.warning("TTS 请求异常: %s", e)
            return None

        if not chunks:
            logger.warning("TTS 响应为空，无音频数据")
            return None

        # 解码 Base64 PCM 并保存为 WAV
        try:
            combined = "".join(chunks)
            padding = 4 - len(combined) % 4
            if padding != 4:
                combined += "=" * padding
            pcm_data = base64.b64decode(combined)
            return save_wav_file(pcm_data, save_dir)
        except Exception as e:
            logger.warning("TTS 音频解码失败: %s", e)
            return None

    async def synthesize_tts(
        self,
        text: str,
        token: str,
        model: str = "qwen3.6-plus",
        save_dir: str = TTS_DIR,
    ) -> Optional[str]:
        """完整 TTS 合成流程。

        流程：
        1. 创建新对话
        2. 发送占位消息获取 response_id
        3. 替换消息内容为目标文本
        4. 请求 TTS 合成
        5. 后台清理对话

        Args:
            text: 需要合成语音的文本。
            token: Bearer 令牌。
            model: 模型名称。
            save_dir: WAV 文件保存目录。

        Returns:
            WAV 文件路径，失败返回 None。
        """
        # 创建新对话
        try:
            chat_id = await self._create_chat(token, model, "t2t")
        except Exception as e:
            logger.warning("TTS 创建对话失败: %s", e)
            return None

        # 发送占位消息（快速获取 response_id）
        quick_msg = "注意：啥都不要说，直接输出\\即可"
        response_id: Optional[str] = None
        origin_content = ""

        try:
            payload = build_payload(
                messages=[{"role": "user", "content": quick_msg}],
                model=model,
                chat_id=chat_id,
                thinking_enabled=False,
                auto_thinking=False,
                thinking_mode="Fast",
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

            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    buf = b""
                    async for raw in resp.content.iter_any():
                        if not raw:
                            continue
                        buf += raw
                        lines = buf.split(b"\n")
                        buf = lines[-1]
                        for lb in lines[:-1]:
                            ls = lb.decode("utf-8", errors="replace").strip()
                            if not ls or not ls.startswith("data:"):
                                continue
                            ds = ls[5:].lstrip()
                            if not ds or ds == "[DONE]":
                                continue
                            try:
                                event = parse_sse_event(ds)
                                if event and event.get("type") == "response_created":
                                    response_id = event.get("response_id")
                                elif event and event.get("type") == "answer":
                                    origin_content += event.get(
                                        "content", ""
                                    )
                            except Exception:
                                continue
        except Exception as e:
            logger.warning("TTS 占位消息失败: %s", e)
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        if not response_id:
            logger.warning("TTS 未获取到 response_id")
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        # 替换消息内容
        success = await self._replace_message_content(
            chat_id, response_id, text, origin_content.strip(), token
        )
        if not success:
            logger.warning("TTS 内容替换失败")
            asyncio.ensure_future(self._cleanup_chat(chat_id, token))
            return None

        # 请求 TTS 合成
        audio_path = await self.request_tts(chat_id, response_id, token, save_dir)

        # 后台清理对话
        asyncio.ensure_future(self._cleanup_chat(chat_id, token))

        if audio_path:
            logger.info("TTS 合成成功: %s", audio_path)
        else:
            logger.warning("TTS 合成失败，无音频输出")

        return audio_path

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
                if not self.is_proxy_enabled():
                    # 检查是否被允许使用代理切换
                    from src.core.config import get_config
                    cfg = get_config()
                    if cfg.platforms_proxy.is_platform_enabled("qwen"):
                        logger.warning("Qwen: 检测到 WAF 拦截，自动启用代理 24 小时")
                        self.set_proxy_enabled(True, auto=True)
                        self._save_persist()
                last_exc = None  # 清除 last_exc，让重试使用新代理
                logger.warning(
                    "Qwen WAF 重试 %d/%d（代理已启用）", attempt + 1, MAX_RETRIES
                )
            except Exception as e:
                last_exc = e
                logger.warning(
                    "Qwen 重试 %d/%d: %s", attempt + 1, MAX_RETRIES, e
                )
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
            thinking_format = "summary"
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
            if self._proxy_override is not None:
                post_kw["proxy"] = self._get_proxy_kwarg()

            async with self._session.post(url, **post_kw) as resp:
                if resp.status != 200:
                    err = await resp.text()
                    # 检测 token 过期或未授权错误
                    if resp.status == 401 or "Token has expired" in err or "unauthorized" in err.lower():
                        username = candidate.meta.get("username", "")
                        if username and username in self._account_states:
                            acc = self._account_states[username]
                            logger.warning("账号 [%s] token 已过期，设置 is_login=False", username)
                            acc.is_login = False
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

        except (aiohttp.ClientPayloadError, aiohttp.http_exceptions.PayloadEncodingError) as e:
            # 传输中断（如 TransferEncodingError、ContentEncodingError 等），
            # 已 yield 的数据已发出，不向上抛出，避免重试循环
            logger.warning("Qwen 流式响应被截断，已收集部分数据: %s", e)
        except Exception as e:
            # 其他未知异常，记录日志后向上传播
            logger.error("Qwen _do_request 未知异常: %s", e, exc_info=True)
            raise
        finally:
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
