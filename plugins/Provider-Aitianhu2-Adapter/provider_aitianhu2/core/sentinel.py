"""AItianhu2 Sentinel 模块。

提供哨兵 prepare/finalize 请求。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import aiohttp

from .constants import BASE_URL
from .headers import build_headers


async def sentinel_prepare(
    session: aiohttp.ClientSession,
    device_id: str,
    api_key: str,
    requirements_token: str,
) -> Dict[str, Any]:
    """POST /backend-api/sentinel/chat-requirements/prepare。

    Args:
        session: 共享的 aiohttp ClientSession。
        device_id: 设备标识。
        api_key: API key。
        requirements_token: prepare 阶段的 p 值。

    Returns:
        服务器响应字典。
    """
    headers = {
        **build_headers(device_id),
        "Authorization": f"Bearer {api_key}",
    }
    async with session.post(
        f"{BASE_URL}/backend-api/sentinel/chat-requirements/prepare",
        headers=headers,
        json={"p": requirements_token},
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


async def sentinel_finalize(
    session: aiohttp.ClientSession,
    device_id: str,
    api_key: str,
    prepare_token: str,
    pow_result: Optional[str] = None,
    *,
    account_id: str = "",
) -> Dict[str, Any]:
    """POST /backend-api/sentinel/chat-requirements/finalize。

    Args:
        session: 共享的 aiohttp ClientSession。
        device_id: 设备标识。
        api_key: API key。
        prepare_token: prepare 返回的 token。
        pow_result: PoW 结果（可选）。
        account_id: 动态拉取的 ``chatgpt-account-id``；为空时不发该头。

    Returns:
        服务器响应字典。
    """
    headers = {
        **build_headers(device_id),
        "Authorization": f"Bearer {api_key}",
    }
    if account_id:
        headers["chatgpt-account-id"] = account_id
    body: Dict[str, Any] = {"prepare_token": prepare_token}
    if pow_result:
        body["proofofwork"] = pow_result
    async with session.post(
        f"{BASE_URL}/backend-api/sentinel/chat-requirements/finalize",
        headers=headers,
        json=body,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        resp.raise_for_status()
        return await resp.json()
