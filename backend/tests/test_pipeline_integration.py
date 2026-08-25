"""Integration test for the full batch pipeline (generate -> guardrail check
-> agent diagnosis -> decision write) with Supabase and the LLM mocked out.
This proves the wiring end-to-end without needing live credentials; the real
proof-of-life run against actual Supabase/Groq/Gemini happens once API keys
are available.
"""

from __future__ import annotations

import itertools
import uuid
from unittest.mock import MagicMock

import pytest

from app.agents.llm_client import LLMResult
from app.api import pipeline

_chain_seq_counter = itertools.count(1)


class FakeTable:
    """Minimal stand-in for supabase-py's fluent table query builder.

    Simulates just enough of Postgres's insert-time defaults (decision_id,
    chain_seq) that the hash-chain write path (audit/logger.py,
    audit/hash_chain.py) exercises the same insert -> hash -> update
    sequence it does against real Supabase.
    """

    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name
        self._filters = []
        self._pending_write = None
        self._pending_update = None
        self._order_field = None
        self._order_desc = False
        self._limit = None

    def select(self, *_args, **_kwargs):
        return self

    def insert(self, row):
        row = dict(row)
        if self.name == "decisions":
            row.setdefault("decision_id", str(uuid.uuid4()))
            row.setdefault("chain_seq", next(_chain_seq_counter))
        self._pending_write = [row]
        return self

    def upsert(self, row, on_conflict=None):
        self._pending_write = [row]
        return self

    def update(self, row):
        self._pending_update = row
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def order(self, field, desc=False, **_kwargs):
        self._order_field = field
        self._order_desc = desc
        return self

    def limit(self, n, **_kwargs):
        self._limit = n
        return self

    def _apply_order_and_limit(self, rows):
        if self._order_field is not None:
            rows = sorted(
                rows, key=lambda r: r.get(self._order_field) or 0, reverse=self._order_desc
            )
        if self._limit is not None:
            rows = rows[: self._limit]
        return rows

    def execute(self):
        if self._pending_write is not None:
            self.store.setdefault(self.name, []).extend(self._pending_write)
            result = self._pending_write
            self._pending_write = None
            return MagicMock(data=result)

        if self._pending_update is not None:
            rows = self.store.get(self.name, [])
            matched = [r for r in rows if all(r.get(f) == v for f, v in self._filters)]
            for r in matched:
                r.update(self._pending_update)
            self._filters = []
            self._pending_update = None
            return MagicMock(data=matched)

        rows = self.store.get(self.name, [])
        for field, value in self._filters:
            rows = [r for r in rows if r.get(field) == value]
        self._filters = []
        rows = self._apply_order_and_limit(rows)
        self._order_field = None
        self._order_desc = False
        self._limit = None
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
    import app.audit.hash_chain as hash_chain
    import app.audit.logger as audit_logger
    import app.audit.verify as audit_verify

    monkeypatch.setattr(audit_logger, "get_supabase", lambda: fake)
    monkeypatch.setattr(hash_chain, "get_supabase", lambda: fake)
    monkeypatch.setattr(audit_verify, "get_supabase", lambda: fake)
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
        assert len(row["guardrail_checks"]) == 13


def test_run_batch_hash_chain_is_intact(fake_supabase, fake_diagnose):
    """ENHANCEMENTS.md §2.4: every decision written by a batch run should
    chain correctly and verify clean."""
    from app.audit.verify import verify_chain

    pipeline.run_batch(n=8, seed=2)

    ok, count, error = verify_chain()
    assert ok, error
    assert count == 8


def test_hash_chain_detects_tampering(fake_supabase, fake_diagnose):
    """Altering a past decision's content after the fact must break
    verification from that point forward — the whole point of the chain."""
    from app.audit.verify import verify_chain

    pipeline.run_batch(n=5, seed=3)

    decisions = fake_supabase.store["decisions"]
    decisions[2]["amount_recovered"] = 999_999_999.0  # tamper with a middle record

    ok, position, error = verify_chain()
    assert not ok
    assert position == 2
    assert error is not None


def test_process_event_falls_back_to_heuristic_agent_on_llm_failure(fake_supabase, monkeypatch):
    """ENHANCEMENTS.md §2.5: three-way degradation — if both LLM providers
    fail, the pipeline drops to the deterministic heuristic agent instead
    of a hard 'I don't know' with zero confidence."""
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
        "customer": {
            "customer_id": "cust_x",
            "name": "Test Customer",
            "opted_out_of_recovery_comms": False,
        },
    }
    row = pipeline.process_event(event)
    assert row["llm_provider"] == "heuristic"
    assert row["llm_fallback_used"] is True
    assert row["action_type"] == "smart_retry"  # network_error, attempt 1 -> retry
    assert row["confidence"] > 0.0
