"""Tests for the diagnosis agent's contract validation and fallback wiring.
No real network calls — call_diagnosis_llm is monkeypatched.
"""

from __future__ import annotations

import pytest

from app.agents import diagnosis_agent
from app.agents.diagnosis_agent import DiagnosisValidationError, diagnose
from app.agents.llm_client import LLMResult


def _patch_llm(monkeypatch, data, provider="groq", fallback_used=False):
    def fake_call(system_prompt, user_prompt, tool_schema, on_fallback=None):
        return LLMResult(data=data, provider=provider, fallback_used=fallback_used)

    monkeypatch.setattr(diagnosis_agent, "call_diagnosis_llm", fake_call)


VALID_RESPONSE = {
    "root_cause": "bank_server_down",
    "confidence": 0.82,
    "reasoning": "Two-sentence explanation.",
    "recommended_action": "smart_retry",
    "action_params": {"retry_window_minutes": 45},
    "customer_message": None,
}


def test_diagnose_returns_valid_diagnosis(monkeypatch):
    _patch_llm(monkeypatch, VALID_RESPONSE)
    result = diagnose({"event_id": "evt_1"})
    assert result.root_cause == "bank_server_down"
    assert result.recommended_action == "smart_retry"
    assert result.llm_provider == "groq"
    assert result.llm_fallback_used is False


def test_diagnose_marks_fallback_used(monkeypatch):
    _patch_llm(monkeypatch, VALID_RESPONSE, provider="gemini", fallback_used=True)
    result = diagnose({"event_id": "evt_1"})
    assert result.llm_provider == "gemini"
    assert result.llm_fallback_used is True


def test_diagnose_rejects_disallowed_action(monkeypatch):
    bad = dict(VALID_RESPONSE, recommended_action="delete_customer_account")
    _patch_llm(monkeypatch, bad)
    with pytest.raises(DiagnosisValidationError):
        diagnose({"event_id": "evt_1"})


def test_diagnose_rejects_out_of_range_confidence(monkeypatch):
    bad = dict(VALID_RESPONSE, confidence=1.5)
    _patch_llm(monkeypatch, bad)
    with pytest.raises(DiagnosisValidationError):
        diagnose({"event_id": "evt_1"})


def test_diagnose_rejects_missing_field(monkeypatch):
    bad = dict(VALID_RESPONSE)
    del bad["reasoning"]
    _patch_llm(monkeypatch, bad)
    with pytest.raises(DiagnosisValidationError):
        diagnose({"event_id": "evt_1"})
