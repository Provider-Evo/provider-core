"""AItianhu2 异步 HTTP 客户端协调器（多账号版）。

每个 ``Account``（见 ``accounts.py``）在运行时对应一个 ``AccountSession``：
独立 ``aiohttp.ClientSession``、独立 cookie jar、独立 device_id、独立
持久化条目。成功认证的账号会各自暴露为一个 ``Candidate``；调度层（gateway）
可在多个账号之间做限速容错。
"""

from __future__ import annotations

import asyncio
import base64
import mimetypes
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import aiohttp

from src.core.dispatch.candidate import Candidate, make_id
from src.logger import get_logger

from ..accounts import Account, get_enabled_accounts
from .auth import authenticate, fetch_account_id, fetch_carids
from .chat import ChatService, RateLimitError
from .constants import (
    ACCOUNT_ID,
    CAPS,
    CARIDS_REFRESH_INTERVAL,
    MODELS,
    SESSION_EXPIRY_INTERVAL,
    SESSION_REFRESH_INTERVAL,
)
from .models import ModelsService
from .persistence import (
    PERSIST_INTERVAL,
    load_account_state,
    load_all_persist,
    restore_cookie_jar,
    save_account_persist,
    save_all_persist,
)
from .pow import (
    _build_sentinel_config,
    _get_requirements_token,
    _solve_pow,
)
from .sentinel import sentinel_finalize, sentinel_prepare
from .upload import UploadService, image_dimensions

logger = get_logger(__name__)

MAX_RETRIES = 3


@dataclass
class AccountSession:
    """单账号的隔离会话状态。"""

    account: Account
    session: aiohttp.ClientSession
    device_id: str = ""
    authenticated: bool = False
    session_authed_at: float = 0.0
    models: List[str] = field(default_factory=list)
    account_id: str = ""
    account_id_fetched_at: float = 0.0
    upload: Optional[UploadService] = None
    chat: Optional[ChatService] = None
    models_svc: Optional[ModelsService] = None


class Aitianhu2Client:
    """AItianhu2 多账号异步客户端。"""

    def __init__(self) -> None:
        self._account_sessions: Dict[str, AccountSession] = {}
        self._candidates: List[Candidate] = []
        self._closing = False
        self._models: List[str] = list(MODELS)
        self._persist_task: Optional[asyncio.Task] = None
        self._carids_task: Optional[asyncio.Task] = None

        # 共享 carids 缓存（同一服务器对所有账号返回同样的 carids）
        self._carids: List[str] = []
        self._carids_fetched_at: float = 0

        # 上游传入但本客户端不使用；保留接口避免调用方报错
        self._session: Optional[aiohttp.ClientSession] = None

    # ------------------------------------------------------------------
    # 代理接口（aitianhu2 不支持代理，保持签名与平台协议一致）
    # ------------------------------------------------------------------
    def is_proxy_enabled(self) -> bool:
        return False

    def set_proxy_enabled(self, enabled: bool, *, auto: bool = False) -> None:
        del enabled, auto
        return None

    def _get_proxy_kwarg(self) -> None:
        return None

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    async def init_immediate(self, session: aiohttp.ClientSession) -> None:
        """立即初始化：为每个启用账号建立隔离会话并发认证。"""
        self._session = session  # 仅占位；实际用 per-account session
        accounts = get_enabled_accounts()
        if not accounts:
            logger.warning(
                "AItianhu2: 未配置任何已启用的 api_key，"
                "请在 src/platforms/aitianhu2/accounts.py 中填写。"
            )
            return

        all_state = load_all_persist()
        accounts_state = all_state.get("accounts") or {}

        # 共享 carids：在账号认证前先刷新一次，便于所有账号复用
        probe_session: Optional[aiohttp.ClientSession] = None
        try:
            probe_session = aiohttp.ClientSession()
            await self._refresh_carids_into(probe_session)
        finally:
            if probe_session is not None:
                await probe_session.close()

        for account in accounts:
            asess = await self._build_account_session(
                account, accounts_state.get(account.id) or {},
            )
            self._account_sessions[account.id] = asess

        # 并发认证所有账号
        tasks = [
            asyncio.ensure_future(self._authenticate_account(asess))
            for asess in self._account_sessions.values()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for asess, res in zip(self._account_sessions.values(), results):
            if isinstance(res, Exception):
                logger.error(
                    "AItianhu2: 账号 %s 初始化异常: %s",
                    asess.account.id, res,
                )

        self._rebuild_candidates()
        self._save_all_persist()

        ok = sum(1 for a in self._account_sessions.values() if a.authenticated)
        logger.info(
            "AItianhu2 客户端初始化完成：账号 %d/%d 认证成功，候选项 %d",
            ok, len(self._account_sessions), len(self._candidates),
        )

    async def _build_account_session(
        self,
        account: Account,
        state: Dict[str, Any],
    ) -> AccountSession:
        """为一个账号构建隔离会话，并加载其持久化状态。"""
        sess = aiohttp.ClientSession(
            cookie_jar=aiohttp.CookieJar(unsafe=True),
            connector=aiohttp.TCPConnector(limit=32),
        )
        asess = AccountSession(account=account, session=sess)
        asess.device_id = str(state.get("device_id") or "") or str(uuid.uuid4())
        asess.models = list(
            state.get("models")
            if isinstance(state.get("models"), list) and state.get("models")
            else self._models
        )
        asess.authenticated = bool(state.get("authenticated", False))
        asess.session_authed_at = float(state.get("session_authed_at", 0))
        asess.account_id = str(state.get("account_id") or "")
        asess.account_id_fetched_at = float(state.get("account_id_fetched_at", 0))

        cookies = state.get("cookies") or {}
        if isinstance(cookies, dict) and cookies:
            restore_cookie_jar(
                sess,
                {str(k): str(v) for k, v in cookies.items() if v},
            )

        # 硬过期：超过 24h 强制重认证
        if asess.authenticated and asess.session_authed_at > 0:
            age = time.time() - asess.session_authed_at
            if age >= SESSION_EXPIRY_INTERVAL:
                logger.info(
                    "AItianhu2: 账号 %s 持久化会话已过期（%d 秒前认证）",
                    account.id, int(age),
                )
                asess.authenticated = False

        proxy_resolver = self._get_proxy_kwarg
        asess.upload = UploadService(sess, proxy_resolver)
        asess.chat = ChatService(sess, proxy_resolver)
        asess.models_svc = ModelsService(sess, proxy_resolver)
        return asess

    async def _authenticate_account(self, asess: AccountSession) -> None:
        """为单个账号跑完整认证流程；成功后拉 account_id + models。"""
        if asess.authenticated and asess.session_authed_at > 0:
            age = time.time() - asess.session_authed_at
            if age < SESSION_EXPIRY_INTERVAL:
                # 恢复路径：补齐 account_id 与 models
                if not asess.account_id:
                    await self._refresh_account_id(asess)
                await self._refresh_models_for(asess)
                return
        try:
            await authenticate(
                asess.session,
                asess.account.api_key,
                asess.device_id,
                carids=self._carids or None,
            )
            asess.authenticated = True
            asess.session_authed_at = time.time()
            await self._refresh_account_id(asess)
            await self._refresh_models_for(asess)
            self._save_account_persist(asess)
        except Exception as exc:
            asess.authenticated = False
            asess.session_authed_at = 0
            logger.error(
                "AItianhu2: 账号 %s 认证失败: %s",
                asess.account.id, exc,
            )

    async def background_setup(self) -> None:
        """启动后台持久化、健康检查与 carids 周期刷新。"""
        if self._persist_task is None:
            self._persist_task = asyncio.ensure_future(self._bg_persist())
        if any(a.authenticated for a in self._account_sessions.values()):
            asyncio.ensure_future(self._bg_session_health_check())
            if self._carids_task is None:
                self._carids_task = asyncio.ensure_future(self._bg_carids_refresh())

    async def close(self) -> None:
        """关闭所有账号会话与后台任务。"""
        self._closing = True
        for task_name, task in (
            ("持久化", self._persist_task),
            ("carids", self._carids_task),
        ):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.debug("AItianhu2 后台 %s 任务已取消", task_name)
        self._persist_task = None
        self._carids_task = None

        for asess in self._account_sessions.values():
            try:
                if asess.authenticated:
                    self._save_account_persist(asess)
            except Exception as exc:
                logger.debug(
                    "AItianhu2: 账号 %s 关闭前持久化失败: %s",
                    asess.account.id, exc,
                )
            try:
                await asess.session.close()
            except Exception:
                pass
        self._account_sessions.clear()
        logger.info("AItianhu2 客户端已关闭")

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def _save_account_persist(self, asess: AccountSession) -> None:
        save_account_persist(
            asess.account.id,
            asess.session,
            device_id=asess.device_id,
            authenticated=asess.authenticated,
            models=asess.models,
            api_key_hint=asess.account.api_key[-8:],
            session_authed_at=asess.session_authed_at,
            account_id=asess.account_id,
            account_id_fetched_at=asess.account_id_fetched_at,
        )

    def _save_all_persist(self) -> None:
        accounts_payload: Dict[str, Dict[str, Any]] = {}
        for asess in self._account_sessions.values():
            from .persistence import extract_cookie_state
            accounts_payload[asess.account.id] = {
                "device_id": asess.device_id,
                "authenticated": asess.authenticated,
                "models": list(asess.models),
                "api_key_hint": asess.account.api_key[-8:],
                "cookies": extract_cookie_state(asess.session),
                "session_authed_at": asess.session_authed_at,
                "account_id": asess.account_id,
                "account_id_fetched_at": asess.account_id_fetched_at,
                "updated": time.time(),
            }
        carids_payload: Optional[Dict[str, Any]] = None
        if self._carids:
            carids_payload = {
                "ids": list(self._carids),
                "fetched_at": self._carids_fetched_at,
            }
        save_all_persist(accounts_payload, carids=carids_payload)

    async def _bg_persist(self) -> None:
        while not self._closing:
            await asyncio.sleep(PERSIST_INTERVAL)
            if not self._closing:
                try:
                    self._save_all_persist()
                except Exception as exc:
                    logger.warning("AItianhu2: 后台持久化失败: %s", exc)

    # ------------------------------------------------------------------
    # 候选项
    # ------------------------------------------------------------------
    def _rebuild_candidates(self) -> None:
        self._candidates = [
            Candidate(
                id=make_id("aitianhu2", asess.account.api_key[:12]),
                platform="aitianhu2",
                resource_id=asess.account.api_key[:12],
                models=list(asess.models or self._models),
                context_length=128000,
                meta={
                    "api_key": asess.account.api_key,
                    "device_id": asess.device_id,
                    "account_id": asess.account_id,
                    "account_key": asess.account.id,
                },
                **CAPS,
            )
            for asess in self._account_sessions.values()
            if asess.authenticated
        ]

    async def candidates(self) -> List[Candidate]:
        return list(self._candidates)

    async def ensure_candidates(self, count: int) -> int:
        del count
        return len(self._candidates)

    def update_models(self, models: List[str]) -> None:
        self._models = list(models)
        for asess in self._account_sessions.values():
            asess.models = list(models)
        self._rebuild_candidates()
        self._save_all_persist()

    # ------------------------------------------------------------------
    # 聊天补全
    # ------------------------------------------------------------------
    async def complete(
        self,
        candidate: Candidate,
        messages: List[Dict[str, Any]],
        model: str,
        stream: bool,
        *,
        thinking: bool = False,
        search: bool = False,
        system_hints: Optional[List[str]] = None,
        **kw: Any,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        del stream, thinking, search, kw
        account_key = candidate.meta.get("account_key", "")
        asess = self._account_sessions.get(account_key)
        if asess is None or not asess.authenticated:
            raise RuntimeError(
                "AItianhu2: 账号 {} 未认证或不存在".format(account_key or "?"),
            )

        last_exc: Optional[Exception] = None
        next_backoff: float = 1.0
        for attempt in range(MAX_RETRIES):
            if attempt > 0:
                await asyncio.sleep(min(next_backoff, 600.0))
                next_backoff *= 2
            try:
                async for chunk in self._do_request_asess(
                    asess, model, messages, system_hints=system_hints,
                ):
                    yield chunk
                return
            except RateLimitError as exc:
                # 上游 429：尊重服务器给出的冷却秒数，下一轮重试前 sleep
                last_exc = exc
                next_backoff = float(getattr(exc, "cooldown", 180) or 180)
                logger.warning(
                    "AItianhu2 账号 %s 被限流，将在 %ds 后重试 (%d/%d)",
                    asess.account.id, int(next_backoff),
                    attempt + 1, MAX_RETRIES,
                )
            except Exception as exc:
                err_msg = str(exc)
                if "401" in err_msg or "Unauthorized" in err_msg:
                    logger.warning(
                        "AItianhu2: 账号 %s 收到 401，正在重新认证后重试",
                        asess.account.id,
                    )
                    await self._reauthenticate_account(asess)
                    if not asess.authenticated:
                        raise RuntimeError(
                            "AItianhu2: 账号 {} 重新认证失败".format(asess.account.id),
                        )
                last_exc = exc
                logger.warning(
                    "AItianhu2 账号 %s 重试 %d/%d: %s",
                    asess.account.id, attempt + 1, MAX_RETRIES, exc,
                )
        if last_exc is not None:
            raise last_exc

    async def _do_request_asess(
        self,
        asess: AccountSession,
        model: str,
        messages: List[Dict[str, Any]],
        *,
        system_hints: Optional[List[str]] = None,
    ) -> AsyncGenerator[Union[str, Dict[str, Any]], None]:
        assert asess.chat is not None
        assert asess.upload is not None

        device_id = asess.device_id
        api_key = asess.account.api_key
        account_id = asess.account_id

        user_text = ""
        image_urls: List[str] = []
        for message in reversed(messages):
            if message.get("role") != "user":
                continue
            content = message.get("content", "")
            if isinstance(content, list):
                parts_text: List[str] = []
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "text":
                        parts_text.append(part.get("text", ""))
                    elif part.get("type") == "image_url":
                        image_url = part.get("image_url", {})
                        url = (
                            image_url.get("url", "")
                            if isinstance(image_url, dict)
                            else str(image_url)
                        )
                        if url:
                            image_urls.append(url)
                user_text = "\n".join(parts_text)
            else:
                user_text = str(content)
            break

        requirements_token = _get_requirements_token(device_id)
        prepare_resp = await sentinel_prepare(
            asess.session, device_id, api_key, requirements_token,
        )
        prepare_token = prepare_resp.get("prepare_token", "")

        pow_result: Optional[str] = None
        pow_info = prepare_resp.get("proofofwork", {})
        if pow_info.get("required"):
            started_at = time.time()
            base_config = _build_sentinel_config(device_id, started_at)
            pow_result = _solve_pow(
                pow_info.get("seed", "0.8404077132095769"),
                pow_info.get("difficulty", "075c81"),
                base_config, started_at,
            )

        chat_token = (
            await sentinel_finalize(
                asess.session, device_id, api_key, prepare_token, pow_result,
                account_id=account_id,
            )
        ).get("token", "")

        attachments: Optional[List[Dict[str, Any]]] = None
        if image_urls:
            attachments = []
            for url in image_urls:
                file_path = url[7:] if url.startswith("file://") else url
                if url.startswith("http"):
                    logger.warning("AItianhu2: 跳过远程图片 URL: %s", url)
                    continue
                if not os.path.exists(file_path):
                    logger.warning("AItianhu2: 文件不存在: %s", file_path)
                    continue
                result = await asess.upload.upload(
                    device_id, api_key, file_path,
                    account_id=account_id,
                )
                file_id = result["file_id"]
                file_type, _ = mimetypes.guess_type(file_path)
                file_type = file_type or "application/octet-stream"
                attachment: Dict[str, Any] = {
                    "id": file_id,
                    "name": os.path.basename(file_path),
                    "mime_type": file_type,
                    "size": os.path.getsize(file_path),
                    "source": "local",
                }
                if file_type.startswith("image/"):
                    attachment.update(image_dimensions(file_path, file_type))
                metadata = result.get("metadata", {})
                if metadata.get("fileTokenSize"):
                    attachment["file_token_size"] = metadata["fileTokenSize"]
                attachments.append(attachment)
            if not attachments:
                attachments = None

        conv_prepare = await asess.chat.prepare(
            device_id, api_key, model, attachments,
            system_hints=system_hints,
            account_id=account_id,
        )
        conduit_token = (
            conv_prepare.get("conduit_token")
            if isinstance(conv_prepare, dict) else None
        ) or None
        result = await asess.chat.stream(
            device_id, api_key, model, user_text, chat_token, attachments,
            system_hints=system_hints,
            conduit_token=conduit_token,
            account_id=account_id,
        )

        text = result.get("text", "")
        if text:
            yield text

        image_assets = result.get("image_assets", [])
        conversation_id = result.get("conversation_id") or ""
        if image_assets:
            for asset in image_assets:
                resolved = await asess.chat.resolve_image(
                    asset["asset_pointer"],
                    conversation_id,
                    device_id,
                    account_id=account_id,
                )
                local_path = resolved.get("local_path", "")
                if (
                    local_path
                    and os.path.exists(local_path)
                    and local_path.endswith(".png")
                ):
                    with open(local_path, "rb") as file_obj:
                        image_bytes = file_obj.read()
                    image_b64 = base64.b64encode(image_bytes).decode("ascii")
                    yield "\n[Image generated: data:image/png;base64,{}]\n".format(
                        image_b64,
                    )
                else:
                    yield "\n[Image generated: {}]\n".format(
                        asset.get("asset_pointer", ""),
                    )

        await asess.chat.cleanup(
            device_id, api_key, conversation_id,
            account_id=account_id,
        )

    # ------------------------------------------------------------------
    # 账号级刷新
    # ------------------------------------------------------------------
    async def _refresh_account_id(self, asess: AccountSession) -> None:
        """动态拉取 chatgpt-account-id（22h 软刷新）。"""
        if (
            asess.account_id
            and asess.account_id_fetched_at > 0
            and (time.time() - asess.account_id_fetched_at) < SESSION_REFRESH_INTERVAL
        ):
            return
        try:
            aid = await fetch_account_id(
                asess.session, asess.device_id, asess.account.api_key,
            )
        except Exception as exc:
            logger.warning(
                "AItianhu2: 账号 %s 拉取 account_id 失败: %s",
                asess.account.id, exc,
            )
            if not asess.account_id:
                asess.account_id = ACCOUNT_ID
            return
        asess.account_id = aid or ACCOUNT_ID
        asess.account_id_fetched_at = time.time()

    async def _refresh_models_for(self, asess: AccountSession) -> None:
        if asess.models_svc is None:
            return
        try:
            server_models = await asess.models_svc.fetch(
                asess.device_id, asess.account.api_key,
            )
            if server_models:
                asess.models = [
                    model["id"] for model in server_models if model.get("id")
                ]
        except Exception as exc:
            err_msg = str(exc)
            if "401" in err_msg or "Unauthorized" in err_msg:
                logger.warning(
                    "AItianhu2: 账号 %s 收到 401，会话可能已过期",
                    asess.account.id,
                )
                await self._reauthenticate_account(asess, skip_models=True)
            else:
                logger.warning(
                    "AItianhu2: 账号 %s 刷新远端模型列表失败: %s",
                    asess.account.id, exc,
                )

    async def _reauthenticate_account(
        self,
        asess: AccountSession,
        *,
        skip_models: bool = False,
    ) -> None:
        asess.authenticated = False
        try:
            await self._refresh_carids(force=True, clear_cache=True)
            await authenticate(
                asess.session,
                asess.account.api_key,
                asess.device_id,
                carids=self._carids or None,
            )
            asess.authenticated = True
            asess.session_authed_at = time.time()
            asess.account_id = ""
            asess.account_id_fetched_at = 0
            await self._refresh_account_id(asess)
            if not skip_models:
                await self._refresh_models_for(asess)
            self._rebuild_candidates()
            self._save_account_persist(asess)
            logger.info(
                "AItianhu2: 账号 %s 自动重新认证成功", asess.account.id,
            )
        except Exception as exc:
            logger.error(
                "AItianhu2: 账号 %s 自动重新认证失败: %s",
                asess.account.id, exc,
            )
            self._rebuild_candidates()

    async def _bg_session_health_check(self) -> None:
        health_check_interval = 30 * 60
        while not self._closing:
            await asyncio.sleep(health_check_interval)
            if self._closing:
                break
            for asess in list(self._account_sessions.values()):
                if not asess.authenticated:
                    continue
                if asess.session_authed_at > 0:
                    age = time.time() - asess.session_authed_at
                    if age >= SESSION_REFRESH_INTERVAL:
                        logger.info(
                            "AItianhu2: 账号 %s 会话已达软刷新阈值（%d 秒），重新认证",
                            asess.account.id, int(age),
                        )
                        await self._reauthenticate_account(asess)
                        continue
                try:
                    await self._refresh_models_for(asess)
                except Exception as exc:
                    logger.warning(
                        "AItianhu2: 账号 %s 健康检查失败: %s，正在重新认证",
                        asess.account.id, exc,
                    )
                    await self._reauthenticate_account(asess, skip_models=True)
            self._rebuild_candidates()

    # ------------------------------------------------------------------
    # 共享 carids
    # ------------------------------------------------------------------
    async def _refresh_carids_into(
        self,
        session: aiohttp.ClientSession,
        *,
        force: bool = False,
    ) -> None:
        if (
            not force
            and self._carids
            and (time.time() - self._carids_fetched_at < CARIDS_REFRESH_INTERVAL)
        ):
            return
        try:
            new_ids = await fetch_carids(session, force=True)
        except Exception as exc:
            logger.warning("AItianhu2: carids 刷新异常: %s", exc)
            return
        if new_ids:
            self._carids = list(new_ids)
            self._carids_fetched_at = time.time()
            logger.info(
                "AItianhu2: carids 已刷新（%d 个，%s）",
                len(new_ids), "强制" if force else "定时",
            )

    async def _refresh_carids(
        self,
        *,
        force: bool = False,
        clear_cache: bool = False,
    ) -> None:
        if clear_cache:
            from . import auth as _auth_mod
            _auth_mod._carids_cache = []
        probe_session: Optional[aiohttp.ClientSession] = None
        try:
            probe_session = aiohttp.ClientSession()
            await self._refresh_carids_into(probe_session, force=True)
        finally:
            if probe_session is not None:
                await probe_session.close()

    async def _bg_carids_refresh(self) -> None:
        while not self._closing:
            await asyncio.sleep(CARIDS_REFRESH_INTERVAL)
            if self._closing:
                break
            try:
                await self._refresh_carids(force=True)
                if self._carids:
                    self._save_all_persist()
            except Exception as exc:
                logger.warning("AItianhu2: 后台 carids 刷新失败: %s", exc)


# 旧名兼容（部分测试 / 外部调用可能按旧名导入）
__all__ = ["Aitianhu2Client", "AccountSession"]
