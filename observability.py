"""Structured logging and per-stage timings.

Every request carries a trace id, and each pipeline stage records its own
wall-clock time, so a slow answer can be attributed to retrieval, reranking or
generation without guesswork:

    >>> timer = StageTimer(trace_id="abc123")
    >>> with timer.stage("retrieve"):
    ...     pass
    >>> timer.timings["retrieve"] >= 0
    True

Set ``LOG_FORMAT=text`` for human-readable logs; the default emits one JSON
object per line, which is what log aggregators expect.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from collections.abc import Iterator

LOGGER_NAME = "rag"


def new_trace_id() -> str:
    """Short, log-friendly trace id."""
    return uuid.uuid4().hex[:12]


def configure_logging(level: str | int | None = None) -> None:
    """Configure the ``rag`` logger once, idempotently."""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return

    handler = logging.StreamHandler()
    if os.getenv("LOG_FORMAT", "json").lower() == "text":
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    else:
        handler.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(handler)
    logger.setLevel(level or os.getenv("LOG_LEVEL", "INFO").upper())
    logger.propagate = False


def log_event(event: str, trace_id: str | None = None, level: int = logging.INFO, **fields) -> None:
    """Emit one structured event."""
    configure_logging()
    payload = {"event": event}
    if trace_id:
        payload["trace_id"] = trace_id
    payload.update({key: value for key, value in fields.items() if value is not None})
    logging.getLogger(LOGGER_NAME).log(level, json.dumps(payload, default=str))


class StageTimer:
    """Collects millisecond timings for named pipeline stages."""

    def __init__(self, trace_id: str | None = None, log: bool = False):
        self.trace_id = trace_id or new_trace_id()
        self.timings: dict[str, float] = {}
        self.log = log

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            self.timings[name] = round(elapsed_ms, 2)
            if self.log:
                log_event("stage", self.trace_id, stage=name, ms=self.timings[name])

    @property
    def total_ms(self) -> float:
        return round(sum(self.timings.values()), 2)

    def as_dict(self) -> dict[str, float]:
        return dict(self.timings)


def summarize(request: str, answer: str, timings: dict[str, float], **fields) -> dict:
    """Build the structured record for a completed request."""
    return {
        "request": request[:120],
        "answer_chars": len(answer or ""),
        "timings_ms": timings,
        **fields,
    }
