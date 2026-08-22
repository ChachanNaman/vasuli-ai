"""Unit tests for the deterministic guardrail engine (PRD §7).

Every rule in the PRD §7 table has at least one pass case and one block
case. No LLM, no network, no database — these run against plain dicts and
in-memory PastDecision lists.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.guardrails.rules import (
    MANDATE_PRE_DEBIT_NOTICE_MIN_HOURS,
    PastDecision,
    check_contact_window,
    check_cool_down_window,
    check_daily_contact_cap,
    check_dispute_freeze,
    check_dlt_template_compliance,
    check_economic_stopping_rule,
    check_invoice_spend_cap,
    check_mandate_pre_debit_notice,
    check_max_retry_attempts,
    check_opt_out,
    check_reliability_floor,
    check_retry_rate_limit,
    run_guardrails,
)

# 2026-08-20 12:00 UTC = 17:30 IST — inside the 08:00-19:00 contact window,
# so existing tests that don't care about contact_window aren't affected by
# it incidentally failing.
NOW = datetime(2026, 8, 20, 12, 0, 0, tzinfo=timezone.utc)

# 2026-08-20 21:30 UTC = 03:00 IST the next day — outside the contact window,
# used by the new contact_window tests below.
THREE_AM_IST = datetime(2026, 8, 20, 21, 30, 0, tzinfo=timezone.utc)

TOTAL_GUARDRAIL_CHECKS = 12


def base_customer(**overrides):
    c = {
        "customer_id": "cust_1",
        "name": "Test Customer",
        "opted_out_of_recovery_comms": False,
        "preferred_channel": "whatsapp",
        "language_pref": "hinglish",
    }
    c.update(overrides)
    return c


def base_event(**overrides):
    e = {
        "event_id": "evt_1",
        "event_type": "payment_failed",
        "amount": 999.0,
        "attempt_number": 1,
        "customer": base_customer(),
    }
    e.update(overrides)
    return e


# ---------------------------------------------------------------------------
# max_retry_attempts
# ---------------------------------------------------------------------------


def test_max_retry_attempts_passes_under_limit():
    event = base_event(event_type="payment_failed", attempt_number=2)
    result = check_max_retry_attempts(event)
    assert result.passed


def test_max_retry_attempts_blocks_at_payment_limit():
    event = base_event(event_type="payment_failed", attempt_number=3)
    result = check_max_retry_attempts(event)
    assert not result.passed


def test_max_retry_attempts_subscription_higher_limit():
    event = base_event(event_type="subscription_charge_failed", attempt_number=3)
    result = check_max_retry_attempts(event)
    assert result.passed  # 3 < 4 for subscriptions

    event = base_event(event_type="subscription_charge_failed", attempt_number=4)
    result = check_max_retry_attempts(event)
    assert not result.passed


def test_max_retry_attempts_ignores_non_retryable_event():
    event = base_event(event_type="checkout_abandoned", attempt_number=99)
    result = check_max_retry_attempts(event)
    assert result.passed


# ---------------------------------------------------------------------------
# cool_down_window
# ---------------------------------------------------------------------------


def test_cool_down_window_passes_with_no_history():
    result = check_cool_down_window("cust_1", NOW, [])
    assert result.passed


def test_cool_down_window_blocks_within_4h():
    past = [
        PastDecision(
            event_id="evt_0",
            customer_id="cust_1",
            timestamp=NOW - timedelta(hours=1),
            action_type="send_nudge",
            action_status="executed",
        )
    ]
    result = check_cool_down_window("cust_1", NOW, past)
    assert not result.passed


def test_cool_down_window_passes_after_4h():
    past = [
        PastDecision(
            event_id="evt_0",
            customer_id="cust_1",
            timestamp=NOW - timedelta(hours=5),
            action_type="send_nudge",
            action_status="executed",
        )
    ]
    result = check_cool_down_window("cust_1", NOW, past)
    assert result.passed


def test_cool_down_window_ignores_other_customers():
    past = [
        PastDecision(
            event_id="evt_0",
            customer_id="cust_other",
            timestamp=NOW - timedelta(minutes=5),
            action_type="send_nudge",
            action_status="executed",
        )
    ]
    result = check_cool_down_window("cust_1", NOW, past)
    assert result.passed


def test_cool_down_window_ignores_blocked_decisions():
    past = [
        PastDecision(
            event_id="evt_0",
            customer_id="cust_1",
            timestamp=NOW - timedelta(minutes=5),
            action_type="send_nudge",
            action_status="blocked_by_guardrail",
        )
    ]
    result = check_cool_down_window("cust_1", NOW, past)
    assert result.passed


# ---------------------------------------------------------------------------
# daily_contact_cap
# ---------------------------------------------------------------------------


def test_daily_contact_cap_passes_under_cap():
    past = [
        PastDecision("evt_0", "cust_1", NOW - timedelta(hours=10), "send_nudge", "executed"),
    ]
    result = check_daily_contact_cap("cust_1", NOW, past)
    assert result.passed


def test_daily_contact_cap_blocks_at_cap():
    past = [
        PastDecision("evt_0", "cust_1", NOW - timedelta(hours=10), "send_nudge", "executed"),
        PastDecision("evt_1", "cust_1", NOW - timedelta(hours=5), "generate_payment_link", "executed"),
    ]
    result = check_daily_contact_cap("cust_1", NOW, past)
    assert not result.passed


def test_daily_contact_cap_ignores_older_than_24h():
    past = [
        PastDecision("evt_0", "cust_1", NOW - timedelta(hours=25), "send_nudge", "executed"),
        PastDecision("evt_1", "cust_1", NOW - timedelta(hours=26), "send_nudge", "executed"),
    ]
    result = check_daily_contact_cap("cust_1", NOW, past)
    assert result.passed


# ---------------------------------------------------------------------------
# opt_out_enforcement
# ---------------------------------------------------------------------------


def test_opt_out_blocks_contact_action():
    event = base_event(customer=base_customer(opted_out_of_recovery_comms=True))
    result = check_opt_out(event, "send_nudge")
    assert not result.passed


def test_opt_out_allows_non_contact_action():
    event = base_event(customer=base_customer(opted_out_of_recovery_comms=True))
    result = check_opt_out(event, "smart_retry")
    assert result.passed


def test_opt_out_passes_when_not_opted_out():
    event = base_event(customer=base_customer(opted_out_of_recovery_comms=False))
    result = check_opt_out(event, "send_nudge")
    assert result.passed


# ---------------------------------------------------------------------------
# invoice_spend_cap
# ---------------------------------------------------------------------------


def test_invoice_spend_cap_blocks_over_1l():
    event = base_event(event_type="invoice_overdue", amount=150000)
    result = check_invoice_spend_cap(event, "escalate_b2b_chase")
    assert not result.passed


def test_invoice_spend_cap_passes_under_1l():
    event = base_event(event_type="invoice_overdue", amount=50000)
    result = check_invoice_spend_cap(event, "escalate_b2b_chase")
    assert result.passed


def test_invoice_spend_cap_ignores_non_invoice_events():
    event = base_event(event_type="payment_failed", amount=999999)
    result = check_invoice_spend_cap(event, "smart_retry")
    assert result.passed


# ---------------------------------------------------------------------------
# retry_rate_limit
# ---------------------------------------------------------------------------


def test_retry_rate_limit_blocks_within_30min():
    event = base_event(event_id="evt_1")
    past = [
        PastDecision("evt_1", "cust_1", NOW - timedelta(minutes=10), "smart_retry", "executed"),
    ]
    result = check_retry_rate_limit(event, NOW, past)
    assert not result.passed


def test_retry_rate_limit_passes_after_30min():
    event = base_event(event_id="evt_1")
    past = [
        PastDecision("evt_1", "cust_1", NOW - timedelta(minutes=45), "smart_retry", "executed"),
    ]
    result = check_retry_rate_limit(event, NOW, past)
    assert result.passed


def test_retry_rate_limit_ignores_other_events():
    event = base_event(event_id="evt_1")
    past = [
        PastDecision("evt_2", "cust_1", NOW - timedelta(minutes=5), "smart_retry", "executed"),
    ]
    result = check_retry_rate_limit(event, NOW, past)
    assert result.passed


# ---------------------------------------------------------------------------
# reliability_floor
# ---------------------------------------------------------------------------


def test_reliability_floor_firm_tier_below_threshold():
    event = base_event(event_type="invoice_overdue", payment_reliability_score=0.2)
    result = check_reliability_floor(event)
    assert result.passed
    assert "tier=firm" in result.detail


def test_reliability_floor_soft_tier_above_threshold():
    event = base_event(event_type="invoice_overdue", payment_reliability_score=0.85)
    result = check_reliability_floor(event)
    assert result.passed
    assert "tier=soft" in result.detail


def test_reliability_floor_ignores_non_invoice():
    event = base_event(event_type="payment_failed")
    result = check_reliability_floor(event)
    assert result.passed


# ---------------------------------------------------------------------------
# contact_window (RBI recovery-agent contact hours, ENHANCEMENTS.md §2.2)
# ---------------------------------------------------------------------------


def test_contact_window_blocks_contact_action_at_3am_ist():
    result = check_contact_window("send_nudge", THREE_AM_IST)
    assert not result.passed


def test_contact_window_passes_contact_action_within_window():
    result = check_contact_window("send_nudge", NOW)
    assert result.passed


def test_contact_window_ignores_silent_actions_at_any_hour():
    result = check_contact_window("smart_retry", THREE_AM_IST)
    assert result.passed


# ---------------------------------------------------------------------------
# mandate_pre_debit_notice (RBI e-mandate framework, ENHANCEMENTS.md §2.2)
# ---------------------------------------------------------------------------


def test_mandate_pre_debit_notice_blocks_silent_retry_on_active_mandate():
    event = base_event(event_type="subscription_charge_failed", mandate_status="active")
    result = check_mandate_pre_debit_notice(event, "smart_retry", {})
    assert not result.passed


def test_mandate_pre_debit_notice_passes_with_confirmed_notice():
    event = base_event(event_type="subscription_charge_failed", mandate_status="active")
    result = check_mandate_pre_debit_notice(
        event, "smart_retry", {"pre_debit_notice_hours": MANDATE_PRE_DEBIT_NOTICE_MIN_HOURS}
    )
    assert result.passed


def test_mandate_pre_debit_notice_blocks_insufficient_notice():
    event = base_event(event_type="subscription_charge_failed", mandate_status="active")
    result = check_mandate_pre_debit_notice(event, "smart_retry", {"pre_debit_notice_hours": 2})
    assert not result.passed


def test_mandate_pre_debit_notice_ignores_expired_mandate():
    event = base_event(event_type="subscription_charge_failed", mandate_status="expired")
    result = check_mandate_pre_debit_notice(event, "initiate_mandate_reauth", {})
    assert result.passed


def test_mandate_pre_debit_notice_ignores_non_subscription_event():
    event = base_event(event_type="payment_failed")
    result = check_mandate_pre_debit_notice(event, "smart_retry", {})
    assert result.passed


def test_mandate_pre_debit_notice_ignores_non_mandate_actions():
    event = base_event(event_type="subscription_charge_failed", mandate_status="active")
    result = check_mandate_pre_debit_notice(event, "send_nudge", {})
    assert result.passed


# ---------------------------------------------------------------------------
# dlt_template_compliance (TRAI DLT registration, ENHANCEMENTS.md §2.2)
# ---------------------------------------------------------------------------


def test_dlt_template_compliance_passes_for_comms_action():
    result = check_dlt_template_compliance("send_nudge")
    assert result.passed
    assert "template" in result.detail


def test_dlt_template_compliance_passes_for_non_comms_action():
    result = check_dlt_template_compliance("smart_retry")
    assert result.passed


# ---------------------------------------------------------------------------
# dispute_freeze (ENHANCEMENTS.md §2.2)
# ---------------------------------------------------------------------------


def test_dispute_freeze_blocks_any_action_on_disputed_payment():
    event = base_event(dispute_opened=True)
    result = check_dispute_freeze(event)
    assert not result.passed


def test_dispute_freeze_passes_without_open_dispute():
    event = base_event(dispute_opened=False)
    result = check_dispute_freeze(event)
    assert result.passed


# ---------------------------------------------------------------------------
# economic_stopping_rule (ENHANCEMENTS.md §2.3)
# ---------------------------------------------------------------------------


def test_economic_stopping_rule_blocks_tiny_amount():
    event = base_event(amount=0.10)  # a few paise — never worth a retry
    result = check_economic_stopping_rule(event, "smart_retry", "bank_server_down")
    assert not result.passed


def test_economic_stopping_rule_passes_reasonable_amount():
    event = base_event(amount=999.0)
    result = check_economic_stopping_rule(event, "smart_retry", "bank_server_down")
    assert result.passed


def test_economic_stopping_rule_ignores_no_op_actions():
    event = base_event(amount=0.10)
    result = check_economic_stopping_rule(event, "flag_for_human_review", None)
    assert result.passed


# ---------------------------------------------------------------------------
# run_guardrails orchestrator
# ---------------------------------------------------------------------------


def test_run_guardrails_all_pass_executes():
    event = base_event()
    result = run_guardrails(event, "smart_retry", [], now=NOW)
    assert result.action_status == "executed"
    assert result.block_reason is None
    assert len(result.checks) == TOTAL_GUARDRAIL_CHECKS  # every rule logged, pass or fail


def test_run_guardrails_opt_out_only_failure_yields_skipped_opt_out():
    event = base_event(customer=base_customer(opted_out_of_recovery_comms=True))
    result = run_guardrails(event, "send_nudge", [], now=NOW)
    assert result.action_status == "skipped_opt_out"


def test_run_guardrails_non_optout_failure_yields_blocked():
    event = base_event(attempt_number=3)
    result = run_guardrails(event, "smart_retry", [], now=NOW)
    assert result.action_status == "blocked_by_guardrail"
    assert "max_retry_attempts" in result.block_reason


def test_run_guardrails_logs_every_check_even_on_early_failure():
    event = base_event(attempt_number=3, customer=base_customer(opted_out_of_recovery_comms=True))
    result = run_guardrails(event, "smart_retry", [], now=NOW)
    # both max_retry_attempts and opt-out related checks should still all be present
    assert len(result.checks) == TOTAL_GUARDRAIL_CHECKS
    rule_names = {c.rule_name for c in result.checks}
    assert "max_retry_attempts" in rule_names
    assert "opt_out_enforcement" in rule_names


def test_run_guardrails_retry_storm_scenario_blocks_second_rapid_retry():
    """PRD §11 failure story: rapid repeat retries on the same payment must
    be caught by retry_rate_limit even though every other rule passes."""
    event = base_event(event_id="evt_storm", attempt_number=1)
    past = [
        PastDecision("evt_storm", "cust_1", NOW - timedelta(minutes=2), "smart_retry", "executed"),
    ]
    result = run_guardrails(event, "smart_retry", past, now=NOW)
    assert result.action_status == "blocked_by_guardrail"
    assert "retry_rate_limit" in result.block_reason
