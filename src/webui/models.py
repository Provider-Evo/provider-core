from __future__ import annotations

"""WebUI 视图模型。"""

from dataclasses import dataclass
from typing import List

__all__ = ["DocLink", "DocSection"]


@dataclass(frozen=True)
class DocLink:
    """在线文档链接。"""

    title: str
    description: str
    href: str


@dataclass(frozen=True)
class DocSection:
    """在线文档分组。"""

    title: str
    items: List[DocLink]
