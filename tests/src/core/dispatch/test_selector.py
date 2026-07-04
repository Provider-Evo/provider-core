"""Tests for src/core/dispatch/selector.py."""
import math
import os
import sqlite3
import pytest
import tempfile
import time
from pathlib import Path

from src.core.dispatch.selector import Selector, TASRecord
from src.core.dispatch.candidate import Candidate


class TestTASRecord:
    def test_default_values(self):
        r = TASRecord()
        assert r.group == ""
        assert r.n_success == 0
        assert r.n_fails == 0
        assert r.latency_sum == 0.0
        assert r.latency_sum_sq == 0.0
        assert r.n_latency_samples == 0
        assert r.speed_sum == 0.0
        assert r.speed_sum_sq == 0.0
        assert r.n_speed_samples == 0
        assert r.last_success == 0.0
        assert r.last_used == 0.0
        assert r.error_time == 0.0
        assert r.n_calls == 0

    def test_to_dict(self):
        r = TASRecord(
            group="test",
            n_success=5,
            n_fails=1,
            latency_sum=500.0,
            n_latency_samples=5,
            speed_sum=100.0,
            n_speed_samples=5,
        )
        d = r.to_dict()
        assert d["group"] == "test"
        assert d["n_success"] == 5
        assert d["n_fails"] == 1
        assert d["latency_sum"] == 500.0
        assert d["n_latency_samples"] == 5
        assert d["speed_sum"] == 100.0
        assert d["n_speed_samples"] == 5
        # Derived fields
        assert "success_rate" in d
        assert "mean_latency" in d
        assert "mean_speed" in d

    def test_from_dict(self):
        data = {
            "group": "test",
            "n_success": 3,
            "n_fails": 1,
            "latency_sum": 300.0,
            "latency_sum_sq": 30000.0,
            "n_latency_samples": 3,
            "speed_sum": 60.0,
            "speed_sum_sq": 2000.0,
            "n_speed_samples": 3,
            "last_success": 1000.0,
            "last_used": 900.0,
            "error_time": 0.0,
            "n_calls": 4,
        }
        r = TASRecord.from_dict(data)
        assert r.group == "test"
        assert r.n_success == 3
        assert r.latency_sum == 300.0

    def test_beta_mean(self):
        r = TASRecord(n_success=8, n_fails=2)
        # Beta(2+8, 2+2) = Beta(10, 4), mean = 10/14 ≈ 0.714
        assert abs(r.beta_mean - 10 / 14) < 0.001

    def test_beta_std(self):
        r = TASRecord(n_success=8, n_fails=2)
        assert r.beta_std > 0

    def test_latency_mean(self):
        r = TASRecord(latency_sum=500.0, n_latency_samples=5)
        assert r.latency_mean == 100.0

    def test_latency_mean_no_samples(self):
        r = TASRecord()
        assert r.latency_mean == 1000.0

    def test_speed_mean(self):
        r = TASRecord(speed_sum=100.0, n_speed_samples=5)
        assert r.speed_mean == 20.0

    def test_speed_mean_no_samples(self):
        r = TASRecord()
        assert r.speed_mean == 10.0

    def test_total_obs(self):
        r = TASRecord(n_success=5, n_fails=3)
        assert r.total_obs == 8


@pytest.fixture
def selector():
    with tempfile.TemporaryDirectory() as td:
        yield Selector(persist_dir=td, prune_days=9999)


class TestSelector:
    def test_init(self, selector):
        assert selector._db_path.exists()

    @pytest.mark.asyncio
    async def test_select_empty_returns_empty(self, selector):
        result = await selector.select([])
        assert result == []

    @pytest.mark.asyncio
    async def test_select_single_candidate(self, selector):
        cand = Candidate(id="test_123", platform="test", resource_id="r1")
        result = await selector.select([cand], count=1)
        assert len(result) == 1
        assert result[0] is cand

    @pytest.mark.asyncio
    async def test_select_multiple_candidates(self, selector):
        cands = [
            Candidate(id="test_1", platform="test", resource_id="r1"),
            Candidate(id="test_2", platform="test", resource_id="r2"),
            Candidate(id="test_3", platform="test", resource_id="r3"),
        ]
        result = await selector.select(cands, count=2)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_select_respects_count(self, selector):
        cands = [
            Candidate(id="test_1", platform="test", resource_id="r1"),
            Candidate(id="test_2", platform="test", resource_id="r2"),
        ]
        result = await selector.select(cands, count=1)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_record_success(self, selector):
        await selector.record(
            "test_123", success=True, latency=0.5, tokens=100,
            duration=2.0, platform="test",
        )
        r = selector._pool["test_123"]
        assert r.n_calls == 1
        assert r.n_fails == 0
        assert r.last_success > 0
        assert r.latency_sum > 0
        assert r.n_latency_samples == 1

    @pytest.mark.asyncio
    async def test_record_fail(self, selector):
        await selector.record("test_123", success=False, platform="test")
        r = selector._pool["test_123"]
        assert r.n_calls == 0
        assert r.n_fails == 1
        assert r.error_time > 0

    @pytest.mark.asyncio
    async def test_record_with_completion_tokens(self, selector):
        await selector.record(
            "test_123", success=True, latency=1.0, tokens=50,
            duration=5.0, generation_dur=4.0, completion_tokens=40,
            platform="test",
        )
        r = selector._pool["test_123"]
        assert r.speed_sum > 0
        # speed = 40 / 4.0 = 10.0 tok/s
        assert abs(r.speed_mean - 10.0) < 0.1

    @pytest.mark.asyncio
    async def test_get_stats(self, selector):
        await selector.record(
            "test_123", success=True, latency=0.5, tokens=10,
            duration=2.0, platform="test",
        )
        stats_dict = await selector.get_stats()
        assert "test_123" in stats_dict
        d = stats_dict["test_123"]
        assert "group" in d
        assert "n_success" in d
        assert "n_fails" in d
        assert "latency_sum" in d
        assert "speed_sum" in d

    @pytest.mark.asyncio
    async def test_cooling_filter(self, selector):
        cands = [
            Candidate(id="test_1", platform="test", resource_id="r1"),
            Candidate(id="test_2", platform="test", resource_id="r2"),
        ]
        # Make test_1 cooling
        r1 = selector._ensure("test_1", "test")
        r1.error_time = time.time()
        r1.n_fails = 2

        result = await selector.select(cands, count=1)
        assert result[0].id == "test_2"

    @pytest.mark.asyncio
    async def test_sqlite_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            s1 = Selector(persist_dir=td, prune_days=9999)
            await s1.record(
                "cand_1", success=True, latency=1.0, tokens=20,
                duration=3.0, platform="plat",
            )
            s1._flush()

            s2 = Selector(persist_dir=td, prune_days=9999)
            assert "cand_1" in s2._pool
            assert s2._pool["cand_1"].n_calls == 1
            assert s2._pool["cand_1"].latency_sum > 0

    @pytest.mark.asyncio
    async def test_batch_flush(self, selector):
        await selector.record("a", success=True, latency=0.1, tokens=5, duration=1.0, platform="p")
        await selector.record("b", success=False, platform="p")

        # Should be in dirty buffer, not yet flushed
        assert len(selector._dirty) == 2

        # Manual flush
        selector._flush()

        # Dirty buffer should be empty
        assert len(selector._dirty) == 0

        # Records should be in SQLite
        conn = sqlite3.connect(str(selector._db_path))
        count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        conn.close()
        assert count == 2

    def test_score_fast_vs_slow(self, selector):
        fast = TASRecord(
            group="p", n_success=10, n_fails=0,
            latency_sum=500.0, latency_sum_sq=5000.0, n_latency_samples=10,
            speed_sum=500.0, speed_sum_sq=50000.0, n_speed_samples=10,
            last_success=time.time(), last_used=time.time(), n_calls=10,
        )
        slow = TASRecord(
            group="p", n_success=10, n_fails=0,
            latency_sum=3000.0, latency_sum_sq=900000.0, n_latency_samples=10,
            speed_sum=50.0, speed_sum_sq=500.0, n_speed_samples=10,
            last_success=time.time(), last_used=time.time(), n_calls=10,
        )
        s_fast = selector._score(fast, time.time())
        s_slow = selector._score(slow, time.time())
        assert s_fast > s_slow

    def test_score_error_penalty(self, selector):
        good = TASRecord(
            group="p", n_success=10, n_fails=0,
            latency_sum=1000.0, latency_sum_sq=100000.0, n_latency_samples=10,
            last_success=time.time(), last_used=time.time(), n_calls=10,
        )
        errored = TASRecord(
            group="p", n_success=10, n_fails=0,
            latency_sum=1000.0, latency_sum_sq=100000.0, n_latency_samples=10,
            last_success=time.time(), last_used=time.time(),
            error_time=time.time(), n_calls=10,
        )
        s_good = selector._score(good, time.time())
        s_err = selector._score(errored, time.time())
        assert s_good > s_err

    def test_score_fails_penalty(self, selector):
        reliable = TASRecord(
            group="p", n_success=10, n_fails=0,
            latency_sum=1000.0, n_latency_samples=10,
            last_used=time.time(), n_calls=10,
        )
        flaky = TASRecord(
            group="p", success=5, n_fails=5,
            latency_sum=1000.0, n_latency_samples=10,
            last_used=time.time(), n_calls=10,
        )
        s_reliable = selector._score(reliable, time.time())
        s_flaky = selector._score(flaky, time.time())
        assert s_reliable > s_flaky

    @pytest.mark.asyncio
    async def test_prune_stale(self):
        with tempfile.TemporaryDirectory() as td:
            s = Selector(persist_dir=td, prune_days=0)
            await s.record("old", success=False, platform="p")
            s._pool["old"].last_used = time.time() - 86400 * 2
            s._flush()

            pruned = s.prune_stale()
            assert pruned >= 1
            assert "old" not in s._pool

    def test_close_flushes(self, selector):
        # Record something
        selector._ensure("test", "p")
        selector._dirty["test"] = selector._pool["test"]

        selector.close()
        assert selector._closed
        assert len(selector._dirty) == 0
