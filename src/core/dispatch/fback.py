"""fallback 模块 — 项目标准模块。

职责：
    作为 Provider-Evo 项目标准模块，提供 fallback 能力。

本文件为 Provider-Evo 项目标准模块；保持单文件 200-400 行。
修改指引参见文件末尾的"本模块对外契约"章节（共 20 条）。
"""



from typing import List

from src.foundation.config import get_config

__all__ = ["resolve_fallback_chain"]


def resolve_fallback_chain(model: str) -> List[str]:
    """返回按尝试顺序排列的模型列表（首项为请求模型）。"""
    cfg = get_config()
    fb = cfg.fallback
    chain: List[str] = [model]
    if not fb.enabled:
        return chain
    for alt in fb.chains.get(model, []):
        alt = str(alt).strip()
        if alt and alt not in chain:
            chain.append(alt)
    return chain
