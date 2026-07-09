"""AItianhu2 模型列表模块。

提供从服务器获取可用模型列表的功能。
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import aiohttp

from .constants import BASE_URL, BUILD_HASH, USER_AGENT
from .headers import build_headers


class ModelsService:
    """模型列表服务。

    负责从服务器获取可用模型列表。
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        proxy_resolver: Callable[[], Optional[str]],
    ) -> None:
        """初始化模型服务。

        Args:
            session: 共享的 aiohttp ClientSession。
            proxy_resolver: 代理解析回调。
        """
        self._session = session
        self._resolve_proxy = proxy_resolver

    async def fetch(
        self,
        device_id: str,
        api_key: str,
    ) -> List[Dict[str, Any]]:
        """GET /backend-api/models — 获取服务器可用模型列表。

        Args:
            device_id: 设备标识。
            api_key: API key。

        Returns:
            模型信息列表。
        """
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "oai-client-version": BUILD_HASH,
            "oai-device-id": device_id,
            "oai-language": "zh-CN",
            "origin": BASE_URL,
            "referer": f"{BASE_URL}/",
            "user-agent": USER_AGENT,
        }
        async with self._session.get(
            f"{BASE_URL}/backend-api/models",
            headers=headers,
            params={"iim": "false", "is_gizmo": "false"},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()

        models: List[Dict[str, Any]] = []
        for cat in data.get("categories", []):
            default = cat.get("default_model", "")
            name = cat.get("human_category_name", "")
            category = cat.get("category", "")
            features = cat.get("supported_features", [])
            level = cat.get("subscription_level", "")
            if default:
                models.append({
                    "id": default,
                    "name": name,
                    "category": category,
                    "features": features,
                    "subscription_level": level,
                })
            for mid in cat.get("supported_models", []):
                if mid != default:
                    models.append({
                        "id": mid,
                        "name": name,
                        "category": category,
                        "features": features,
                        "subscription_level": level,
                    })
        return models
