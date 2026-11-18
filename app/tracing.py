"""Minimal observability: one JSON line per request and per feedback event.

This is deliberately simple so the skeleton runs anywhere. It records exactly
the fields you will later send to Langfuse / OpenTelemetry / Prometheus
(latency, tokens, cost, prompt version, retrieved chunk ids), so swapping the
backend is a change to this one file.
"""

import json
import threading
from datetime import datetime, timezone

from app.config import LOG_DIR

_lock = threading.Lock()


def _append(filename: str, record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    with _lock, open(LOG_DIR / filename, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_trace(record: dict) -> None:
    _append("traces.jsonl", record)


def log_feedback(record: dict) -> None:
    _append("feedback.jsonl", record)