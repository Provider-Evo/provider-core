"""默认套餐方案（命名与 qwenplan 门户一致）。"""
from __future__ import annotations

from typing import Any, Dict, List

DEFAULT_PLANS: List[Dict[str, Any]] = [
    {
        "id": "free",
        "name": "Free",
        "description": "体验入门，适合个人轻度使用",
        "price": 0,
        "requests_per_5h": 120,
        "requests_per_month": 6000,
        "features": ["基础模型访问", "社区支持"],
        "strategy_id": "default",
        "entry_alias": "fast",
    },
    {
        "id": "pro",
        "name": "Pro",
        "description": "推荐方案，适合日常开发与团队协作",
        "price": 29,
        "requests_per_5h": 240,
        "requests_per_month": 12000,
        "features": ["全量 Qwen 模型", "优先路由", "更高配额"],
        "strategy_id": "default",
        "entry_alias": "auto",
    },
    {
        "id": "ultra",
        "name": "Ultra",
        "description": "高强度使用，更大配额与推理模型",
        "price": 99,
        "requests_per_5h": 600,
        "requests_per_month": 30000,
        "features": ["推理模型优先", "最高配额", "专属支持"],
        "strategy_id": "default",
        "entry_alias": "reasoning",
    },
]

# 兼容旧 API 字段名
MARKET_TEMPLATES: List[Dict[str, Any]] = DEFAULT_PLANS
