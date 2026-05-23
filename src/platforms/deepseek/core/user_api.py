from __future__ import annotations

# src/platforms/deepseek/core/user_api.py
"""DeepSeek 用户相关 API 封装（登录/注册/验证码/设置等）"""

import secrets
import uuid
from typing import Any, Dict, Optional, Tuple

from src.logger import get_logger

import aiohttp

from src.platforms.deepseek.core.constants import DEFAULT_HOST
from src.platforms.deepseek.core.headers import build_basic_headers, build_headers

logger = get_logger(__name__)


def _make_device_id() -> str:
    """生成随机设备 ID（UUID v4 格式）。

    Returns:
        UUID 字符串。
    """
    return str(uuid.uuid4())


async def login(
    session: aiohttp.ClientSession,
    username: str,
    password: str,
) -> Tuple[str, str]:
    """邮箱或手机号密码登录。

    Args:
        session: aiohttp ClientSession。
        username: 邮箱或手机号。
        password: 密码。

    Returns:
        (token, user_id) 二元组。

    Raises:
        Exception: 登录失败时抛出，含详细错误信息。
    """
    is_email = "@" in username
    payload: Dict[str, Any] = {
        "password": password,
        "device_id": _make_device_id(),
        "os": "web",
    }
    if is_email:
        payload["email"] = username
        payload["mobile"] = ""
        payload["area_code"] = ""
    else:
        payload["email"] = ""
        payload["mobile"] = username
        payload["area_code"] = "+86"

    headers = build_basic_headers()
    async with session.post(
        "https://{}/api/v0/users/login".format(DEFAULT_HOST),
        headers=headers,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=30),
        ssl=False,
    ) as resp:
        if resp.status != 200:
            raise Exception("登录 HTTP 错误 {}".format(resp.status))
        data = await resp.json()
        biz_code = data.get("data", {}).get("biz_code", -1)
        if biz_code != 0:
            biz_msg = data.get("data", {}).get("biz_msg", str(data))
            raise Exception("登录业务错误 {}: {}".format(biz_code, biz_msg))
        biz_data = data["data"]["biz_data"]
        user = biz_data.get("user", {})
        token = user.get("token", "")
        user_id = user.get("id", "")
        return str(token), str(user_id)


async def login_by_sms(
    session: aiohttp.ClientSession,
    mobile_number: str,
    sms_code: str,
    area_code: str = "+86",
) -> Tuple[str, str]:
    """手机短信验证码登录。

    Args:
        session: aiohttp ClientSession。
        mobile_number: 手机号码。
        sms_code: 短信验证码。
        area_code: 区号。

    Returns:
        (token, user_id) 二元组。

    Raises:
        Exception: 登录失败时抛出。
    """
    headers = build_basic_headers()
    payload = {
        "mobile_number": mobile_number,
        "area_code": area_code,
        "sms_verification_code": sms_code,
        "device_id": _make_device_id(),
        "os": "web",
    }
    async with session.post(
        "https://{}/api/v0/users/login_by_mobile_sms".format(DEFAULT_HOST),
        headers=headers,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=30),
        ssl=False,
    ) as resp:
        if resp.status != 200:
            raise Exception("短信登录 HTTP 错误 {}".format(resp.status))
        data = await resp.json()
        biz_code = data.get("data", {}).get("biz_code", -1)
        if biz_code != 0:
            raise Exception("短信登录失败: {}".format(data))
        user = data["data"]["biz_data"]["user"]
        return str(user.get("token", "")), str(user.get("id", ""))


async def send_sms_code(
    session: aiohttp.ClientSession,
    mobile_number: str,
    scenario: str = "mobile_login",
    area_code: str = "+86",
) -> bool:
    """发送短信验证码。

    Args:
        session: aiohttp ClientSession。
        mobile_number: 手机号码。
        scenario: 场景（register/mobile_login/reset_password 等）。
        area_code: 区号。

    Returns:
        是否发送成功。
    """
    headers = build_basic_headers()
    payload = {
        "locale": "zh_CN",
        "device_id": _make_device_id(),
        "scenario": scenario,
        "mobile_number": mobile_number,
        "area_code": area_code,
    }
    try:
        async with session.post(
            "https://{}/api/v0/users/create_sms_verification_code".format(
                DEFAULT_HOST
            ),
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
            ssl=False,
        ) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            return data.get("data", {}).get("biz_code", -1) == 0
    except Exception as exc:
        logger.warning("send_sms_code 失败: %s", exc)
        return False


async def send_email_code(
    session: aiohttp.ClientSession,
    email: str,
    scenario: str = "register",
) -> bool:
    """发送邮箱验证码。

    Args:
        session: aiohttp ClientSession。
        email: 邮箱地址。
        scenario: 场景（register/reset_password）。

    Returns:
        是否发送成功。
    """
    headers = build_basic_headers()
    payload = {
        "email": email,
        "locale": "zh_CN",
        "device_id": _make_device_id(),
        "scenario": scenario,
    }
    try:
        async with session.post(
            "https://{}/api/v0/users/create_email_verification_code".format(
                DEFAULT_HOST
            ),
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=30),
            ssl=False,
        ) as resp:
            if resp.status != 200:
                return False
            data = await resp.json()
            return data.get("data", {}).get("biz_code", -1) == 0
    except Exception as exc:
        logger.warning("send_email_code 失败: %s", exc)
        return False


async def get_current_user(
    session: aiohttp.ClientSession,
    token: str,
) -> Optional[Dict[str, Any]]:
    """获取当前登录用户信息。

    Args:
        session: aiohttp ClientSession。
        token: Bearer 令牌。

    Returns:
        用户信息字典或 None。
    """
    headers = build_headers(token)
    try:
        async with session.get(
            "https://{}/api/v0/users/current".format(DEFAULT_HOST),
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=False,
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("data", {}).get("biz_data", {}).get("user")
    except Exception as exc:
        logger.warning("get_current_user 失败: %s", exc)
        return None


async def logout(
    session: aiohttp.ClientSession,
    token: str,
) -> bool:
    """登出当前会话。

    Args:
        session: aiohttp ClientSession。
        token: Bearer 令牌。

    Returns:
        是否成功。
    """
    headers = build_headers(token)
    try:
        async with session.post(
            "https://{}/api/v0/users/logout".format(DEFAULT_HOST),
            headers=headers,
            json={},
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=False,
        ) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.warning("logout 失败: %s", exc)
        return False


async def logout_all(
    session: aiohttp.ClientSession,
    token: str,
) -> bool:
    """登出所有设备。

    Args:
        session: aiohttp ClientSession。
        token: Bearer 令牌。

    Returns:
        是否成功。
    """
    headers = build_headers(token)
    try:
        async with session.post(
            "https://{}/api/v0/users/logout_all_sessions".format(DEFAULT_HOST),
            headers=headers,
            json={},
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=False,
        ) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.warning("logout_all 失败: %s", exc)
        return False


async def get_user_settings(
    session: aiohttp.ClientSession,
    token: str,
) -> Optional[Dict[str, Any]]:
    """获取用户设置。

    Args:
        session: aiohttp ClientSession。
        token: Bearer 令牌。

    Returns:
        设置字典或 None。
    """
    headers = build_headers(token)
    try:
        async with session.get(
            "https://{}/api/v0/users/settings".format(DEFAULT_HOST),
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=False,
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("data", {}).get("biz_data")
    except Exception as exc:
        logger.warning("get_user_settings 失败: %s", exc)
        return None


async def update_user_settings(
    session: aiohttp.ClientSession,
    token: str,
    training_allowed: bool,
) -> bool:
    """更新用户设置。

    Args:
        session: aiohttp ClientSession。
        token: Bearer 令牌。
        training_allowed: 是否允许数据训练。

    Returns:
        是否成功。
    """
    headers = build_headers(token)
    try:
        async with session.post(
            "https://{}/api/v0/users/update_settings".format(DEFAULT_HOST),
            headers=headers,
            json={"training_allowed": training_allowed},
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=False,
        ) as resp:
            return resp.status == 200
    except Exception as exc:
        logger.warning("update_user_settings 失败: %s", exc)
        return False


async def get_client_settings(
    session: aiohttp.ClientSession,
    device_id: str,
    scope: str = "",
) -> Optional[Dict[str, Any]]:
    """获取远程特征开关。

    Args:
        session: aiohttp ClientSession。
        device_id: 设备 ID。
        scope: 作用域（可选）。

    Returns:
        设置字典或 None。
    """
    headers = build_basic_headers()
    params: Dict[str, str] = {"did": device_id}
    if scope:
        params["scope"] = scope
    try:
        async with session.get(
            "https://{}/api/v0/client/settings".format(DEFAULT_HOST),
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
            ssl=False,
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("data", {}).get("biz_data")
    except Exception as exc:
        logger.warning("get_client_settings 失败: %s", exc)
        return None


async def export_all_history(
    session: aiohttp.ClientSession,
    token: str,
) -> Optional[Dict[str, Any]]:
    """导出所有历史数据。

    Args:
        session: aiohttp ClientSession。
        token: Bearer 令牌。

    Returns:
        导出状态字典或 None。
    """
    headers = build_headers(token)
    try:
        async with session.get(
            "https://{}/api/v0/users/export_all".format(DEFAULT_HOST),
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=30),
            ssl=False,
        ) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("data", {}).get("biz_data")
    except Exception as exc:
        logger.warning("export_all_history 失败: %s", exc)
        return None
