from __future__ import annotations

import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.dispatch.candidate import Candidate
from src.logger import get_logger

__all__ = ["Selector", "TASRecord", "TASWeights"]
logger = get_logger(__name__)

# TAS 超参数
MS = 3       # 最小样本数（停止探索阈值）
ER = 0.1     # 初始探索率（epsilon）
DC = 0.995   # 探索率衰减
ME = 0.02    # 最小探索率
CD = 30.0    # 冷却时间基数（秒）
EMA_A = 0.2  # EMA 平滑系数


@dataclass
class TASRecord:
    """候选项持久化指标记录。

    每个候选项对应一个记录，持久化到 persist/gateway/ 目录。
    包含 5 个核心变量用于自动调优评分：
    error_time、last_call、ema_speed、ema_latency、n_fails。
    """

    platform: str = ""
    error_time: float = 0.0
    last_call: float = 0.0
    ema_speed: float = 0.0
    ema_latency: float = 0.0
    n_calls: int = 0
    n_fails: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """转换为 /v1/status 响应格式。"""
        now = time.time()
        cooling = (
            self.n_fails > 0
            and self.error_time > 0
            and (now - self.error_time) < CD * min(self.n_fails, 10)
        )
        return {
            "platform": self.platform,
            "error_time": round(self.error_time, 3),
            "last_call": round(self.last_call, 3),
            "ema_speed": round(self.ema_speed, 1),
            "ema_latency": round(self.ema_latency, 3),
            "n_calls": self.n_calls,
            "n_fails": self.n_fails,
            "cooling": cooling,
        }


@dataclass
class TASWeights:
    """自适应评分权重（5 维权重，sum=1.0）。

    权重通过 _tune_weights() 在每次 record() 后自动调整：
    成功请求强化与正结果相关的维度权重，
    失败请求削弱导致负结果的维度权重。
    """

    w_err: float = 0.2
    w_call: float = 0.2
    w_speed: float = 0.2
    w_lat: float = 0.2
    w_fails: float = 0.2


class Selector:
    """TAS 选择器（无锁，依赖 asyncio 单线程事件循环）。

    基于 5 个核心变量的自适应评分系统：
    - error_time: 最新 API 出错时间
    - last_call: 最新调用时间
    - ema_speed: token 生成速度（EMA）
    - ema_latency: 首包延迟（EMA）
    - n_fails: 连续失败次数

    评分权重通过自动调优动态调整，持久化到 persist/gateway/ 目录。
    """

    def __init__(self, persist_dir: str = "persist/gateway") -> None:
        self._pool: Dict[str, TASRecord] = {}
        self._cf: Dict[str, int] = {}
        self._w = TASWeights()
        self._eps = ER
        self._n = 0
        self._persist_dir = Path(persist_dir)
        self._load()

    def _load(self) -> None:
        """从 persist/gateway/ 加载所有候选项记录和权重。"""
        if not self._persist_dir.exists():
            self._persist_dir.mkdir(parents=True, exist_ok=True)
            return

        wf = self._persist_dir / "_weights.json"
        if wf.exists():
            try:
                data = json.loads(wf.read_text(encoding="utf-8"))
                self._w = TASWeights(**data)
            except Exception as e:
                logger.warning("加载 TAS 权重失败: %s", e)

        count = 0
        for f in self._persist_dir.glob("*.json"):
            if f.name.startswith("_"):
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                self._pool[f.stem] = TASRecord(**data)
                count += 1
            except Exception:
                pass
        if count:
            logger.info("从持久化加载 %d 条 TAS 记录", count)

    def _ensure(self, key: str, platform: str = "") -> TASRecord:
        """获取或创建候选项记录。"""
        if key not in self._pool:
            self._pool[key] = TASRecord(platform=platform)
        return self._pool[key]

    def _save_record(self, key: str, r: TASRecord) -> None:
        """原子写入单个候选项记录到 JSON 文件。"""
        f = self._persist_dir / "{}.json".format(key)
        tmp = str(f) + ".tmp"
        try:
            Path(tmp).write_text(
                json.dumps(asdict(r), indent=2), encoding="utf-8"
            )
            os.replace(tmp, str(f))
        except Exception as e:
            logger.warning("保存 TAS 记录 [%s] 失败: %s", key, e)

    def _save_weights(self) -> None:
        """原子写入自适应权重到 JSON 文件。"""
        f = self._persist_dir / "_weights.json"
        tmp = str(f) + ".tmp"
        try:
            Path(tmp).write_text(
                json.dumps(asdict(self._w), indent=2), encoding="utf-8"
            )
            os.replace(tmp, str(f))
        except Exception as e:
            logger.warning("保存 TAS 权重失败: %s", e)

    def _cooling(self, key: str) -> bool:
        """判断候选项是否处于冷却状态。"""
        r = self._pool.get(key)
        if r is None or r.error_time <= 0:
            return False
        cf = self._cf.get(key, 0)
        if cf <= 0:
            return False
        return time.time() - r.error_time < CD * min(cf, 10)

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

        act = [c for c in cands if not self._cooling(c.id)] or sorted(
            cands, key=lambda c: self._pool.get(c.id, TASRecord()).error_time
        )[:1]

        self._n += 1
        mean_speed, mean_lat = self._pool_means(act)
        sel: List[Candidate] = []

        for _ in range(min(count, len(act))):
            rem = [c for c in act if c not in sel]
            if not rem:
                break

            if len(rem) == 1:
                sel.append(rem[0])
                continue

            stop = self._stop(rem, mean_speed, mean_lat)
            explore = random.random() < self._eps

            if stop and not explore:
                p = max(
                    rem,
                    key=lambda c: self._score_one(
                        self._ensure(c.id, c.platform), mean_speed, mean_lat
                    ),
                )
            else:
                p = self._explore(rem, mean_speed, mean_lat)
            sel.append(p)

        self._eps = max(ME, self._eps * DC)
        return sel

    def _pool_means(
        self, cands: List[Candidate]
    ) -> tuple:
        """计算候选池的速度和延迟均值（仅已有数据的候选）。"""
        speeds = []
        lats = []
        for c in cands:
            r = self._pool.get(c.id)
            if r:
                if r.ema_speed > 0:
                    speeds.append(r.ema_speed)
                if r.ema_latency > 0:
                    lats.append(r.ema_latency)
        mean_s = sum(speeds) / len(speeds) if speeds else 10.0
        mean_l = sum(lats) / len(lats) if lats else 2.0
        return mean_s, mean_l

    def _stop(
        self,
        cs: List[Candidate],
        mean_speed: float,
        mean_lat: float,
    ) -> bool:
        """判断是否停止探索。

        所有候选 n_calls >= MS 且前两名分差足够大时停止。
        """
        for c in cs:
            r = self._pool.get(c.id)
            if not r or r.n_calls < MS:
                return False

        scored = [
            (c, self._score_one(self._ensure(c.id, c.platform), mean_speed, mean_lat))
            for c in cs
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        s0, s1 = scored[0][1], scored[1][1]
        return (s0 - s1) > 0.1 and self._ensure(
            scored[0][0].id, scored[0][0].platform
        ).n_calls >= MS * 2

    def _score_one(
        self, r: TASRecord, mean_speed: float, mean_lat: float
    ) -> float:
        """计算单个候选项的综合评分。

        基于 5 个核心变量 + 自适应权重：
        1. 错误惩罚（error_time 越近惩罚越重）
        2. 调用新鲜度（last_call 越近数据越可信）
        3. 速度评分（ema_speed 越高越好）
        4. 延迟评分（ema_latency 越低越好）
        5. 连续失败惩罚（n_fails 越大惩罚越重，上限 10）
        """
        now = time.time()

        if r.error_time > 0:
            err_score = math.exp(-(now - r.error_time) / 300.0)
        else:
            err_score = 0.0

        if r.last_call > 0:
            call_score = 1.0 / (1.0 + (now - r.last_call) / 600.0)
        else:
            call_score = 0.0

        center_s = max(mean_speed, 1.0)
        speed_score = 1.0 / (1.0 + math.exp(-(r.ema_speed - center_s) / center_s))

        center_l = max(mean_lat, 0.5)
        lat_score = 1.0 / (1.0 + math.exp((r.ema_latency - center_l) / center_l))

        fails_score = min(r.n_fails, 10) / 10.0

        w = self._w
        return (
            -w.w_err * err_score
            + w.w_call * call_score
            + w.w_speed * speed_score
            + w.w_lat * lat_score
            - w.w_fails * fails_score
        )

    def _explore(
        self,
        cs: List[Candidate],
        mean_speed: float,
        mean_lat: float,
    ) -> Candidate:
        """探索选择：评分 + 高斯噪声。"""
        best_s, best = -float("inf"), cs[0]
        for c in cs:
            r = self._ensure(c.id, c.platform)
            sc = self._score_one(r, mean_speed, mean_lat) + random.gauss(0, 0.05)
            if sc > best_s:
                best_s, best = sc, c
        return best

    def _tune_weights(self, r: TASRecord, success: bool) -> None:
        """基于单次请求结果微调权重（乘法更新 + 归一化）。

        成功时强化与正结果相关的维度权重，
        失败时削弱导致负结果的维度权重。
        """
        lr = 0.02
        now = time.time()
        w = self._w

        err_sig = (
            1.0 - math.exp(-(now - r.error_time) / 300.0)
            if r.error_time > 0
            else 1.0
        )
        call_sig = (
            1.0 / (1.0 + (now - r.last_call) / 600.0)
            if r.last_call > 0
            else 0.0
        )
        speed_sig = min(r.ema_speed / 50.0, 1.0) if r.ema_speed > 0 else 0.5
        lat_sig = 1.0 / (1.0 + r.ema_latency) if r.ema_latency > 0 else 0.5
        fails_sig = 1.0 - min(r.n_fails, 10) / 10.0

        if success:
            w.w_err *= 1.0 + lr * err_sig
            w.w_call *= 1.0 + lr * call_sig
            w.w_speed *= 1.0 + lr * speed_sig
            w.w_lat *= 1.0 + lr * lat_sig
            w.w_fails *= 1.0 + lr * fails_sig
        else:
            w.w_err *= 1.0 - lr * (1.0 - err_sig)
            w.w_call *= 1.0 - lr * (1.0 - call_sig)
            w.w_speed *= 1.0 - lr * speed_sig
            w.w_lat *= 1.0 - lr * lat_sig
            w.w_fails *= 1.0 - lr * (1.0 - fails_sig)

        total = w.w_err + w.w_call + w.w_speed + w.w_lat + w.w_fails
        if total > 0:
            w.w_err /= total
            w.w_call /= total
            w.w_speed /= total
            w.w_lat /= total
            w.w_fails /= total

    async def record(
        self,
        cid: str,
        success: bool,
        latency: float = 0,
        tokens: int = 0,
        duration: float = 0,
        generation_dur: float = 0,
        completion_tokens: int = 0,
        platform: str = "",
    ) -> None:
        """记录请求结果指标并持久化。

        Args:
            cid: 候选项 ID。
            success: 是否成功。
            latency: 首包延迟（秒）。
            tokens: chunk 计数。
            duration: 总耗时（秒）。
            generation_dur: 纯生成时长（秒，排除 TTFT）。
            completion_tokens: 上游实际 completion token 数。
            platform: 平台标识。
        """
        r = self._ensure(cid, platform)

        if success:
            r.last_call = time.time()
            r.n_calls += 1
            r.n_fails = 0
            self._cf[cid] = 0

            if latency > 0:
                if r.ema_latency > 0:
                    r.ema_latency = (
                        EMA_A * latency + (1 - EMA_A) * r.ema_latency
                    )
                else:
                    r.ema_latency = latency

            if (
                completion_tokens > 0
                and generation_dur > 0
            ):
                speed = completion_tokens / generation_dur
            elif tokens > 0 and duration > 0:
                speed = tokens / duration
            else:
                speed = 0

            if speed > 0:
                if r.ema_speed > 0:
                    r.ema_speed = (
                        EMA_A * speed + (1 - EMA_A) * r.ema_speed
                    )
                else:
                    r.ema_speed = speed
        else:
            r.error_time = time.time()
            r.n_fails += 1
            self._cf[cid] = self._cf.get(cid, 0) + 1

        self._tune_weights(r, success)
        self._save_record(cid, r)
        self._save_weights()

    async def get_stats(self) -> Dict[str, Any]:
        """获取全部候选项统计数据。"""
        return {k: v.to_dict() for k, v in self._pool.items()}
