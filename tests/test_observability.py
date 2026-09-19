"""Tests for structured logging and stage timings."""
from __future__ import annotations

import json
import logging

import pytest

from observability import StageTimer, configure_logging, log_event, new_trace_id, summarize


def test_trace_ids_are_short_and_unique():
    first, second = new_trace_id(), new_trace_id()

    assert first != second
    assert len(first) == 12


def test_stage_timer_records_each_stage():
    timer = StageTimer(trace_id="t-1")

    with timer.stage("retrieve"):
        pass
    with timer.stage("generate"):
        pass

    assert set(timer.timings) == {"retrieve", "generate"}
    assert all(value >= 0 for value in timer.timings.values())
    assert timer.total_ms == pytest.approx(sum(timer.timings.values()), abs=0.01)
    assert timer.as_dict() == timer.timings


def test_stage_timer_records_timing_even_when_stage_raises():
    timer = StageTimer()

    with pytest.raises(RuntimeError), timer.stage("retrieve"):
        raise RuntimeError("boom")

    assert "retrieve" in timer.timings


def test_log_event_emits_parseable_json(caplog):
    configure_logging(level=logging.INFO)

    with caplog.at_level(logging.INFO, logger="rag"):
        log_event("ask", "trace-9", stages=3, refused=False)

    payload = json.loads(caplog.records[-1].message)
    assert payload["event"] == "ask"
    assert payload["trace_id"] == "trace-9"
    assert payload["stages"] == 3
    assert payload["refused"] is False


def test_log_event_drops_none_fields(caplog):
    with caplog.at_level(logging.INFO, logger="rag"):
        log_event("ask", None, reason=None)

    payload = json.loads(caplog.records[-1].message)
    assert "reason" not in payload
    assert "trace_id" not in payload


def test_summarize_truncates_long_requests():
    record = summarize("q" * 500, "a" * 10, {"retrieve": 12.5}, refused=True)

    assert len(record["request"]) == 120
    assert record["answer_chars"] == 10
    assert record["timings_ms"] == {"retrieve": 12.5}
    assert record["refused"] is True
