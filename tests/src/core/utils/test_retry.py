"""Tests for src/core/utils/retry.py."""
import asyncio

import pytest

from src.core.utils.retry import retry_with_backoff, retry_on_empty, retry_on_exception


class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        async def success():
            return "ok"

        result = await retry_with_backoff(success)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError(f"fail #{call_count}")
            return "success"

        result = await retry_with_backoff(
            fail_then_succeed,
            max_attempts=5,
            base_delay=0.01,
            max_delay=0.1,
        )
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_last_exception(self):
        async def always_fail():
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            await retry_with_backoff(
                always_fail,
                max_attempts=3,
                base_delay=0.01,
            )

    @pytest.mark.asyncio
    async def test_filters_exceptions(self):
        call_count = 0

        async def raise_different_errors():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("value error")
            raise TypeError("type error")

        # Only retry on ValueError
        with pytest.raises(TypeError):
            await retry_with_backoff(
                raise_different_errors,
                max_attempts=3,
                base_delay=0.01,
                exceptions=(ValueError,),
            )

    @pytest.mark.asyncio
    async def test_with_arguments(self):
        async def add(a, b):
            return a + b

        result = await retry_with_backoff(add, 2, 3)
        assert result == 5

    @pytest.mark.asyncio
    async def test_with_kwargs(self):
        async def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = await retry_with_backoff(greet, "World", greeting="Hi")
        assert result == "Hi, World"

    @pytest.mark.asyncio
    async def test_respects_max_delay(self):
        """Test that max_delay caps the backoff."""
        import time

        async def fail():
            raise Exception("fail")

        start = time.time()
        with pytest.raises(Exception):
            await retry_with_backoff(
                fail,
                max_attempts=3,
                base_delay=0.01,
                max_delay=0.02,  # Very small max delay
            )
        elapsed = time.time() - start
        # Total time should be roughly 0.01 + 0.02 = 0.03s (not exponential)
        assert elapsed < 0.1


class TestRetryOnEmpty:
    @pytest.mark.asyncio
    async def test_returns_nonempty_string(self):
        async def returns_value():
            return "hello"

        result = await retry_on_empty(returns_value, max_retries=3)
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_retries_on_none(self):
        call_count = 0

        async def returns_none_then_value():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return None
            return "finally"

        result = await retry_on_empty(returns_none_then_value, max_retries=3)
        assert result == "finally"

    @pytest.mark.asyncio
    async def test_retries_on_empty_string(self):
        call_count = 0

        async def returns_empty_then_value():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return ""
            return "not empty"

        result = await retry_on_empty(returns_empty_then_value, max_retries=3)
        assert result == "not empty"

    @pytest.mark.asyncio
    async def test_retries_on_dict_with_empty_content(self):
        call_count = 0

        async def returns_dict():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                return {"text": ""}
            return {"text": "content"}

        result = await retry_on_empty(returns_dict, max_retries=3)
        assert result == {"text": "content"}

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        async def always_none():
            return None

        with pytest.raises(ValueError, match="None response"):
            await retry_on_empty(always_none, max_retries=2)

    @pytest.mark.asyncio
    async def test_whitespace_only_string(self):
        async def returns_whitespace():
            return "   "

        with pytest.raises(ValueError, match="empty string response"):
            await retry_on_empty(returns_whitespace, max_retries=2)


class TestRetryOnException:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        async def success():
            return "ok"

        result = await retry_on_exception(success, max_retries=3)
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_retries_on_exception(self):
        call_count = 0

        async def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("fail")
            return "success"

        result = await retry_on_exception(
            fail_then_succeed, max_retries=3, exceptions=(ValueError,)
        )
        assert result == "success"

    @pytest.mark.asyncio
    async def test_calls_on_retry_callback(self):
        retry_calls = []

        async def fail():
            raise RuntimeError("error")

        def on_retry(attempt, error):
            retry_calls.append((attempt, str(error)))

        with pytest.raises(RuntimeError):
            await retry_on_exception(
                fail,
                max_retries=3,
                on_retry=on_retry,
            )

        assert len(retry_calls) == 3  # Called for all 3 attempts
        assert retry_calls[0] == (1, "error")

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        async def always_fail():
            raise TypeError("always fails")

        with pytest.raises(TypeError, match="always fails"):
            await retry_on_exception(
                always_fail, max_retries=3, exceptions=(TypeError,)
            )

    @pytest.mark.asyncio
    async def test_does_not_retry_unlisted_exception(self):
        call_count = 0

        async def fail_with_unlisted():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("unlisted")

        # Only retries on ValueError, not RuntimeError
        with pytest.raises(RuntimeError):
            await retry_on_exception(
                fail_with_unlisted, max_retries=3, exceptions=(ValueError,)
            )

        assert call_count == 1  # Only one attempt, no retries
