"""LLM-vs-heuristic diagnosis agreement — LLM calls mocked out, no live
API usage, no rate limits, fully deterministic."""

from __future__ import annotations

from app.agents.diagnosis_agent import Diagnosis
from app.agents.llm_client import LLMClientError
from app.eval import diagnosis_agreement


def test_agreement_counts_matches_and_mismatches(monkeypatch):
    monkeypatch.setattr(diagnosis_agreement.time, "sleep", lambda *_a, **_k: None)

    def fake_diagnose(event, customer_history=None, on_fallback=None):
        # Deliberately disagree with the heuristic on root_cause for every
        # case, so the test can assert on a known, non-trivial agreement
        # rate rather than relying on real heuristic internals lining up.
        return Diagnosis(
            root_cause="llm_says_something_else",
            confidence=0.9,
            reasoning="mocked",
            recommended_action="flag_for_human_review",
            action_params={},
            customer_message=None,
            llm_provider="groq",
            llm_fallback_used=False,
        )

    monkeypatch.setattr(diagnosis_agreement, "diagnose", fake_diagnose)

    report = diagnosis_agreement.run_diagnosis_agreement(n_cases=5, seed=1)

    assert report["n_cases_requested"] == 5
    assert report["n_evaluated"] == 5
    assert report["llm_calls_failed"] == 0
    assert report["root_cause_agreement_pct"] == 0.0
    assert len(report["rows"]) == 5
    for row in report["rows"]:
        assert row["llm_root_cause"] == "llm_says_something_else"
        assert row["root_cause_agree"] is False


def test_agreement_handles_llm_failures_gracefully(monkeypatch):
    monkeypatch.setattr(diagnosis_agreement.time, "sleep", lambda *_a, **_k: None)

    def failing_diagnose(event, customer_history=None, on_fallback=None):
        raise LLMClientError("both providers down")

    monkeypatch.setattr(diagnosis_agreement, "diagnose", failing_diagnose)

    report = diagnosis_agreement.run_diagnosis_agreement(n_cases=4, seed=2)

    assert report["n_evaluated"] == 0
    assert report["llm_calls_failed"] == 4
    assert report["action_agreement_pct"] is None
    assert report["root_cause_agreement_pct"] is None


def test_agreement_perfect_match_when_llm_mirrors_heuristic(monkeypatch):
    from app.agents.heuristic_agent import diagnose_heuristic

    monkeypatch.setattr(diagnosis_agreement.time, "sleep", lambda *_a, **_k: None)

    def mirroring_diagnose(event, customer_history=None, on_fallback=None):
        h = diagnose_heuristic(event)
        return Diagnosis(
            root_cause=h.root_cause,
            confidence=0.8,
            reasoning="mirrors heuristic",
            recommended_action=h.recommended_action,
            action_params={},
            customer_message=None,
            llm_provider="groq",
            llm_fallback_used=False,
        )

    monkeypatch.setattr(diagnosis_agreement, "diagnose", mirroring_diagnose)

    report = diagnosis_agreement.run_diagnosis_agreement(n_cases=6, seed=3)

    assert report["action_agreement_pct"] == 100.0
    assert report["root_cause_agreement_pct"] == 100.0
