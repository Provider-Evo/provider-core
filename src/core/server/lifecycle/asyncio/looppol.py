
from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional, Tuple

from src.foundation.logger import get_logger

__all__ = ["configure_event_loop_policy"]

logger = get_logger(__name__)

_MIN_UVLOOP_PY314: Tuple[int, int, int] = (0, 22, 1)


def _parse_version(version: str) -> Tuple[int, ...]:
    parts: list[int] = []
    for piece in version.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            break
    return tuple(parts) or (0,)


def _uvloop_version() -> Optional[Tuple[int, ...]]:
    try:
        from importlib.metadata import version as pkg_version

        return _parse_version(pkg_version("uvloop"))
    except Exception:
        return None


def _uvloop_requested() -> bool:
    return os.environ.get("PROVIDER_USE_UVLOOP", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def configure_event_loop_policy() -> None:
    """按平台与 Python 版本选择 asyncio 事件循环实现。"""
    if sys.platform == "win32":
        if sys.version_info < (3, 12):
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        return

    if sys.version_info >= (3, 14) and not _uvloop_requested():
        logger.info(
            "Python 3.14 默认禁用 uvloop（避免 SIGSEGV）；"
            "需启用时安装 uvloop>=0.22.1 并设置 PROVIDER_USE_UVLOOP=1"
        )
        return

    try:
        import uvloop  # type: ignore[import]  # noqa: F401
    except ImportError:
        logger.debug("uvloop 未安装，使用默认 asyncio 事件循环")
        return

    uv_ver = _uvloop_version()
    if sys.version_info >= (3, 14):
        if uv_ver is None or uv_ver < _MIN_UVLOOP_PY314:
            logger.warning(
                "Python 3.14 需要 uvloop>=%s，当前 %s；使用默认 asyncio",
                ".".join(str(part) for part in _MIN_UVLOOP_PY314),
                ".".join(str(part) for part in uv_ver) if uv_ver else "unknown",
            )
            return
        uvloop.install()
        logger.debug(
            "uvloop.install() 已启用 (version %s)",
            ".".join(str(part) for part in uv_ver),
        )
        return

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.debug("uvloop EventLoopPolicy 已启用")
