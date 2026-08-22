"""Zero-API-key deterministic diagnosis fallback (ENHANCEMENTS.md §2.5).

A small, explicit if/elif rule-based diagnosis function over the same
signals the LLM sees (`failure_reason_code`, `attempt_number`,
`mandate_status`, `payment_reliability_score`, etc.), choosing from the
exact same allowed action set as the LLM agent (PRD §8.2). This gives the
system three things:

1. A true fallback of last resort — if Groq *and* Gemini both fail during
   judging, the pipeline degrades to this instead of failing the batch or
   silently doing nothing.
2. A working zero-API-key demo mode — the whole app can run and produce
   real, structured metrics with no external LLM dependency at all.
3. A basis for an honest LLM-vs-heuristic comparison (see README/
   docs/architecture.md for the result, if run).

This is deliberately *not* a learned model — no training data, no
held-out set, just a small set of readable rules, so its behavior is as
auditable as the guardrail engine's.
"""

from __future__ import annotations

from app.agents.diagnosis_agent import Diagnosis

HEURISTIC_PROVIDER = "heuristic"

_TRANSIENT_REASONS = {"bank_server_down", "network_error", "otp_timeout"}
_DEAD_END_REASONS = {"card_expired", "risk_declined"}


def _diagnose_payment_failed(event: dict) -> tuple[str, str, str, float]:
    """Returns (root_cause, action, reasoning, confidence)."""
    reason = event.get("failure_reason_code") or "unknown"
    attempt = event.get("attempt_number") or 1

    if attempt >= 3:
        return (
            reason,
            "flag_for_human_review",
            f"attempt_number={attempt} has exhausted the retry cap; routing to human "
            "review rather than continuing to guess.",
            0.7,
        )
    if reason in _DEAD_END_REASONS:
        return (
            reason,
            "generate_payment_link",
            f"{reason} rarely recovers via a same-method retry; a fresh payment link "
            "sidesteps the underlying blocker instead.",
            0.7,
        )
    if reason in _TRANSIENT_REASONS or reason == "insufficient_funds":
        return (
            reason,
            "smart_retry",
            f"{reason} is a transient or timing-related failure; a retry is a "
            "reasonable first attempt before escalating.",
            0.6,
        )
    return (
        reason,
        "send_nudge",
        f"No strong automatic-retry signal for {reason}; a reminder nudge is the "
        "safer default over a blind retry.",
        0.5,
    )


def _diagnose_subscription_charge_failed(event: dict) -> tuple[str, str, str, float]:
    reason = event.get("failure_reason_code") or "unknown"
    mandate_status = event.get("mandate_status")
    attempt = event.get("attempt_number") or 1

    if mandate_status in ("expired", "revoked"):
        return (
            reason,
            "initiate_mandate_reauth",
            f"mandate_status={mandate_status}; a retry cannot succeed without a fresh "
            "authorization first.",
            0.75,
        )
    if attempt >= 4:
        return (
            reason,
            "flag_for_human_review",
            f"attempt_number={attempt} has exhausted the subscription retry cap.",
            0.7,
        )
    return (
        reason,
        "smart_retry",
        "Mandate is active and retry attempts remain; a retry with a confirmed "
        "pre-debit notice is appropriate.",
        0.6,
    )


def _diagnose_checkout_abandoned(event: dict) -> tuple[str, str, str, float]:
    stage = event.get("checkout_stage_reached")
    minutes = event.get("minutes_since_abandon") or 0

    if stage == "otp_pending" or minutes < 240:
        return (
            "checkout_abandoned",
            "send_nudge",
            f"Abandoned {minutes} minutes ago at stage={stage!r}; recent enough that a "
            "timely nudge has a real chance of converting.",
            0.55,
        )
    return (
        "checkout_abandoned",
        "no_action_recommended",
        f"Abandoned {minutes} minutes ago; a nudge this stale has low expected value.",
        0.5,
    )


def _diagnose_invoice_overdue(event: dict) -> tuple[str, str, str, float]:
    amount = event.get("amount") or 0
    score = event.get("payment_reliability_score")

    if amount > 100_000:
        return (
            "invoice_overdue",
            "flag_for_human_review",
            f"invoice amount ₹{amount:,.2f} exceeds the auto-escalation cap regardless "
            "of reliability score.",
            0.8,
        )
    tier = "firm" if (score is not None and score < 0.3) else "standard"
    return (
        "invoice_overdue",
        "escalate_b2b_chase",
        f"reliability_score={score} -> {tier} chase tier is appropriate.",
        0.6,
    )


def diagnose_heuristic(event: dict) -> Diagnosis:
    """Deterministic, zero-API-key diagnosis. Never raises — every branch
    resolves to a valid action from the same allowed set the LLM agent uses,
    so this is always a safe drop-in replacement, not just a last resort."""
    if event.get("dispute_opened"):
        return Diagnosis(
            root_cause=event.get("failure_reason_code") or "dispute_opened",
            confidence=0.95,
            reasoning="Payment is under dispute/chargeback; no recovery action should "
            "be taken pending resolution.",
            recommended_action="flag_for_human_review",
            action_params={},
            customer_message=None,
            llm_provider=HEURISTIC_PROVIDER,
            llm_fallback_used=True,
        )

    event_type = event.get("event_type")
    dispatch = {
        "payment_failed": _diagnose_payment_failed,
        "subscription_charge_failed": _diagnose_subscription_charge_failed,
        "checkout_abandoned": _diagnose_checkout_abandoned,
        "invoice_overdue": _diagnose_invoice_overdue,
    }.get(event_type)

    if dispatch is None:
        root_cause, action, reasoning, confidence = (
            "unknown",
            "flag_for_human_review",
            f"Unrecognized event_type={event_type!r}.",
            0.3,
        )
    else:
        root_cause, action, reasoning, confidence = dispatch(event)

    action_params: dict = {}
    if action in ("smart_retry", "initiate_mandate_reauth") and event.get("mandate_status") == "active":
        action_params["pre_debit_notice_hours"] = 24

    customer_message = None
    if action in ("send_nudge", "escalate_b2b_chase", "initiate_mandate_reauth"):
        customer_message = (
            "(heuristic mode: message sent from a fixed DLT-registered template, "
            "not freeform-generated)"
        )

    return Diagnosis(
        root_cause=root_cause,
        confidence=confidence,
        reasoning=reasoning,
        recommended_action=action,
        action_params=action_params,
        customer_message=customer_message,
        llm_provider=HEURISTIC_PROVIDER,
        llm_fallback_used=True,
    )
