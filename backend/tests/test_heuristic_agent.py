"""Tests for the deterministic heuristic fallback agent (ENHANCEMENTS.md
§2.5). No mocking needed — this module makes no network calls at all,
which is the entire point of it."""

from __future__ import annotations

from app.agents.diagnosis_agent import ALLOWED_ACTIONS
from app.agents.heuristic_agent import diagnose_heuristic


def base_event(**overrides):
    e = {
        "event_id": "evt_1",
        "event_type": "payment_failed",
        "amount": 999.0,
        "attempt_number": 1,
        "failure_reason_code": "network_error",
        "customer": {"customer_id": "cust_1", "name": "Test Customer"},
    }
    e.update(overrides)
    return e


def test_dispute_opened_always_flags_for_human_review():
    event = base_event(dispute_opened=True)
    result = diagnose_heuristic(event)
    assert result.recommended_action == "flag_for_human_review"
    assert result.confidence > 0.9


def test_transient_payment_failure_recommends_retry():
    event = base_event(failure_reason_code="bank_server_down", attempt_number=1)
    result = diagnose_heuristic(event)
    assert result.recommended_action == "smart_retry"


def test_dead_end_reason_recommends_payment_link():
    event = base_event(failure_reason_code="card_expired", attempt_number=1)
    result = diagnose_heuristic(event)
    assert result.recommended_action == "generate_payment_link"


def test_exhausted_retries_flags_for_human_review():
    event = base_event(failure_reason_code="insufficient_funds", attempt_number=3)
    result = diagnose_heuristic(event)
    assert result.recommended_action == "flag_for_human_review"


def test_expired_mandate_recommends_reauth():
    event = base_event(
        event_type="subscription_charge_failed",
        failure_reason_code="mandate_expired",
        mandate_status="expired",
        attempt_number=1,
    )
    result = diagnose_heuristic(event)
    assert result.recommended_action == "initiate_mandate_reauth"


def test_active_mandate_retry_includes_pre_debit_notice():
    event = base_event(
        event_type="subscription_charge_failed",
        failure_reason_code="insufficient_funds",
        mandate_status="active",
        attempt_number=1,
    )
    result = diagnose_heuristic(event)
    assert result.recommended_action == "smart_retry"
    assert result.action_params.get("pre_debit_notice_hours") == 24


def test_recent_checkout_abandonment_recommends_nudge():
    event = base_event(
        event_type="checkout_abandoned",
        checkout_stage_reached="payment_method_select",
        minutes_since_abandon=15,
    )
    result = diagnose_heuristic(event)
    assert result.recommended_action == "send_nudge"


def test_stale_checkout_abandonment_recommends_no_action():
    event = base_event(
        event_type="checkout_abandoned",
        checkout_stage_reached="cart",
        minutes_since_abandon=60 * 24 * 5,
    )
    result = diagnose_heuristic(event)
    assert result.recommended_action == "no_action_recommended"


def test_invoice_over_cap_flags_for_human_review():
    event = base_event(event_type="invoice_overdue", amount=150_000, payment_reliability_score=0.5)
    result = diagnose_heuristic(event)
    assert result.recommended_action == "flag_for_human_review"


def test_invoice_under_cap_recommends_b2b_chase():
    event = base_event(event_type="invoice_overdue", amount=50_000, payment_reliability_score=0.5)
    result = diagnose_heuristic(event)
    assert result.recommended_action == "escalate_b2b_chase"


def test_result_always_uses_allowed_action_set():
    """Every branch of the heuristic must resolve to something the
    guardrail engine and executors actually know how to handle."""
    scenarios = [
        base_event(),
        base_event(failure_reason_code="card_expired"),
        base_event(attempt_number=5),
        base_event(event_type="subscription_charge_failed", mandate_status="revoked"),
        base_event(event_type="checkout_abandoned", minutes_since_abandon=10),
        base_event(event_type="invoice_overdue", amount=200_000),
        base_event(event_type="something_new_the_generator_might_add_later"),
    ]
    for event in scenarios:
        result = diagnose_heuristic(event)
        assert result.recommended_action in ALLOWED_ACTIONS
        assert result.llm_provider == "heuristic"
        assert result.llm_fallback_used is True
