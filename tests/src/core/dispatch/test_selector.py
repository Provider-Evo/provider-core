"""Tests for src/core/dispatch/selector.py."""
import math
import os
import pytest
import tempfile
import time
from unittest.mock import patch

from src.core.dispatch.selector import Selector, TASRecord, TASWeights
from src.core.dispatch.candidate import Candidate


class TestTASRecord:
    def test_default_values(self):
        r = TASRecord()
        assert r.platform == ""
        assert r.error_time == 0.0
        assert r.last_call == 0.0
        assert r.ema_speed == 0.0
        assert r.ema_latency == 0.0
        assert r.n_calls == 0
        assert r.n_fails == 0

    def test_to_dict(self):
        r = TASRecord(platform="test", ema_speed=25.0, ema_latency=1.2, n_calls=10)
        d = r.to_dict()
        assert d["platform"] == "test"
        assert d["ema_speed"] == 25.0
        assert d["ema_latency"] == 1.2
        assert d["n_calls"] == 10
        assert "cooling" in d

    def test_cooling_in_dict(self):
        r = TASRecord(error_time=time.time(), n_fails=2)
        d = r.to_dict()
        assert d["cooling"] is True

    def test_not_cooling_no_fails(self):
        r = TASRecord(error_time=time.time(), n_fails=0)
        d = r.to_dict()
        assert d["cooling"] is False


class TestTASWeights:
    def test_default_values(self):
        w = TASWeights()
        assert abs(w.w_err - 0.2) < 0.001
        assert abs(w.w_call - 0.2) < 0.001
        assert abs(w.w_speed - 0.2) < 0.001
        assert abs(w.w_lat - 0.2) < 0.001
        assert abs(w.w_fails - 0.2) < 0.001

    def test_sum_is_one(self):
        w = TASWeights()
        total = w.w_err + w.w_call + w.w_speed + w.w_lat + w.w_fails
        assert abs(total - 1.0) < 0.001


@pytest.fixture
def selector():
    with tempfile.TemporaryDirectory() as td:
        yield Selector(persist_dir=td)


class TestSelector:
    def test_init(self, selector):
        assert selector._eps > 0
        assert selector._n == 0

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
        assert r.last_call > 0
        assert r.ema_latency > 0
        assert r.ema_speed > 0

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
        assert r.ema_speed > 0
        # speed = 40 / 4.0 = 10.0 tok/s
        assert abs(r.ema_speed - 10.0) < 0.1

    @pytest.mark.asyncio
    async def test_get_stats(self, selector):
        await selector.record(
            "test_123", success=True, latency=0.5, tokens=10,
            duration=2.0, platform="test",
        )
        stats_dict = await selector.get_stats()
        assert "test_123" in stats_dict
        d = stats_dict["test_123"]
        assert "platform" in d
        assert "ema_speed" in d
        assert "ema_latency" in d
        assert "cooling" in d

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
        selector._cf["test_1"] = 2

        result = await selector.select(cands, count=1)
        assert result[0].id == "test_2"

    @pytest.mark.asyncio
    async def test_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            s1 = Selector(persist_dir=td)
            await s1.record(
                "cand_1", success=True, latency=1.0, tokens=20,
                duration=3.0, platform="plat",
            )

            s2 = Selector(persist_dir=td)
            assert "cand_1" in s2._pool
            assert s2._pool["cand_1"].n_calls == 1

    @pytest.mark.asyncio
    async def test_weights_persistence(self):
        with tempfile.TemporaryDirectory() as td:
            s1 = Selector(persist_dir=td)
            s1._w.w_speed = 0.3
            s1._w.w_lat = 0.2
            s1._w.w_err = 0.2
            s1._w.w_call = 0.1
            s1._w.w_fails = 0.2
            s1._save_weights()

            s2 = Selector(persist_dir=td)
            assert abs(s2._w.w_speed - 0.3) < 0.001
            assert abs(s2._w.w_lat - 0.2) < 0.001
            assert abs(s2._w.w_fails - 0.2) < 0.001

    def test_score_fast_vs_slow(self, selector):
        fast = TASRecord(
            platform="p", ema_speed=50.0, ema_latency=0.5,
            last_call=time.time(), n_calls=10,
        )
        slow = TASRecord(
            platform="p", ema_speed=5.0, ema_latency=3.0,
            last_call=time.time(), n_calls=10,
        )
        s_fast = selector._score_one(fast, 27.5, 1.75)
        s_slow = selector._score_one(slow, 27.5, 1.75)
        assert s_fast > s_slow

    def test_score_error_penalty(self, selector):
        good = TASRecord(
            platform="p", ema_speed=20.0, ema_latency=1.0,
            last_call=time.time(), n_calls=10,
        )
        errored = TASRecord(
            platform="p", ema_speed=20.0, ema_latency=1.0,
            last_call=time.time(), n_calls=10,
            error_time=time.time(),
        )
        s_good = selector._score_one(good, 20.0, 1.0)
        s_err = selector._score_one(errored, 20.0, 1.0)
        assert s_good > s_err

    def test_score_fails_penalty(self, selector):
        reliable = TASRecord(
            platform="p", ema_speed=20.0, ema_latency=1.0,
            last_call=time.time(), n_calls=10, n_fails=0,
        )
        flaky = TASRecord(
            platform="p", ema_speed=20.0, ema_latency=1.0,
            last_call=time.time(), n_calls=10, n_fails=5,
        )
        s_reliable = selector._score_one(reliable, 20.0, 1.0)
        s_flaky = selector._score_one(flaky, 20.0, 1.0)
        assert s_reliable > s_flaky

    def test_score_fails_capped_at_10(self, selector):
        fails_10 = TASRecord(
            platform="p", ema_speed=20.0, ema_latency=1.0,
            last_call=time.time(), n_calls=10, n_fails=10,
        )
        fails_20 = TASRecord(
            platform="p", ema_speed=20.0, ema_latency=1.0,
            last_call=time.time(), n_calls=10, n_fails=20,
        )
        s_10 = selector._score_one(fails_10, 20.0, 1.0)
        s_20 = selector._score_one(fails_20, 20.0, 1.0)
        assert abs(s_10 - s_20) < 0.001

    def test_tune_weights_sum_preserved(self, selector):
        r = TASRecord(
            platform="p", ema_speed=20.0, ema_latency=1.0,
            last_call=time.time(), error_time=time.time(),
        )
        selector._tune_weights(r, True)
        total = (
            selector._w.w_err + selector._w.w_call
            + selector._w.w_speed + selector._w.w_lat
            + selector._w.w_fails
        )
        assert abs(total - 1.0) < 0.001

    def test_stop_criterion_insufficient_samples(self, selector):
        cands = [
            Candidate(id="test_1", platform="test", resource_id="r1"),
            Candidate(id="test_2", platform="test", resource_id="r2"),
        ]
        result = selector._stop(cands, 10.0, 2.0)
        assert result is False

    def test_explore_returns_candidate(self, selector):
        cands = [
            Candidate(id="test_1", platform="test", resource_id="r1"),
            Candidate(id="test_2", platform="test", resource_id="r2"),
        ]
        result = selector._explore(cands, 10.0, 2.0)
        assert result in cands
