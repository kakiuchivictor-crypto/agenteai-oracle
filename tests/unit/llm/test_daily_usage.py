"""Testes do contador diario (persistido) de chamadas ao provedor de LLM."""

from __future__ import annotations

from app.llm.daily_usage import has_daily_capacity, record_daily_call


def test_zero_limit_disables_the_guard(db_session) -> None:
    for _ in range(5):
        assert has_daily_capacity(db_session, daily_limit=0) is True
        record_daily_call(db_session)
    db_session.commit()


def test_denies_calls_beyond_the_daily_limit(db_session) -> None:
    assert has_daily_capacity(db_session, daily_limit=2) is True
    record_daily_call(db_session)
    assert has_daily_capacity(db_session, daily_limit=2) is True
    record_daily_call(db_session)
    assert has_daily_capacity(db_session, daily_limit=2) is False


def test_record_daily_call_accumulates_across_calls(db_session) -> None:
    for _ in range(3):
        record_daily_call(db_session)
    db_session.commit()
    assert has_daily_capacity(db_session, daily_limit=3) is False
    assert has_daily_capacity(db_session, daily_limit=4) is True
