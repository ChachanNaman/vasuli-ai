"""Tests for the recovery outcome probability model (PRD §9).

These don't assert on the random draw itself (that would be flaky) — they
assert the *probabilities* used are correct for each root cause/channel/
score combination, which is the actual assumption worth locking down.
"""

from __future__ import annotations

from app.recovery import outcome_model


def test_smart_retry_probability_bank_server_down():
    draw = outcome_model.smart_retry_outcome("bank_server_down")
    assert draw.probability_used == 0.70


def test_smart_retry_probability_insufficient_funds():
    draw = outcome_model.smart_retry_outcome("insufficient_funds")
    assert draw.probability_used == 0.55


def test_smart_retry_probability_card_expired_is_low():
    draw = outcome_model.smart_retry_outcome("card_expired")
    assert draw.probability_used == 0.05


def test_smart_retry_unknown_root_cause_uses_default():
    draw = outcome_model.smart_retry_outcome("some_new_reason")
    assert draw.probability_used == outcome_model.DEFAULT_RETRY_PROBABILITY


def test_generate_payment_link_bumps_for_card_expired():
    base = outcome_model.generate_payment_link_outcome("insufficient_funds")
    bumped = outcome_model.generate_payment_link_outcome("card_expired")
    assert bumped.probability_used > base.probability_used


def test_send_nudge_whatsapp_beats_email():
    whatsapp = outcome_model.send_nudge_outcome("whatsapp", minutes_since_abandon=10)
    email = outcome_model.send_nudge_outcome("email", minutes_since_abandon=10)
    assert whatsapp.probability_used > email.probability_used


def test_send_nudge_decays_with_time():
    fresh = outcome_model.send_nudge_outcome("whatsapp", minutes_since_abandon=5)
    stale = outcome_model.send_nudge_outcome("whatsapp", minutes_since_abandon=60 * 24 * 10)
    assert fresh.probability_used > stale.probability_used


def test_escalate_b2b_chase_higher_reliability_higher_probability():
    reliable = outcome_model.escalate_b2b_chase_outcome(0.9, days_overdue=5)
    unreliable = outcome_model.escalate_b2b_chase_outcome(0.1, days_overdue=5)
    assert reliable.probability_used > unreliable.probability_used


def test_escalate_b2b_chase_more_overdue_lowers_probability():
    fresh = outcome_model.escalate_b2b_chase_outcome(0.5, days_overdue=2)
    stale = outcome_model.escalate_b2b_chase_outcome(0.5, days_overdue=120)
    assert fresh.probability_used > stale.probability_used


def test_mandate_reauth_uses_fixed_baseline():
    draw = outcome_model.initiate_mandate_reauth_outcome()
    assert draw.probability_used == outcome_model.MANDATE_REAUTH_PROBABILITY


def test_no_execution_outcome_never_recovers():
    draw = outcome_model.no_execution_outcome("flag_for_human_review")
    assert draw.recovered is False
    assert draw.probability_used == 0.0
