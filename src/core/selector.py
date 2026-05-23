from __future__ import annotations

import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

from src.core.candidate import Candidate
from src.logger import get_logger

__all__ = ["Selector", "CandidateStats"]
logger = get_logger(__name__)

# TAS 超参数
W = 200      # 滑动窗口大小
MS = 3       # 最小样本数
ER = 0.1     # 初始探索率
DC = 0.995   # 探索率衰减
ME = 0.02    # 最小探索率
LW = 0.4     # 延迟权重
SW = 0.4     # 成功率权重
TW = 0.2     # 吞吐量权重
CD = 30.0    # 冷却时间基数（秒）


@dataclass
class _S:
    """单次请求采样记录。"""

    ts: float
    lat: float
    ok: bool
    tok: int
    dur: float


@dataclass
class CandidateStats:
    """候选项性能统计（Beta 分布 + EMA）。"""

    alpha: float = 1.0
    beta_p: float = 1.0
    reqs: int = 0
    succ: int = 0
    fail: int = 0
    ema_lat: float = 1.0
    ema_thr: float = 10.0
    ft: float = 0.0
    fs: int = 0
    explores: int = 0
    exploits: int = 0
    samples: Deque[_S] = field(default_factory=lambda: deque(maxlen=W))

    def record_ok(self, lat: float, tok: int, dur: float) -> None:
        """记录一次成功请求。

        Args:
            lat: 首 token 延迟（秒）。
            tok: 生成 token 数。
            dur: 总耗时（秒）。
        """
        self.reqs += 1
        self.succ += 1
        self.fs = 0
        self.alpha += 1
        a = 0.2
        self.ema_lat = a * lat + (1 - a) * self.ema_lat
        if dur > 0 and tok > 0:
            self.ema_thr = a * (tok / dur) + (1 - a) * self.ema_thr
        self.samples.append(_S(time.time(), lat, True, tok, dur))

    def record_fail(self) -> None:
        """记录一次失败请求。"""
        self.reqs += 1
        self.fail += 1
        self.fs += 1
        self.ft = time.time()
        self.beta_p += 1
        self.samples.append(_S(time.time(), float("inf"), False, 0, 0))

    @property
    def sr(self) -> float:
        """成功率（Beta 分布均值）。"""
        return self.alpha / (self.alpha + self.beta_p)

    @property
    def var(self) -> float:
        """Beta 分布方差。"""
        t = self.alpha + self.beta_p
        return (self.alpha * self.beta_p) / (t * t * (t + 1))

    @property
    def cooling(self) -> bool:
        """是否处于冷却状态。"""
        return self.fs > 0 and time.time() - self.ft < CD * min(self.fs, 10)

    def score(self) -> float:
        """综合评分。

        Returns:
            综合评分值（越高越好）。
        """
        nl = 1 / (1 + math.exp(self.ema_lat - 2))
        nt = 1 / (1 + math.exp(-(self.ema_thr - 5) / 5))
        return SW * self.sr + LW * nl + TW * nt

    def thompson(self) -> float:
        """Thompson 采样。

        Returns:
            Beta 分布随机样本。
        """
        try:
            x = random.gammavariate(self.alpha, 1)
            y = random.gammavariate(self.beta_p, 1)
            return x / (x + y) if x + y > 0 else 0.5
        except (ValueError, ZeroDivisionError):
            return 0.5

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（用于 /v1/status）。

        Returns:
            统计字典。
        """
        return {
            "alpha": self.alpha,
            "beta_p": self.beta_p,
            "reqs": self.reqs,
            "succ": self.succ,
            "fail": self.fail,
            "ema_lat": round(self.ema_lat, 3),
            "ema_thr": round(self.ema_thr, 1),
            "score": round(self.score(), 4),
            "sr": round(self.sr, 4),
            "cooling": self.cooling,
        }


class Selector:
    """TAS 选择器（无锁，依赖 asyncio 单线程事件循环）。

    所有 select/record 调用均在同一事件循环中串行执行，
    Python GIL 保证 dict/dataclass 字段赋值的原子性，
    因此无需 asyncio.Lock。
    """

    def __init__(self) -> None:
        """初始化选择器。"""
        self._st: Dict[str, CandidateStats] = {}
        self._eps = ER
        self._n = 0

    def _e(self, cid: str) -> CandidateStats:
        """获取或创建候选项统计。

        Args:
            cid: 候选项 ID。

        Returns:
            统计对象。
        """
        if cid not in self._st:
            self._st[cid] = CandidateStats()
        return self._st[cid]

    async def select(
        self, cands: List[Candidate], count: int = 1
    ) -> List[Candidate]:
        """选择候选项（TAS 算法）。

        Args:
            cands: 候选项列表。
            count: 需要选择的数量。

        Returns:
            选中的候选项列表。
        """
        if not cands:
            return []
        # 过滤冷却中的候选项，全部冷却时取冷却时间最短的
        act = [c for c in cands if not self._e(c.id).cooling] or sorted(
            cands, key=lambda c: self._e(c.id).ft
        )[:1]
        self._n += 1
        sel: List[Candidate] = []
        for _ in range(min(count, len(act))):
            rem = [c for c in act if c not in sel]
            if not rem:
                break
            # 单候选项时直接返回，不走 TAS 判断
            if len(rem) == 1:
                p = rem[0]
                self._e(p.id).exploits += 1
                sel.append(p)
                continue
            stop = self._stop(rem)
            explore = random.random() < self._eps
            if stop and not explore:
                p = max(rem, key=lambda c: self._e(c.id).score())
                self._e(p.id).exploits += 1
            else:
                p = self._ts(rem)
                self._e(p.id).explores += 1
            sel.append(p)
        self._eps = max(ME, self._eps * DC)
        return sel

    def _stop(self, cs: List[Candidate]) -> bool:
        """判断是否停止探索（TAS 停止准则）。

        Args:
            cs: 候选项列表（至少 2 个）。

        Returns:
            是否应该停止探索。
        """
        for c in cs:
            if self._e(c.id).reqs < MS:
                return False
        rk = sorted(cs, key=lambda c: self._e(c.id).score(), reverse=True)
        s0, s1 = self._e(rk[0].id), self._e(rk[1].id)
        return (
            s0.score() - s1.score() > math.sqrt(s0.var) + math.sqrt(s1.var)
            and s0.reqs >= MS * 2
        )

    def _ts(self, cs: List[Candidate]) -> Candidate:
        """Thompson 采样选择。

        Args:
            cs: 候选项列表。

        Returns:
            Thompson 采样选中的候选项。
        """
        best_s, best = -1.0, cs[0]
        for c in cs:
            s = self._e(c.id)
            sc = (
                SW * s.thompson()
                + LW * (
                    1 / (1 + math.exp(s.ema_lat - 2)) + random.gauss(0, 0.05)
                )
                + TW * (
                    1 / (1 + math.exp(-(s.ema_thr - 5) / 5))
                    + random.gauss(0, 0.05)
                )
            )
            if sc > best_s:
                best_s, best = sc, c
        return best

    async def record(
        self,
        cid: str,
        success: bool,
        latency: float = 0,
        tokens: int = 0,
        duration: float = 0,
    ) -> None:
        """记录请求结果指标。

        Args:
            cid: 候选项 ID。
            success: 是否成功。
            latency: 首 token 延迟（秒）。
            tokens: 生成 token 数。
            duration: 总耗时（秒）。
        """
        s = self._e(cid)
        if success:
            s.record_ok(latency, tokens, duration)
        else:
            s.record_fail()

    async def get_stats(self) -> Dict[str, Any]:
        """获取全部候选项统计数据。

        Returns:
            统计字典（cid -> 统计）。
        """
        return {k: v.to_dict() for k, v in self._st.items()}
