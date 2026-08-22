"""The four evaluation arms (ENHANCEMENTS.md §2.1).

Each arm is a pure function of (event, case_seed) -> ArmResult. All four
arms are evaluated on *the same case* using the same `case_seed` — common
random numbers — via `random.seed(case_seed)` immediately before the one
outcome draw each arm makes for that case, so a case that "gets lucky"
gets lucky identically in every arm. Differences between arms are then
attributable to policy, not noise.

Simplifying assumption, stated explicitly: every case is evaluated
independently under each policy — no cross-case history. Guardrail rules
that depend on a customer's decision history (cool-down, daily cap,
retry-rate-limit) therefore always see an empty history, i.e. "first
touch" semantics for every case. This is a conservative choice: it gives
Vasuli's guardrails *less* to block on than a real sequential run would,
which if anything understates Vasuli's compliance advantage over the
baseline arms rather than flattering it.

`now` is fixed to a single daytime instant for every case in every arm, so
the RBI contact-window rule doesn't introduce arbitrary pass/fail noise
unrelated to the actual policy being compared.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timezone

from app.agents.heuristic_agent import diagnose_heuristic
from app.guardrails.rules import run_guardrails
from app.recovery import cost_model, outcome_model

# 2026-01-15 12:00 UTC = 17:30 IST — inside the RBI contact window, fixed
# for every case/arm so contact_window never introduces incidental noise.
EVAL_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


@dataclass
class ArmResult:
    case_id: str
    event_type: str
    amount: float
    action_type: str
    recovered: bool
    amount_recovered: float
    cost: float
    contacted: bool
    guardrail_violations: int  # rules that would fail for this action, whether or not enforced
    enforced: bool  # whether this arm actually respects the guardrail engine's verdict


def _case_seed(master_seed: int, event_id: str) -> int:
    """Deterministic per-case seed derived from the master seed and this
    case's event_id, so re-running with the same master_seed reproduces
    the exact same per-case draws regardless of iteration order."""
    import hashlib

    digest = hashlib.sha256(f"{master_seed}:{event_id}".encode()).hexdigest()
    return int(digest[:16], 16)


def _draw_outcome(action_type: str, event: dict, root_cause: str | None, case_seed: int) -> outcome_model.OutcomeDraw:
    """Seed, then make exactly one outcome draw for this (action, event) —
    the common-random-numbers contract every arm relies on."""
    random.seed(case_seed)
    if action_type == "smart_retry":
        return outcome_model.smart_retry_outcome(root_cause or "")
    if action_type == "generate_payment_link":
        return outcome_model.generate_payment_link_outcome(root_cause or "")
    if action_type == "send_nudge":
        channel = event.get("customer", {}).get("preferred_channel", "sms")
        return outcome_model.send_nudge_outcome(channel, event.get("minutes_since_abandon"))
    if action_type == "escalate_b2b_chase":
        return outcome_model.escalate_b2b_chase_outcome(
            event.get("payment_reliability_score"), event.get("days_overdue")
        )
    if action_type == "initiate_mandate_reauth":
        return outcome_model.initiate_mandate_reauth_outcome()
    return outcome_model.no_execution_outcome(action_type)


def _case_amount(event: dict) -> float:
    return event.get("amount") or event.get("cart_value") or 0.0


def _fixed_action_for(event: dict) -> str:
    """fixed_dunning's naive, cause-blind action ladder: the same single
    action for every event of a given type, regardless of root cause,
    attempt history, mandate status, or reliability score."""
    event_type = event.get("event_type")
    if event_type in ("payment_failed", "subscription_charge_failed"):
        return "smart_retry"
    if event_type == "checkout_abandoned":
        return "send_nudge"
    if event_type == "invoice_overdue":
        return "escalate_b2b_chase"
    return "flag_for_human_review"


def _worst_action_for(event: dict) -> str:
    """max_pressure's most-aggressive-available action — mirrors
    tests/test_guardrails_adversarial.py's stub agent, reused here as a
    policy rather than a test fixture."""
    event_type = event.get("event_type")
    if event_type == "payment_failed":
        return "smart_retry"
    if event_type == "subscription_charge_failed":
        return "smart_retry"
    if event_type == "checkout_abandoned":
        return "send_nudge"
    if event_type == "invoice_overdue":
        return "escalate_b2b_chase"
    return "smart_retry"


def _count_guardrail_violations(event: dict, action: str, root_cause: str | None) -> int:
    result = run_guardrails(event, action, [], now=EVAL_NOW, root_cause=root_cause, action_params={})
    return len([c for c in result.checks if not c.passed])


NO_OP_ACTIONS = {"flag_for_human_review", "no_action_recommended"}


def _organic_draw(event: dict, master_seed: int) -> outcome_model.OutcomeDraw:
    """The same natural-recovery draw do_nothing uses, keyed by the same
    case_seed. Used both for the do_nothing arm itself and for any other
    arm's cases where no real action executes — a case the agent declines
    to touch (blocked, skipped, or genuinely a no-op call) still has its
    organic chance to resolve on its own; it must not be scored as a hard
    zero just because the agent didn't act. Without this, any arm that
    ever exercises restraint would be unfairly penalized relative to
    do_nothing for the exact same cases."""
    case_seed = _case_seed(master_seed, event["event_id"])
    random.seed(case_seed)
    return outcome_model.natural_recovery_outcome(event)


def run_do_nothing(event: dict, master_seed: int) -> ArmResult:
    draw = _organic_draw(event, master_seed)
    return ArmResult(
        case_id=event["event_id"],
        event_type=event["event_type"],
        amount=_case_amount(event),
        action_type="do_nothing",
        recovered=draw.recovered,
        amount_recovered=_case_amount(event) if draw.recovered else 0.0,
        cost=0.0,
        contacted=False,
        guardrail_violations=0,
        enforced=True,
    )


def _fixed_arm(event: dict, master_seed: int, action: str, violations: int) -> ArmResult:
    amount = _case_amount(event)
    root_cause = event.get("failure_reason_code")

    if action in NO_OP_ACTIONS:
        draw = _organic_draw(event, master_seed)
    else:
        case_seed = _case_seed(master_seed, event["event_id"])
        draw = _draw_outcome(action, event, root_cause, case_seed)

    return ArmResult(
        case_id=event["event_id"],
        event_type=event["event_type"],
        amount=amount,
        action_type=action,
        recovered=draw.recovered,
        amount_recovered=amount if draw.recovered else 0.0,
        cost=cost_model.action_cost(action),
        contacted=action in cost_model.CONTACT_ACTION_TYPES,
        guardrail_violations=violations,
        enforced=False,  # fires regardless of what the guardrail engine would say
    )


def run_fixed_dunning(event: dict, master_seed: int) -> ArmResult:
    action = _fixed_action_for(event)
    violations = _count_guardrail_violations(event, action, event.get("failure_reason_code"))
    return _fixed_arm(event, master_seed, action, violations)


def run_max_pressure(event: dict, master_seed: int) -> ArmResult:
    action = _worst_action_for(event)
    violations = _count_guardrail_violations(event, action, event.get("failure_reason_code"))
    return _fixed_arm(event, master_seed, action, violations)


def run_vasuli(event: dict, master_seed: int) -> ArmResult:
    """The real guardrailed policy: heuristic diagnosis (fast, deterministic,
    zero-API-key — see run_comparison.py's module docstring for why this
    arm doesn't call the live LLM) + the actual guardrail engine + the
    actual outcome model.

    When the guardrail engine blocks/skips the proposed action, or the
    diagnosis itself is a no-op (flag_for_human_review /
    no_action_recommended), the case defers to the same organic-recovery
    draw as do_nothing — Vasuli choosing *not* to act must never score
    worse than never having tried, or "incremental recovery" would
    penalize exactly the restraint the guardrail engine exists to provide.
    """
    diagnosis = diagnose_heuristic(event)
    action = diagnosis.recommended_action
    root_cause = diagnosis.root_cause

    guardrail_result = run_guardrails(
        event, action, [], now=EVAL_NOW, root_cause=root_cause, action_params=diagnosis.action_params
    )
    violations = len([c for c in guardrail_result.checks if not c.passed])
    amount = _case_amount(event)

    if guardrail_result.action_status != "executed" or action in NO_OP_ACTIONS:
        draw = _organic_draw(event, master_seed)
        return ArmResult(
            case_id=event["event_id"],
            event_type=event["event_type"],
            amount=amount,
            action_type=action,
            recovered=draw.recovered,
            amount_recovered=amount if draw.recovered else 0.0,
            cost=0.0,
            contacted=False,
            guardrail_violations=violations,
            enforced=True,
        )

    case_seed = _case_seed(master_seed, event["event_id"])
    draw = _draw_outcome(action, event, root_cause, case_seed)
    return ArmResult(
        case_id=event["event_id"],
        event_type=event["event_type"],
        amount=amount,
        action_type=action,
        recovered=draw.recovered,
        amount_recovered=amount if draw.recovered else 0.0,
        cost=cost_model.action_cost(action),
        contacted=action in cost_model.CONTACT_ACTION_TYPES,
        guardrail_violations=violations,
        enforced=True,
    )


ARMS = {
    "do_nothing": run_do_nothing,
    "fixed_dunning": run_fixed_dunning,
    "vasuli": run_vasuli,
    "max_pressure": run_max_pressure,
}
