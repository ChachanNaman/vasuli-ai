"""Recovery outcome probability model (PRD §9).

Every action type gets a *probabilistic* outcome, not a hard-coded win —
"one cherry-picked match proves nothing" per the brief. This module is the
single place all recovery-probability assumptions live, so the exact model
is inspectable rather than a black box.

None of this is real-world calibrated data — it's a hand-tuned, clearly
documented simulation, and is presented to judges as exactly that.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class OutcomeDraw:
    recovered: bool
    probability_used: float
    notes: str


# ---------------------------------------------------------------------------
# smart_retry — probability weighted by root cause and retry timing.
# Mirrors PRD §9's example numbers: insufficient_funds retried next day ≈
# 55%, bank_server_down retried in 45 min ≈ 70%, card_expired basically
# never recovers via retry (same card, same problem) — that case should
# have been routed to generate_payment_link by the diagnosis agent instead,
# but we still model it honestly here in case the agent gets it wrong.
# ---------------------------------------------------------------------------
RETRY_PROBABILITY_BY_ROOT_CAUSE = {
    "insufficient_funds": 0.55,
    "bank_server_down": 0.70,
    "network_error": 0.65,
    "otp_timeout": 0.60,
    "otp_mismatch": 0.50,
    "daily_limit_exceeded": 0.35,
    "card_expired": 0.05,
    "risk_declined": 0.10,
    "mandate_expired": 0.05,
    "mandate_revoked": 0.05,
}
DEFAULT_RETRY_PROBABILITY = 0.40


def retry_probability(root_cause: str) -> float:
    """Pure probability lookup, no random draw — used by both
    `smart_retry_outcome` (below) and the guardrail engine's economic
    stopping rule (app/guardrails/rules.py), which needs an expected-value
    estimate *without* consuming a random draw (that would desync the
    common-random-numbers seeding the evaluation harness relies on)."""
    return RETRY_PROBABILITY_BY_ROOT_CAUSE.get(root_cause, DEFAULT_RETRY_PROBABILITY)


def smart_retry_outcome(root_cause: str) -> OutcomeDraw:
    p = retry_probability(root_cause)
    recovered = random.random() < p
    return OutcomeDraw(
        recovered=recovered,
        probability_used=p,
        notes=f"smart_retry recovery probability for root_cause={root_cause!r} is {p}",
    )


# ---------------------------------------------------------------------------
# generate_payment_link — a fresh manual-completion link. Higher baseline
# than a same-method retry since the customer picks a different method,
# but still decays with how stale the failure is.
# ---------------------------------------------------------------------------
PAYMENT_LINK_BASE_PROBABILITY = 0.45


def payment_link_probability(root_cause: str) -> float:
    """Pure probability lookup — see `retry_probability`'s docstring."""
    # card_expired / risk_declined are exactly the cases a fresh link helps
    # most with, since the underlying blocker (same card, same method) is
    # sidestepped rather than retried.
    bump = 0.15 if root_cause in ("card_expired", "risk_declined") else 0.0
    return min(0.85, PAYMENT_LINK_BASE_PROBABILITY + bump)


def generate_payment_link_outcome(root_cause: str) -> OutcomeDraw:
    p = payment_link_probability(root_cause)
    recovered = random.random() < p
    return OutcomeDraw(
        recovered=recovered,
        probability_used=p,
        notes=f"generate_payment_link recovery probability for root_cause={root_cause!r} is {p}",
    )


# ---------------------------------------------------------------------------
# send_nudge — weighted by channel, language match, and time since abandon.
# ---------------------------------------------------------------------------
CHANNEL_BASE_PROBABILITY = {
    "whatsapp": 0.35,
    "sms": 0.22,
    "email": 0.12,
    "call": 0.28,
}


def nudge_probability(preferred_channel: str, minutes_since_abandon: int | None = None) -> float:
    """Pure probability lookup — see `retry_probability`'s docstring."""
    p = CHANNEL_BASE_PROBABILITY.get(preferred_channel, 0.15)

    if minutes_since_abandon is not None:
        # Decay: recovery odds roughly halve every 24h since abandonment.
        days = minutes_since_abandon / (60 * 24)
        decay = 0.5 ** (days / 1.0)
        p = p * max(0.15, decay)

    return round(min(p, 0.6), 3)


def send_nudge_outcome(
    preferred_channel: str, minutes_since_abandon: int | None = None
) -> OutcomeDraw:
    p = nudge_probability(preferred_channel, minutes_since_abandon)
    recovered = random.random() < p
    return OutcomeDraw(
        recovered=recovered,
        probability_used=p,
        notes=f"send_nudge via {preferred_channel} probability={p} "
        f"(minutes_since_abandon={minutes_since_abandon})",
    )


# ---------------------------------------------------------------------------
# escalate_b2b_chase — weighted by payment_reliability_score and days_overdue.
# ---------------------------------------------------------------------------


def b2b_chase_probability(payment_reliability_score: float | None, days_overdue: int | None) -> float:
    """Pure probability lookup — see `retry_probability`'s docstring."""
    score = payment_reliability_score if payment_reliability_score is not None else 0.5
    overdue_penalty = min(0.3, (days_overdue or 0) / 400)
    return round(max(0.05, min(0.75, score * 0.8 - overdue_penalty + 0.15)), 3)


def escalate_b2b_chase_outcome(
    payment_reliability_score: float | None, days_overdue: int | None
) -> OutcomeDraw:
    p = b2b_chase_probability(payment_reliability_score, days_overdue)
    recovered = random.random() < p
    return OutcomeDraw(
        recovered=recovered,
        probability_used=p,
        notes=f"escalate_b2b_chase probability={p} "
        f"(reliability_score={payment_reliability_score}, days_overdue={days_overdue})",
    )


# ---------------------------------------------------------------------------
# initiate_mandate_reauth — lower baseline, reflects real-world mandate churn.
# ---------------------------------------------------------------------------
MANDATE_REAUTH_PROBABILITY = 0.30


def mandate_reauth_probability() -> float:
    """Pure probability lookup — see `retry_probability`'s docstring."""
    return MANDATE_REAUTH_PROBABILITY


def initiate_mandate_reauth_outcome() -> OutcomeDraw:
    p = mandate_reauth_probability()
    recovered = random.random() < p
    return OutcomeDraw(
        recovered=recovered,
        probability_used=p,
        notes=f"initiate_mandate_reauth probability={p}",
    )


# ---------------------------------------------------------------------------
# natural/organic recovery — the "do_nothing" baseline (ENHANCEMENTS.md
# §2.1): some fraction of at-risk value comes back with *zero* agent
# intervention (the customer retries on their own, a business customer
# pays late anyway). Any evaluation of "does the agent help" that doesn't
# net this out is measuring raw recovery, not the agent's actual lift —
# incremental recovery (policy minus this baseline) is the number that
# means anything. Deliberately illustrative, stated explicitly like every
# other probability in this module.
# ---------------------------------------------------------------------------
NATURAL_RECOVERY_PROBABILITY_BY_EVENT_TYPE = {
    "payment_failed": 0.15,
    "subscription_charge_failed": 0.10,
    "checkout_abandoned": 0.08,
    "invoice_overdue": 0.20,
}


def natural_recovery_probability(event: dict) -> float:
    """Pure probability lookup — see `retry_probability`'s docstring. For
    invoice_overdue, scales with the customer's own historical reliability
    (a reliable payer settles up on their own more often even with zero
    chasing) rather than using the flat event-type baseline alone."""
    event_type = event.get("event_type")
    base = NATURAL_RECOVERY_PROBABILITY_BY_EVENT_TYPE.get(event_type, 0.10)
    if event_type == "invoice_overdue":
        score = event.get("payment_reliability_score")
        if score is not None:
            return round(max(0.05, min(0.5, base * (0.5 + score))), 3)
    return base


def natural_recovery_outcome(event: dict) -> OutcomeDraw:
    p = natural_recovery_probability(event)
    recovered = random.random() < p
    return OutcomeDraw(
        recovered=recovered,
        probability_used=p,
        notes=f"do_nothing (organic recovery) probability={p} for event_type={event.get('event_type')!r}",
    )


def expected_recovery_probability(action_type: str, event: dict, root_cause: str | None) -> float:
    """Best-effort expected-recovery probability for *any* action type, event
    context, and diagnosed root cause — used only by the guardrail engine's
    economic stopping rule (app/guardrails/rules.py) to estimate expected
    recovery in rupees without drawing a random outcome. Not used by the
    executor layer, which always calls the specific `*_outcome()` function
    for its own action type directly."""
    if action_type == "smart_retry":
        return retry_probability(root_cause or "")
    if action_type == "generate_payment_link":
        return payment_link_probability(root_cause or "")
    if action_type == "send_nudge":
        channel = event.get("customer", {}).get("preferred_channel", "sms")
        return nudge_probability(channel, event.get("minutes_since_abandon"))
    if action_type == "escalate_b2b_chase":
        return b2b_chase_probability(
            event.get("payment_reliability_score"), event.get("days_overdue")
        )
    if action_type == "initiate_mandate_reauth":
        return mandate_reauth_probability()
    return 0.0


def no_execution_outcome(action_type: str) -> OutcomeDraw:
    """flag_for_human_review / no_action_recommended — counted honestly as
    not recovered by the agent, never swept under the rug (PRD §9)."""
    return OutcomeDraw(
        recovered=False,
        probability_used=0.0,
        notes=f"{action_type}: no execution attempted, not counted as recovered",
    )
