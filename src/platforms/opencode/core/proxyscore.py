"""Proxy scoring and selection for opencode platform.

Tracks per-proxy performance metrics and uses a 4-dimensional scoring
algorithm with TAS-like exploration to select the best proxy from a pool.

Dimensions:
- n_fails: consecutive failure count (lower = better)
- last_success: timestamp of last success (more recent = better)
- ema_latency: EMA of response latency in ms (lower = better)
- n_calls: total call count (more data = more confident)

Persistence: JSON file with atomic write.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger("opencode.proxyscore")


@dataclass
class _ProxyRecord:
    """Performance metrics for a single proxy address."""

    n_fails: int = 0
    last_success: float = 0.0
    ema_latency: float = 0.0
    n_calls: int = 0

    def to_dict(self) -> dict:
        return {
            "n_fails": self.n_fails,
            "last_success": self.last_success,
            "ema_latency": self.ema_latency,
            "n_calls": self.n_calls,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "_ProxyRecord":
        return cls(
            n_fails=data.get("n_fails", 0),
            last_success=data.get("last_success", 0.0),
            ema_latency=data.get("ema_latency", 0.0),
            n_calls=data.get("n_calls", 0),
        )


class ProxyPoolSelector:
    """Pool-level proxy selector with exploration and 4-dimension scoring.

    Usage::

        selector = ProxyPoolSelector("persist/opencode/proxy_score.json")
        selector.update_pool(["1.2.3.4:8080", "5.6.7.8:3128"])
        chosen = selector.select(["1.2.3.4:8080", "5.6.7.8:3128"])
        # ... make request through chosen proxy ...
        selector.record_success(chosen, latency_ms=420.0)
        # or on failure:
        selector.record_failure(chosen)

    Scoring weights (4-dimensional, sum = 1.0):
    - fail_score:     0.30  (penalty for consecutive failures)
    - recency_score:  0.20  (bonus for recent success)
    - latency_score:  0.30  (lower EMA latency = better)
    - confidence:     0.20  (more calls = more confident)

    Exploration: 10% chance to pick the least-used candidate, ensuring
    all proxies are periodically tested.
    """

    _EXPLORATION_RATE: float = 0.10
    _MAX_FAIL_PENALTY: int = 10
    _RECENCY_HALFLIFE: float = 300.0  # 5 minutes
    _LATENCY_CEILING: float = 5000.0  # ms
    _CONFIDENCE_SATURATE: float = 50.0  # calls
    _EMA_ALPHA: float = 0.3

    def __init__(self, persist_path: str) -> None:
        self._path = Path(persist_path)
        self._scores: Dict[str, _ProxyRecord] = {}
        self._load()

    # -----------------------------------------------------------------
    # Pool management
    # -----------------------------------------------------------------

    def update_pool(self, addresses: List[str]) -> None:
        """Synchronize the score table with the current proxy pool.

        New addresses get default (empty) scores. Existing addresses
        retain their accumulated scores.
        """
        current = set(addresses)
        # Add new proxies
        for addr in addresses:
            if addr not in self._scores:
                self._scores[addr] = _ProxyRecord()
        # Remove stale proxies no longer in the pool
        stale = [k for k in self._scores if k not in current]
        for k in stale:
            del self._scores[k]
        self._save()

    # -----------------------------------------------------------------
    # Recording outcomes
    # -----------------------------------------------------------------

    def record_success(self, addr: str, latency_ms: float) -> None:
        """Record a successful request through the given proxy."""
        rec = self._scores.get(addr)
        if rec is None:
            rec = _ProxyRecord()
            self._scores[addr] = rec
        rec.n_fails = 0
        rec.last_success = time.time()
        rec.n_calls += 1
        if rec.ema_latency == 0:
            rec.ema_latency = latency_ms
        else:
            rec.ema_latency = (
                self._EMA_ALPHA * latency_ms
                + (1 - self._EMA_ALPHA) * rec.ema_latency
            )
        self._save()

    def record_failure(self, addr: str) -> None:
        """Record a failed request through the given proxy."""
        rec = self._scores.get(addr)
        if rec is None:
            rec = _ProxyRecord()
            self._scores[addr] = rec
        rec.n_fails += 1
        self._save()

    # -----------------------------------------------------------------
    # Selection
    # -----------------------------------------------------------------

    def select(self, candidates: List[str]) -> Optional[str]:
        """Select the best proxy from *candidates* using TAS-like logic.

        Returns:
            A proxy address string, or None if candidates is empty.
        """
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]

        # Cold start: return candidate with fewest calls
        call_counts = [
            (addr, self._scores.get(addr, _ProxyRecord()).n_calls)
            for addr in candidates
        ]
        if all(c == 0 for _, c in call_counts):
            return candidates[0]

        # 10% exploration: return least-used candidate
        if random.random() < self._EXPLORATION_RATE:
            min_calls = min(c for _, c in call_counts)
            cold = [addr for addr, c in call_counts if c == min_calls]
            return random.choice(cold)

        # Exploitation: return highest-scored candidate
        best_addr: Optional[str] = None
        best_score = float("-inf")
        for addr in candidates:
            rec = self._scores.get(addr, _ProxyRecord())
            s = self._score(rec)
            if s > best_score:
                best_score = s
                best_addr = addr
        return best_addr

    # -----------------------------------------------------------------
    # Scoring
    # -----------------------------------------------------------------

    def _score(self, rec: _ProxyRecord) -> float:
        """Compute composite score for a ProxyRecord. Higher is better."""
        now = time.time()

        # Failure penalty (range: -1.0 to 0.0)
        fail_score = -min(rec.n_fails, self._MAX_FAIL_PENALTY) / float(
            self._MAX_FAIL_PENALTY
        )

        # Recency bonus (range: 0.0 to 1.0)
        if rec.last_success > 0:
            elapsed = now - rec.last_success
            recency_score = 1.0 - min(1.0, elapsed / self._RECENCY_HALFLIFE)
        else:
            recency_score = 0.0

        # Latency score (range: 0.0 to 1.0)
        if rec.n_calls > 0:
            latency_score = max(0.0, 1.0 - rec.ema_latency / self._LATENCY_CEILING)
        else:
            latency_score = 0.5  # no data -> neutral

        # Confidence (range: 0.0 to 1.0)
        confidence = min(1.0, rec.n_calls / self._CONFIDENCE_SATURATE)

        return (
            0.30 * fail_score
            + 0.20 * recency_score
            + 0.30 * latency_score
            + 0.20 * confidence
        )

    # -----------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------

    def _load(self) -> None:
        """Load persisted scores from disk (silent on missing/corrupt)."""
        if not self._path.exists():
            return
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
            for addr, rec_data in data.items():
                self._scores[addr] = _ProxyRecord.from_dict(rec_data)
        except Exception as exc:
            log.warning("Failed to load proxy scores from %s: %s", self._path, exc)

    def _save(self) -> None:
        """Atomically persist scores to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {addr: rec.to_dict() for addr, rec in self._scores.items()}
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(str(tmp), str(self._path))
        except Exception as exc:
            log.warning("Failed to save proxy scores to %s: %s", self._path, exc)
