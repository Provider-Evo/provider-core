"""Selector with stale candidate pruning for provider-self."""
from __future__ import annotations

import time

from echotools.dispatch.selector import AdaptiveSelector as _BaseSelector
from echotools.dispatch.selector import TASRecord

from src.logger import get_logger

__all__ = ["Selector", "TASRecord"]

logger = get_logger(__name__)

_DEFAULT_PRUNE_DAYS = 30


class Selector(_BaseSelector):
    """AdaptiveSelector with stale candidate file pruning.

    On initialization, removes persisted JSON records whose file
    modification time exceeds the configured threshold, preventing
    unbounded growth of the candidate store.
    """

    def __init__(
        self,
        persist_dir: str = "persist/dispatch",
        group_attr: str = "group",
        prune_days: int = _DEFAULT_PRUNE_DAYS,
    ) -> None:
        """Initialize selector and prune stale candidate files.

        Args:
            persist_dir: Persistence directory path.
            group_attr: Group attribute name on candidate objects.
            prune_days: Maximum age in days before a candidate file
                is considered stale.  Defaults to 30.
        """
        self._prune_days = prune_days
        super().__init__(persist_dir=persist_dir, group_attr=group_attr)
        self.prune_stale()

    def prune_stale(self) -> int:
        """Remove candidate files not modified within the threshold.

        Iterates over JSON files in the persist directory, deletes those
        whose mtime is older than ``prune_days``, and removes the
        corresponding entries from the in-memory pool.

        Returns:
            Number of candidate files successfully pruned.
        """
        if not self._persist_dir.exists():
            return 0

        cutoff = time.time() - self._prune_days * 86400
        pruned = 0

        for f in self._persist_dir.glob("*.json"):
            if f.name.startswith("_"):
                continue
            try:
                if f.stat().st_mtime < cutoff:
                    key = f.stem
                    f.unlink()
                    self._pool.pop(key, None)
                    pruned += 1
            except Exception as exc:
                logger.debug("failed to prune %s: %s", f.name, exc)

        if pruned:
            logger.info(
                "pruned %d stale candidates (older than %d days)",
                pruned,
                self._prune_days,
            )

        return pruned
