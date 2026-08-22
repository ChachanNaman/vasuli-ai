"""Integration test for the full batch pipeline (generate -> guardrail check
-> agent diagnosis -> decision write) with Supabase and the LLM mocked out.
This proves the wiring end-to-end without needing live credentials; the real
proof-of-life run against actual Supabase/Groq/Gemini happens once API keys
are available.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.agents.llm_client import LLMResult
from app.api import pipeline


class FakeTable:
    """Minimal stand-in for supabase-py's fluent table query builder."""

    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name
        self._filters = []
        self._pending_write = None

    def select(self, *_args, **_kwargs):
        return self

    def insert(self, row):
        self._pending_write = [row]
        return self

    def upsert(self, row, on_conflict=None):
        self._pending_write = [row]
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def order(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    def execute(self):
        if self._pending_write is not None:
            self.store.setdefault(self.name, []).extend(self._pending_write)
            result = self._pending_write
            self._pending_write = None
            return MagicMock(data=result)

        rows = self.store.get(self.name, [])
        for field, value in self._filters:
            rows = [r for r in rows if r.get(field) == value]
        self._filters = []
        return MagicMock(data=rows)


class FakeSupabase:
    def __init__(self):
        self.store: dict = {}

    def table(self, name):
        return FakeTable(self.store, name)


@pytest.fixture
def fake_supabase(monkeypatch):
    fake = FakeSupabase()
    monkeypatch.setattr(pipeline, "get_supabase", lambda: fake)
    import app.audit.logger as audit_logger

    monkeypatch.setattr(audit_logger, "get_supabase", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(pipeline.time, "sleep", lambda *_args, **_kwargs: None)


@pytest.fixture
def fake_diagnose(monkeypatch):
    def fake(event, customer_history=None, on_fallback=None):
        from app.agents.diagnosis_agent import Diagnosis

        return Diagnosis(
            root_cause=event.get("failure_reason_code") or "unknown",
            confidence=0.8,
            reasoning="Mocked diagnosis for integration test.",
            recommended_action="smart_retry"
            if event["event_type"] in ("payment_failed", "subscription_charge_failed")
            else "flag_for_human_review",
            action_params={},
            customer_message=None,
            llm_provider="groq",
            llm_fallback_used=False,
        )

    monkeypatch.setattr(pipeline, "diagnose", fake)
    return fake


def test_run_batch_writes_events_and_decisions(fake_supabase, fake_diagnose):
    decisions = pipeline.run_batch(n=10, seed=1)

    assert len(decisions) == 10
    assert len(fake_supabase.store.get("events", [])) == 10
    assert len(fake_supabase.store.get("decisions", [])) == 10

    for row in fake_supabase.store["decisions"]:
        assert row["action_status"] in ("executed", "blocked_by_guardrail", "skipped_opt_out")
        assert isinstance(row["guardrail_checks"], list)
        assert len(row["guardrail_checks"]) == 7


def test_process_event_routes_to_human_review_on_llm_failure(fake_supabase, monkeypatch):
    from app.agents.llm_client import LLMClientError

    def failing_diagnose(event, customer_history=None, on_fallback=None):
        raise LLMClientError("both providers down")

    monkeypatch.setattr(pipeline, "diagnose", failing_diagnose)

    event = {
        "event_id": "evt_x",
        "event_type": "payment_failed",
        "amount": 500,
        "attempt_number": 1,
        "failure_reason_code": "network_error",
        "customer": {"customer_id": "cust_x", "opted_out_of_recovery_comms": False},
    }
    row = pipeline.process_event(event)
    assert row["action_type"] == "flag_for_human_review"
    assert row["confidence"] == 0.0
