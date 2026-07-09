"""策略市场模板库。"""
from __future__ import annotations

from typing import Any, Dict, List

MARKET_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "entropy-balanced",
        "name": "Entropy 均衡调度",
        "brand": "entropy",
        "description": "多模型轮询，适合通用 coding 任务",
        "models": ["qwen3-coder-plus", "deepseek-v4-flash-free"],
    },
    {
        "id": "entropy-fast",
        "name": "Entropy 极速",
        "brand": "entropy",
        "description": "优先低延迟免费模型",
        "models": ["mimo-v2.5-free", "north-mini-code-free"],
    },
    {
        "id": "entropy-reasoning",
        "name": "Entropy 推理",
        "brand": "entropy",
        "description": "偏向推理与思考链模型",
        "models": ["nemotron-3-ultra-free", "qwen3.6-plus-free"],
    },
]
