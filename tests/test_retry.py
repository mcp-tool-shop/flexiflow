from __future__ import annotations

import pytest

from flexiflow.extras.retry import retry_async, RetryConfig


async def test_retry_succeeds_after_failures():
    """Retry decorator retries until success within max_attempts."""
    calls = {"n": 0}

    @retry_async(RetryConfig(max_attempts=3, base_delay=0))
    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("not yet")
        return "ok"

    result = await flaky()
    assert result == "ok"
    assert calls["n"] == 3


async def test_retry_raises_after_max_attempts():
    """Retry decorator raises after exhausting max_attempts."""
    calls = {"n": 0}

    @retry_async(RetryConfig(max_attempts=2, base_delay=0))
    async def always_fails():
        calls["n"] += 1
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="nope"):
        await always_fails()

    assert calls["n"] == 2


async def test_retry_succeeds_first_try():
    """No retry needed when function succeeds immediately."""
    calls = {"n": 0}

    @retry_async(RetryConfig(max_attempts=3, base_delay=0))
    async def works():
        calls["n"] += 1
        return "success"

    result = await works()
    assert result == "success"
    assert calls["n"] == 1


async def test_retry_only_on_specified_exceptions():
    """Retry only catches specified exception types."""
    calls = {"n": 0}

    @retry_async(RetryConfig(max_attempts=3, base_delay=0, retry_on=(ValueError,)))
    async def raises_type_error():
        calls["n"] += 1
        raise TypeError("wrong type")

    # TypeError is not in retry_on, so should raise immediately
    with pytest.raises(TypeError):
        await raises_type_error()

    assert calls["n"] == 1  # only one attempt


def test_invalid_config_max_attempts():
    """max_attempts < 1 raises ValueError."""
    with pytest.raises(ValueError, match="max_attempts"):
        retry_async(RetryConfig(max_attempts=0))


def test_invalid_config_negative_delay():
    """Negative delays raise ValueError."""
    with pytest.raises(ValueError, match="delays"):
        retry_async(RetryConfig(base_delay=-1))


def test_invalid_config_backoff():
    """backoff < 1.0 raises ValueError."""
    with pytest.raises(ValueError, match="backoff"):
        retry_async(RetryConfig(backoff=0.5))


def test_invalid_config_jitter():
    """jitter outside 0.0-1.0 raises ValueError."""
    with pytest.raises(ValueError, match="jitter"):
        retry_async(RetryConfig(jitter=1.5))
