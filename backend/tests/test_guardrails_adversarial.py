"""Adversarial guardrail test (ENHANCEMENTS.md §2.6).

A stub "agent" that, for every case in a batch, recommends the single
worst legal action available for that event — a silent retry against a
maxed-out attempt count, contacting an opted-out customer at 3am, an
auto-escalated invoice over the spend cap, a retry against an
already-disputed payment, a silent debit against a live mandate with no
notice, and an action that costs more than it could possibly recover.

This converts "the guardrail engine can't be argued past" from an
assertion in the README into a test that actually tries to break it and
fails to. Nothing here calls the LLM or the executor — the point is that
zero disallowed actions should even be *eligible* to reach the executor
layer, which the pipeline only calls when action_status == "executed".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.data.generator import generate_batch
from app.guardrails.rules import PastDecision, run_guardrails

# 21:30 UTC = 03:00 IST the next day — outside the RBI recovery-agent
# contact window on purpose.
THREE_AM_IST = datetime(2026, 1, 15, 21, 30, 0, tzinfo=timezone.utc)


def _worst_action_for(event: dict) -> str:
    """The single most aggressive action available for this event type —
    deliberately ignoring whether it's actually a good idea."""
    event_type = event.get("event_type")
    if event_type in ("payment_failed",):
        return "smart_retry"
    if event_type == "subscription_charge_failed":
        return "smart_retry" if event.get("mandate_status") == "active" else "initiate_mandate_reauth"
    if event_type == "checkout_abandoned":
        return "send_nudge"
    if event_type == "invoice_overdue":
        return "escalate_b2b_chase"
    return "smart_retry"


def _make_adversarial(event: dict) -> dict:
    """Mutate a generated event to be maximally hostile to every rule at
    once: opted-out customer, maxed-out attempt count, over-cap invoice
    amount, an open dispute, and a live mandate with zero notice."""
    event = dict(event)
    event["attempt_number"] = 99
    event["amount"] = max(event.get("amount") or 0, 500_000)
    event["dispute_opened"] = True
    event["mandate_status"] = "active"
    customer = dict(event.get("customer", {}))
    customer["opted_out_of_recovery_comms"] = True
    event["customer"] = customer
    return event


def _hostile_history(event: dict, now: datetime) -> list[PastDecision]:
    """Recent decision history engineered to blow every rate/frequency
    limit: a retry on this exact event 2 minutes ago, and two contacts on
    this customer in the last hour."""
    event_id = event["event_id"]
    customer_id = event["customer"]["customer_id"]
    return [
        PastDecision(event_id, customer_id, now - timedelta(minutes=2), "smart_retry", "executed"),
        PastDecision(event_id, customer_id, now - timedelta(minutes=30), "send_nudge", "executed"),
        PastDecision(event_id, customer_id, now - timedelta(minutes=45), "send_nudge", "executed"),
    ]


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_adversarial_worst_case_agent_never_gets_anything_executed(seed):
    events = generate_batch(80, seed=seed)
    executed = []

    for event_obj in events:
        event = _make_adversarial(event_obj.to_dict())
        worst_action = _worst_action_for(event)
        history = _hostile_history(event, THREE_AM_IST)

        result = run_guardrails(
            event,
            worst_action,
            history,
            now=THREE_AM_IST,
            root_cause=event.get("failure_reason_code"),
            action_params={},  # never a confirmed pre-debit notice
        )

        if result.action_status == "executed":
            executed.append((event["event_id"], worst_action, result.to_dict()))

    assert executed == [], (
        f"{len(executed)}/{len(events)} adversarial worst-case actions were "
        f"NOT blocked: {executed[:3]}"
    )


def test_adversarial_agent_always_fails_at_least_one_rule():
    """Sanity check on the test itself: every mutated case should trip at
    least one guardrail (otherwise the adversarial mutation isn't actually
    adversarial for that event, and a 0-executed result would be
    meaningless)."""
    events = generate_batch(20, seed=42)
    for event_obj in events:
        event = _make_adversarial(event_obj.to_dict())
        worst_action = _worst_action_for(event)
        history = _hostile_history(event, THREE_AM_IST)
        result = run_guardrails(
            event, worst_action, history, now=THREE_AM_IST,
            root_cause=event.get("failure_reason_code"), action_params={},
        )
        failed_rules = [c.rule_name for c in result.checks if not c.passed]
        assert failed_rules, f"expected at least one failed rule for {event['event_id']}"
