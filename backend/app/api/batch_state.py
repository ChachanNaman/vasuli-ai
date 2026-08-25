"""In-memory per-batch pause/resume state (FEATURES.md #2).

A single-merchant demo doesn't need durable batch state — a module-level
registry keyed by batch_id is enough, matching the "in-memory is fine, no
new infra needed" note in FEATURES.md. It resets on backend restart along
with everything else kept in memory here, which is fine: a fresh batch run
gets a fresh batch_id.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class BatchState:
    batch_id: str
    n: int
    seed: Optional[int]
    total: int = 0
    processed: int = 0
    status: str = "running"  # running | paused | completed | error
    decisions: list = field(default_factory=list)
    error: Optional[str] = None
    _resume_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def __post_init__(self) -> None:
        self._resume_event.set()


_batches: dict[str, BatchState] = {}
_registry_lock = threading.Lock()


def create(n: int, seed: Optional[int]) -> BatchState:
    batch_id = uuid.uuid4().hex[:12]
    state = BatchState(batch_id=batch_id, n=n, seed=seed)
    with _registry_lock:
        _batches[batch_id] = state
    return state


def get(batch_id: str) -> Optional[BatchState]:
    return _batches.get(batch_id)


def pause(batch_id: str) -> Optional[BatchState]:
    state = _batches.get(batch_id)
    if state is None or state.status in ("completed", "error"):
        return state
    state.status = "paused"
    state._resume_event.clear()
    return state


def resume(batch_id: str) -> Optional[BatchState]:
    state = _batches.get(batch_id)
    if state is None or state.status in ("completed", "error"):
        return state
    state.status = "running"
    state._resume_event.set()
    return state


def wait_if_paused(state: BatchState) -> None:
    """Block the pipeline thread between events while paused. Called by
    run_batch before starting each new event — never mid-decision, since
    an in-flight diagnose/guardrail/execute sequence for one event always
    runs to completion once started."""
    state._resume_event.wait()


def remaining_event_count(state: BatchState) -> int:
    return max(state.total - state.processed, 0)


def to_status_dict(state: BatchState) -> dict:
    return {
        "batch_id": state.batch_id,
        "n": state.n,
        "total": state.total,
        "processed": state.processed,
        "status": state.status,
        # Unprocessed events in a paused batch, surfaced honestly rather
        # than silently dropped — they resume processing normally as soon
        # as the batch is resumed.
        "skipped_paused": remaining_event_count(state) if state.status == "paused" else 0,
        "decisions_written": len(state.decisions),
        "error": state.error,
    }
