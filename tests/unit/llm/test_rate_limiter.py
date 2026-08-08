"""Testes do limitador global de chamadas ao provedor de LLM."""

from __future__ import annotations

from app.llm.rate_limiter import LlmCallLimiter


def test_allows_calls_within_the_limit() -> None:
    limiter = LlmCallLimiter(max_calls_per_minute=3)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True


def test_denies_calls_beyond_the_limit() -> None:
    limiter = LlmCallLimiter(max_calls_per_minute=2)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False


def test_frees_up_after_the_window_passes() -> None:
    limiter = LlmCallLimiter(max_calls_per_minute=1, window_seconds=0.05)
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False

    import time

    time.sleep(0.06)
    assert limiter.try_acquire() is True


def test_zero_limit_disables_the_guard() -> None:
    limiter = LlmCallLimiter(max_calls_per_minute=0)
    for _ in range(50):
        assert limiter.try_acquire() is True
