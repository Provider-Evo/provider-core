"""AItianhu2 认证模块。

提供 Super Sponsor key 认证流程，并实现 carids 的动态抓取与缓存。
carids 的持久化由 ``core.client`` 层负责；本模块只维护进程内缓存与
兜底列表。
"""

from __future__ import annotations

import random
import re
from typing import List, Optional

import aiohttp
from yarl import URL

from src.logger import get_logger
from .constants import ACCOUNT_ID, BASE_URL, USER_AGENT
from .headers import build_headers

logger = get_logger(__name__)


async def fetch_account_id(
    session: aiohttp.ClientSession,
    device_id: str,
    api_key: str,
) -> str:
    """动态从服务器挑选最佳 ``chatgpt-account-id``。

    对齐上游 ``_fetch_account_pool``（``main.py:511-554``）：
    付费账号（team/plus/pro/business/enterprise）优先；其余为免费账号；
    最终兜底到 ``ACCOUNT_ID`` 常量。

    Args:
        session: 已认证的 aiohttp 会话。
        device_id: 设备标识。
        api_key: 已认证的 Super Sponsor key。

    Returns:
        服务器推荐的 chatgpt-account-id 字符串。
    """
    try:
        async with session.get(
            f"{BASE_URL}/backend-api/accounts/check/v4-2023-04-27",
            headers={
                **build_headers(device_id),
                "Authorization": f"Bearer {api_key}",
            },
            params={"timezone_offset_min": -480},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                ordering = data.get("account_ordering", []) or []
                accounts = data.get("accounts", {}) or {}

                paid: List[str] = []
                free: List[str] = []
                paid_plans = {"team", "plus", "pro", "business", "enterprise"}
                for aid in ordering:
                    acct = (accounts.get(aid) or {}).get("account") or {}
                    plan = acct.get("plan_type", "")
                    if plan in paid_plans:
                        paid.append(aid)
                    else:
                        free.append(aid)

                pool = paid + free
                if pool:
                    chosen = pool[0]
                    logger.debug(
                        "AItianhu2: 动态选择 account_id=%s (pool=%d, paid=%d)",
                        chosen, len(pool), len(paid),
                    )
                    return chosen
    except Exception as exc:
        logger.warning("AItianhu2: 拉取 account pool 失败: %s", exc)

    return ACCOUNT_ID

# 兜底：当动态抓取失败时使用（与上游 ``main.py`` 中早期版本一致）
_FALLBACK_CARIDS: List[str] = [
    "2lmlv9yb", "vd6ik8uu", "tiogs5rl", "gpjqgznb", "pe1qpt65",
    "ykzuuk80", "4d8x1ofr", "2d5bq6yh", "aed1rpkx", "96tbypd8",
    "i1fgpvve", "k8v8bkxr", "ai08n6ny", "8mx0rdhp", "5tgbliw9",
    "r22ifihy", "kyuys5t8", "1m4ryk4o", "212ddi0s", "vzwga1do",
]

# 进程内缓存：首次抓取成功后填充；跨 authenticate 调用复用。
_carids_cache: List[str] = []


async def fetch_carids(
    session: aiohttp.ClientSession,
    *,
    force: bool = False,
) -> List[str]:
    """动态从落地页抓取 carids 列表。

    对齐上游 ``_fetch_carids()``（``main.py:79-102``）：
    GET ``{BASE_URL}/?model=gpt-5-5``（无 Authorization），
    正则提取 JS 中的 ``var carids = ['xxx', 'yyy', ...]``。

    Args:
        session: 共享的 aiohttp 会话。
        force: 为 True 时强制刷新，绕过进程内缓存。

    Returns:
        carid 列表。动态抓取失败时回退到 ``_FALLBACK_CARIDS``。
    """
    global _carids_cache
    if _carids_cache and not force:
        return list(_carids_cache)

    try:
        async with session.get(
            f"{BASE_URL}/?model=gpt-5-5",
            headers={"User-Agent": USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status == 200:
                text = await resp.text()
                m = re.search(r"var\s+carids\s*=\s*\[([^\]]+)\]", text)
                if m:
                    ids = re.findall(r"'([^']+)'", m.group(1))
                    if ids:
                        _carids_cache = list(ids)
                        logger.info(
                            "AItianhu2: 动态抓取到 %d 个 carids", len(ids),
                        )
                        return list(_carids_cache)
                # 200 OK but regex didn't match — landing page format may have changed.
                # Log a short snippet around the first "carid" occurrence for debugging.
                idx = text.lower().find("carid")
                snippet = text[max(0, idx - 30):idx + 120] if idx >= 0 else text[:200]
                logger.warning(
                    "AItianhu2: 落地页 200 但未匹配到 carids，"
                    "页面格式可能已变更；片段: %r",
                    snippet,
                )
    except Exception as exc:
        logger.warning("AItianhu2: carids 动态抓取失败: %s", exc)

    if _FALLBACK_CARIDS:
        logger.warning("AItianhu2: 回退到兜底 carids 列表")
        _carids_cache = list(_FALLBACK_CARIDS)
        return list(_carids_cache)

    return []


async def authenticate(
    session: aiohttp.ClientSession,
    api_key: str,
    device_id: str,
    *,
    carids: Optional[List[str]] = None,
) -> None:
    """Super Sponsor key 认证流程。

    Args:
        session: 共享的 aiohttp ClientSession。
        api_key: Super Sponsor key。
        device_id: 设备标识。
        carids: 预抓取的 carids 列表；未提供时回退到模块缓存/兜底列表。

    Raises:
        Exception: 密钥被拒绝或认证失败。
    """
    ids = carids or _carids_cache or _FALLBACK_CARIDS
    if not ids:
        raise Exception("AItianhu2: 无可用的 carids（动态抓取与兜底均失败）")
    carid = random.choice(ids)

    # Step 1: 访问 /list 获取初始 cookie（sl-session 等）
    await session.get(
        f"{BASE_URL}/list",
        headers={"User-Agent": USER_AGENT},
        timeout=aiohttp.ClientTimeout(total=30),
    )

    # Step 2: 设置认证 cookie
    jar = session.cookie_jar
    jar.update_cookies({
        "superSponsor": api_key,
        "carid": carid,
    }, response_url=URL(BASE_URL))

    # Step 3: 登录令牌请求
    async with session.get(
        f"{BASE_URL}/auth/logintoken",
        params={"carid": carid, "usertoken": api_key},
        headers={"User-Agent": USER_AGENT},
        allow_redirects=False,
        timeout=aiohttp.ClientTimeout(total=30),
    ) as resp:
        # Check 1: 302 -> /list => 密钥被服务器拒绝
        if resp.status == 302:
            location = resp.headers.get("Location", "")
            if location == "/list":
                raise Exception(
                    "Super Sponsor key 被服务器拒绝，"
                    "请访问 https://fks.aitianhu3.top/ 获取有效密钥。"
                )

        # Check 2 / 3: 200 时检查错误页面（上游 main.py:482-494）
        if resp.status == 200:
            body_text = await resp.text()
            if "wrong-email-credentials" in body_text:
                raise Exception(
                    "Super Sponsor key 无效或已过期"
                    "（服务器返回 wrong-email-credentials），"
                    "请访问 https://fks.aitianhu3.top/ 获取有效密钥。"
                )
            if "login" in body_text.lower():
                raise Exception(
                    "服务器返回登录页面而非会话 cookie，"
                    "密钥可能已失效，请访问 https://fks.aitianhu3.top/。"
                )

    # Step 4: 修复服务器返回的格式异常 cookie 路径
    # 直接遍历内部 cookie 存储，因为 filter_cookies 会过滤掉路径不匹配的 cookie
    base_url = URL(BASE_URL)
    for cookie_name in ("gfsessionid", "SERVERID"):
        to_fix = []
        for (domain, path), cookie_dict in jar._cookies.items():
            morsel = cookie_dict.get(cookie_name)
            if morsel is not None and morsel.get("path", "/") != "/":
                to_fix.append((domain, path, morsel))

        for domain, path, morsel in to_fix:
            jar.clear(lambda m, name=cookie_name: m.key == name)
            morsel["path"] = "/"
            jar.update_cookies({cookie_name: morsel}, response_url=base_url)

    # Step 5: 校验会话 cookie
    cookies = jar.filter_cookies(base_url)
    if not cookies.get("gfsessionid"):
        raise Exception(
            "认证失败：服务器未返回 gfsessionid cookie，密钥可能已过期。"
        )

    logger.debug("AItianhu2 认证成功 [carid=%s]", carid)
