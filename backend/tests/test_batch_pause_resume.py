"""FEATURES.md #2: the live pause/resume kill switch.

Exercises app.api.batch_state directly (pure in-memory logic, no Supabase
needed) plus pipeline.run_batch's pause-aware loop, reusing
test_pipeline_integration.py's FakeSupabase/FakeTable fixtures rather than
re-implementing a fake Postgres client.
"""

from __future__ import annotations

import threading
import time

from app.agents.diagnosis_agent import Diagnosis
from app.api import batch_state, pipeline
from tests.test_pipeline_integration import FakeSupabase


def test_pause_blocks_and_resume_unblocks_between_events(monkeypatch):
    def fake_diagnose(event, customer_history=None, on_fallback=None):
        return Diagnosis(
            root_cause=event.get("failure_reason_code") or "unknown",
            confidence=0.8,
            reasoning="mocked",
            recommended_action="flag_for_human_review",
            action_params={},
            customer_message=None,
            llm_provider="groq",
            llm_fallback_used=False,
        )

    monkeypatch.setattr(pipeline, "diagnose", fake_diagnose)
    monkeypatch.setattr(pipeline.time, "sleep", lambda *_a, **_k: None)

    fake = FakeSupabase()
    monkeypatch.setattr(pipeline, "get_supabase", lambda: fake)
    import app.audit.hash_chain as hash_chain
    import app.audit.logger as audit_logger

    monkeypatch.setattr(audit_logger, "get_supabase", lambda: fake)
    monkeypatch.setattr(hash_chain, "get_supabase", lambda: fake)

    state = batch_state.create(n=6, seed=1)
    batch_state.pause(state.batch_id)
    assert state.status == "paused"

    thread = threading.Thread(
        target=pipeline.run_batch, kwargs={"n": 6, "seed": 1, "batch_id": state.batch_id}
    )
    thread.start()

    # Give the worker a moment to hit the pause gate; it must not process
    # any events while paused.
    time.sleep(0.2)
    assert state.processed == 0
    assert state.status == "paused"

    batch_state.resume(state.batch_id)
    thread.join(timeout=5)
    assert not thread.is_alive()

    assert state.status == "completed"
    assert state.processed == 6
    assert len(state.decisions) == 6


def test_status_dict_reports_skipped_paused_honestly():
    state = batch_state.create(n=10, seed=None)
    state.total = 10
    state.processed = 4
    batch_state.pause(state.batch_id)

    status = batch_state.to_status_dict(state)
    assert status["status"] == "paused"
    assert status["skipped_paused"] == 6
    assert status["processed"] == 4

    batch_state.resume(state.batch_id)
    status = batch_state.to_status_dict(state)
    assert status["status"] == "running"
    assert status["skipped_paused"] == 0


def test_pause_and_resume_unknown_batch_id_returns_none():
    assert batch_state.pause("does-not-exist") is None
    assert batch_state.resume("does-not-exist") is None
    assert batch_state.get("does-not-exist") is None
