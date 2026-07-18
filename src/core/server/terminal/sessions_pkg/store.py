from __future__ import annotations

"""终端会话存储主类。"""

from pathlib import Path
from typing import Optional

from src.foundation.logger import get_logger
from src.core.server.terminal.sessions_pkg.cleanup import SessionCleanupMixin
from src.core.server.terminal.sessions_pkg.meta import SessionMetadataMixin
from src.core.server.terminal.sessions_pkg.output import SessionOutputMixin

__all__ = ["TerminalSessionStore", "get_terminal_store"]

logger = get_logger(__name__)

_DEFAULT_MAX_OUTPUT_BYTES: int = 5 * 1024 * 1024
_DEFAULT_DESTROYED_RETENTION: int = 300

_store: Optional["TerminalSessionStore"] = None


class TerminalSessionStore(SessionMetadataMixin, SessionOutputMixin, SessionCleanupMixin):
    """持久化终端会话元数据及离线输出。

    所有文件 I/O 操作均捕获异常并记录日志，不向调用方抛出存储层错误，
    确保终端功能在持久化失败时仍可降级运行。
    """

    def __init__(
        self,
        persist_dir: Path,
        max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
    ) -> None:
        self.persist_dir = persist_dir
        self.max_output_bytes = max_output_bytes
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("TerminalSessionStore 初始化: persist_dir=%s", persist_dir)


def get_terminal_store(persist_dir: Optional[Path] = None) -> TerminalSessionStore:
    """获取或创建模块级 TerminalSessionStore 单例。

    采用惰性初始化策略：首次调用时根据 ``persist_dir`` 参数创建
    实例并缓存；后续调用始终返回同一实例，忽略 ``persist_dir`` 参数。
    """
    global _store
    if _store is not None:
        return _store

    if persist_dir is None:
        from src.foundation.paths import persist_dir as _default_persist_dir
        persist_dir = _default_persist_dir("terminal")

    _store = TerminalSessionStore(persist_dir)
    logger.debug("全局 TerminalSessionStore 单例已创建: %s", persist_dir)
    return _store
