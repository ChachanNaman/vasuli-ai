"""Tests for the recovery executor dispatch (app/recovery/executors.py).
Razorpay calls are monkeypatched — no real network/keys needed.
"""

from __future__ import annotations

import pytest

from app.recovery import executors
from app.recovery.razorpay_client import PaymentLinkResult


def base_event(**overrides):
    e = {
        "event_id": "evt_1",
        "amount": 999.0,
        "currency": "INR",
        "customer": {"name": "Test Customer", "preferred_channel": "whatsapp"},
    }
    e.update(overrides)
    return e


@pytest.fixture
def fake_payment_link(monkeypatch):
    def fake(**kwargs):
        return PaymentLinkResult(url="https://rzp.io/fake/plink_test", is_live=False)

    monkeypatch.setattr(executors, "create_payment_link", fake)
    return fake


def test_smart_retry_uses_payment_link_and_outcome_model(fake_payment_link, monkeypatch):
    monkeypatch.setattr(
        "random.random", lambda: 0.0
    )  # force recovery (probability > 0 for bank_server_down)
    result = executors.execute("smart_retry", base_event(), "bank_server_down")
    assert result.recovered is True
    assert result.amount_recovered == 999.0
    assert result.razorpay_payment_link == "https://rzp.io/fake/plink_test"
    assert result.is_live_integration is False


def test_smart_retry_no_recovery_zero_amount(fake_payment_link, monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.999)  # force no recovery
    result = executors.execute("smart_retry", base_event(), "card_expired")
    assert result.recovered is False
    assert result.amount_recovered == 0.0


def test_generate_payment_link_dispatch(fake_payment_link, monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.0)
    result = executors.execute("generate_payment_link", base_event(), "card_expired")
    assert result.recovered is True
    assert result.razorpay_payment_link is not None


def test_send_nudge_dispatch_no_payment_link(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.0)
    event = base_event(minutes_since_abandon=5)
    result = executors.execute("send_nudge", event, "checkout_abandoned")
    assert result.razorpay_payment_link is None
    assert result.is_live_integration is False


def test_escalate_b2b_chase_dispatch(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.0)
    event = base_event(payment_reliability_score=0.9, days_overdue=5)
    result = executors.execute("escalate_b2b_chase", event, "invoice_overdue")
    assert result.recovered is True
    assert result.amount_recovered == event["amount"]


def test_initiate_mandate_reauth_dispatch(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.999)
    result = executors.execute("initiate_mandate_reauth", base_event(), "mandate_expired")
    assert result.recovered is False


def test_flag_for_human_review_never_executes_or_recovers():
    result = executors.execute("flag_for_human_review", base_event(), "unknown")
    assert result.recovered is False
    assert result.amount_recovered == 0.0
    assert result.razorpay_payment_link is None


def test_no_action_recommended_never_recovers():
    result = executors.execute("no_action_recommended", base_event(), "unknown")
    assert result.recovered is False
