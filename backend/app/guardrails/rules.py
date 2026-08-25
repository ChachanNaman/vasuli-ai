"""
Deterministic guardrail engine (PRD §7). No LLM involved anywhere in this
module — every function here is pure and unit-testable in isolation.

This runs *after* the diagnosis agent proposes an action but *before* the
recovery executor is allowed to touch anything. The agent cannot argue its
way past these checks; that separation is the whole "AI judgment" answer
(PRD §5).

Design note: guardrails don't query the database themselves. They're pure
functions of (event, proposed action, customer's recent decision history,
now) so they stay trivially testable. The caller (the batch pipeline) is
responsible for fetching that history from Supabase and passing it in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.recovery import cost_model
from app.recovery.outcome_model import expected_recovery_probability

# Actions that involve contacting the customer at all (comms channel, or a
# link handed to them to act on). smart_retry is silent — no customer
# contact — so it's excluded here on purpose.
CONTACT_ACTIONS = {
    "generate_payment_link",
    "send_nudge",
    "escalate_b2b_chase",
    "initiate_mandate_reauth",
}

RETRY_ACTIONS = {"smart_retry"}

# Actions that touch a live subscription mandate directly — a silent retry
# or re-auth against an active mandate is exactly what the e-mandate
# pre-debit notice rule below gates (ENHANCEMENTS.md §2.2).
MANDATE_TOUCHING_ACTIONS = {"smart_retry", "initiate_mandate_reauth"}

COOL_DOWN_WINDOW = timedelta(hours=4)
DAILY_CONTACT_CAP = 2
DAILY_CONTACT_WINDOW = timedelta(hours=24)
RETRY_RATE_LIMIT_WINDOW = timedelta(minutes=30)
INVOICE_AUTO_ESCALATE_CAP = 100_000
RELIABILITY_FIRM_THRESHOLD = 0.3
RELIABILITY_SOFT_THRESHOLD = 0.7

# RBI recovery-agent guidelines restrict borrower contact to roughly this
# window (ENHANCEMENTS.md §2.2). India Standard Time, not the server's
# local time or UTC — a merchant's customers are (in this demo) assumed to
# be in India regardless of where the backend happens to run.
IST = timezone(timedelta(hours=5, minutes=30))
CONTACT_WINDOW_START_HOUR = 8
CONTACT_WINDOW_END_HOUR = 19

# RBI's e-mandate/recurring-payment framework requires prior notification
# before an auto-debit, on a set notice period. We don't state the current
# rupee-threshold/notice-period figure from memory (ENHANCEMENTS.md §2.2
# explicitly warns that figure has changed in 2026 rule updates) — this is
# our own conservative operating minimum, not a claimed regulatory number.
MANDATE_PRE_DEBIT_NOTICE_MIN_HOURS = 24

# TRAI mandates all commercial SMS/WhatsApp content be pre-registered on the
# DLT platform — never freeform LLM-generated text sent directly, even
# though the LLM drafts a customer_message for the reasoning trace (PRD
# §8.1). The executor is responsible for actually substituting one of these
# templates rather than the LLM's raw text; this table is the single
# source of truth both the executor and this guardrail check read from.
DLT_APPROVED_TEMPLATES: dict[str, list[str]] = {
    "send_nudge": [
        "Hi {name}, your payment of ₹{amount} didn't go through. Complete it "
        "here: {link}",
        "{name}, aapka ₹{amount} ka payment complete nahi hua. Yahan complete "
        "karein: {link}",
    ],
    "escalate_b2b_chase": [
        "Dear {name}, invoice {invoice_id} of ₹{amount} is {days_overdue} days "
        "overdue. Please arrange payment at your earliest convenience.",
    ],
    "initiate_mandate_reauth": [
        "Hi {name}, your payment mandate needs re-authorization to continue "
        "your {plan_name} subscription: {link}",
    ],
}

# Economic stopping rule (ENHANCEMENTS.md §2.3): force no_action_recommended
# whenever expected_recovery < ECONOMIC_MULTIPLIER * (action_cost +
# nuisance_cost). 3x is a deliberately conservative illustrative multiplier,
# not a derived figure — stated explicitly so it can be argued with.
ECONOMIC_MULTIPLIER = 3


@dataclass
class GuardrailCheck:
    rule_name: str
    passed: bool
    detail: str

    def to_dict(self) -> dict:
        return {"rule_name": self.rule_name, "passed": self.passed, "detail": self.detail}


@dataclass
class PastDecision:
    """Minimal shape the guardrail engine needs from a prior decision row."""

    event_id: str
    customer_id: str
    timestamp: datetime
    action_type: str
    action_status: str  # 'executed' | 'blocked_by_guardrail' | 'skipped_opt_out'


def _parse_ts(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


# ---------------------------------------------------------------------------
# Individual rules — each returns a GuardrailCheck. `passed=True` means the
# rule did NOT block the action.
# ---------------------------------------------------------------------------


def check_max_retry_attempts(event: dict) -> GuardrailCheck:
    """Block retry if attempt_number >= 3 for payments, >= 4 for subscriptions.

    Regulatory basis: card network rules cap retry attempts on a declined
    instrument (ENHANCEMENTS.md §2.2)."""
    event_type = event.get("event_type")
    attempt_number = event.get("attempt_number")

    if event_type not in ("payment_failed", "subscription_charge_failed"):
        return GuardrailCheck("max_retry_attempts", True, "not a retryable event type")

    limit = 4 if event_type == "subscription_charge_failed" else 3
    if attempt_number is None:
        return GuardrailCheck("max_retry_attempts", True, "no attempt_number on event")

    if attempt_number >= limit:
        return GuardrailCheck(
            "max_retry_attempts",
            False,
            f"attempt_number={attempt_number} >= limit={limit}; route to human/manual queue",
        )
    return GuardrailCheck(
        "max_retry_attempts", True, f"attempt_number={attempt_number} < limit={limit}"
    )


def check_cool_down_window(
    customer_id: str, now: datetime, past_decisions: list[PastDecision]
) -> GuardrailCheck:
    """No repeat contact to the same customer within 4h of the last attempt.

    Regulatory basis: reasonable-conduct expectation under RBI fair-practice
    codes (ENHANCEMENTS.md §2.2)."""
    contacts = [
        d
        for d in past_decisions
        if d.customer_id == customer_id
        and d.action_type in CONTACT_ACTIONS
        and d.action_status == "executed"
    ]
    if not contacts:
        return GuardrailCheck("cool_down_window", True, "no prior contact on record")

    last = max(contacts, key=lambda d: d.timestamp)
    elapsed = now - last.timestamp
    if elapsed < COOL_DOWN_WINDOW:
        remaining = COOL_DOWN_WINDOW - elapsed
        return GuardrailCheck(
            "cool_down_window",
            False,
            f"last contact {elapsed} ago, cool-down is {COOL_DOWN_WINDOW}; "
            f"{remaining} remaining",
        )
    return GuardrailCheck(
        "cool_down_window", True, f"last contact {elapsed} ago, cool-down window has passed"
    )


def check_daily_contact_cap(
    customer_id: str, now: datetime, past_decisions: list[PastDecision]
) -> GuardrailCheck:
    """Max 2 recovery touches per customer per 24h across all channels.

    Regulatory basis: reasonable-conduct expectation under RBI fair-practice
    codes (ENHANCEMENTS.md §2.2) — same basis as the cool-down window, at a
    longer horizon."""
    window_start = now - DAILY_CONTACT_WINDOW
    contacts_in_window = [
        d
        for d in past_decisions
        if d.customer_id == customer_id
        and d.action_type in CONTACT_ACTIONS
        and d.action_status == "executed"
        and window_start <= d.timestamp <= now
    ]
    count = len(contacts_in_window)
    if count >= DAILY_CONTACT_CAP:
        return GuardrailCheck(
            "daily_contact_cap",
            False,
            f"{count} contacts in trailing 24h, cap is {DAILY_CONTACT_CAP}",
        )
    return GuardrailCheck(
        "daily_contact_cap", True, f"{count} contacts in trailing 24h, cap is {DAILY_CONTACT_CAP}"
    )


def check_opt_out(event: dict, proposed_action: str) -> GuardrailCheck:
    """If customer opted out of recovery comms, no comms action is permitted.

    Regulatory basis: TRAI's DND registry plus our own opt-out flag
    (ENHANCEMENTS.md §2.2 — "now explicitly tied to the regulatory reason,
    not just good practice")."""
    opted_out = bool(event.get("customer", {}).get("opted_out_of_recovery_comms", False))
    if not opted_out:
        return GuardrailCheck("opt_out_enforcement", True, "customer has not opted out")

    if proposed_action in CONTACT_ACTIONS:
        return GuardrailCheck(
            "opt_out_enforcement",
            False,
            "customer opted out of recovery comms; route to excluded bucket",
        )
    return GuardrailCheck(
        "opt_out_enforcement",
        True,
        "customer opted out, but proposed action has no customer contact",
    )


def check_invoice_spend_cap(event: dict, proposed_action: str) -> GuardrailCheck:
    """Invoices over ₹1,00,000 cannot be auto-escalated; human review only.

    This is a policy cap, not a cited regulation — a deliberate internal
    stopping rule for the "compliant escalation" bar (PRD §7)."""
    if event.get("event_type") != "invoice_overdue":
        return GuardrailCheck("invoice_spend_cap", True, "not an invoice event")

    amount = event.get("amount", 0)
    if amount > INVOICE_AUTO_ESCALATE_CAP and proposed_action == "escalate_b2b_chase":
        return GuardrailCheck(
            "invoice_spend_cap",
            False,
            f"invoice amount ₹{amount:,.2f} exceeds ₹{INVOICE_AUTO_ESCALATE_CAP:,} "
            "auto-escalation cap; flag for human review only",
        )
    return GuardrailCheck(
        "invoice_spend_cap", True, f"invoice amount ₹{amount:,.2f} within auto-escalation cap"
    )


def check_promise_to_pay(event: dict, now: datetime) -> GuardrailCheck:
    """A customer's logged commitment to pay by a specific date is a real
    trust relationship — escalating again before that date arrives
    undermines the exact thing the chase sequence exists to preserve, so a
    pending promise defers escalation.

    But a promise that has already passed with no payment is not a reason
    for permanent silence — the opposite: a broken promise is itself a
    stronger signal that this account needs firmer follow-up, not less. So
    this rule only ever defers (block), never permanently blocks — once
    the promised date is in the past, escalation is explicitly allowed to
    proceed. This asymmetry is the whole point of the rule; a rule that
    just paused forever on any promise would let a customer stall
    indefinitely by promising and never paying.

    Policy cap, not a cited regulation — same basis as invoice_spend_cap
    above."""
    if event.get("event_type") != "invoice_overdue":
        return GuardrailCheck("promise_to_pay", True, "not an invoice event")

    promise_date_str = event.get("promise_to_pay_date")
    if not promise_date_str:
        return GuardrailCheck("promise_to_pay", True, "no active payment promise on record")

    promise_date = datetime.fromisoformat(promise_date_str).replace(tzinfo=timezone.utc)
    if now < promise_date:
        remaining = promise_date - now
        return GuardrailCheck(
            "promise_to_pay",
            False,
            f"customer promised to pay by {promise_date_str}, {remaining} remaining; "
            "deferring escalation until the promise date passes",
        )

    overdue_by = now - promise_date
    return GuardrailCheck(
        "promise_to_pay",
        True,
        f"promise to pay by {promise_date_str} was broken {overdue_by} ago; "
        "escalation is warranted, not withheld",
    )


def check_contact_window(proposed_action: str, now: datetime) -> GuardrailCheck:
    """No customer-facing action (call, SMS, WhatsApp, or a link handed to
    them to act on) outside 08:00-19:00 IST; queue until the window opens.

    Regulatory basis: RBI recovery-agent guidelines restrict borrower
    contact to roughly this window (ENHANCEMENTS.md §2.2)."""
    if proposed_action not in CONTACT_ACTIONS:
        return GuardrailCheck("contact_window", True, "action has no customer contact")

    ist_hour = now.astimezone(IST).hour
    if CONTACT_WINDOW_START_HOUR <= ist_hour < CONTACT_WINDOW_END_HOUR:
        return GuardrailCheck(
            "contact_window", True, f"{ist_hour:02d}:00 IST is within the contact window"
        )
    return GuardrailCheck(
        "contact_window",
        False,
        f"{ist_hour:02d}:00 IST is outside the {CONTACT_WINDOW_START_HOUR:02d}:00-"
        f"{CONTACT_WINDOW_END_HOUR:02d}:00 IST RBI recovery-agent contact window; "
        "queue until window opens",
    )


def check_mandate_pre_debit_notice(
    event: dict, proposed_action: str, action_params: Optional[dict]
) -> GuardrailCheck:
    """A retry or re-auth against an *active* mandate must carry a confirmed
    pre-debit notice period; it may never fire as a silent retry.

    Regulatory basis: RBI's e-mandate/recurring-payment framework requires
    prior notification before an auto-debit, on a set notice period
    (ENHANCEMENTS.md §2.2). We deliberately do not cite a specific rupee
    threshold or notice-period figure here — that figure has changed in
    2026 rule updates and we haven't independently verified the current
    revision; `MANDATE_PRE_DEBIT_NOTICE_MIN_HOURS` is our own conservative
    operating minimum, not a claimed regulatory number."""
    if event.get("event_type") != "subscription_charge_failed":
        return GuardrailCheck("mandate_pre_debit_notice", True, "not a subscription event")
    if event.get("mandate_status") != "active":
        return GuardrailCheck(
            "mandate_pre_debit_notice", True, "mandate not active; nothing live to pre-notify"
        )
    if proposed_action not in MANDATE_TOUCHING_ACTIONS:
        return GuardrailCheck(
            "mandate_pre_debit_notice", True, "action does not touch an active mandate"
        )

    notice_hours = (action_params or {}).get("pre_debit_notice_hours")
    if not isinstance(notice_hours, (int, float)) or notice_hours < MANDATE_PRE_DEBIT_NOTICE_MIN_HOURS:
        return GuardrailCheck(
            "mandate_pre_debit_notice",
            False,
            f"no confirmed pre-debit notice >= {MANDATE_PRE_DEBIT_NOTICE_MIN_HOURS}h on an "
            "active mandate; a silent retry/re-auth is not permitted",
        )
    return GuardrailCheck(
        "mandate_pre_debit_notice", True, f"pre-debit notice of {notice_hours}h confirmed"
    )


def check_dlt_template_compliance(proposed_action: str) -> GuardrailCheck:
    """Comms actions must draw their sent message from a small, fixed,
    pre-registered template set — never the LLM's freeform text sent
    directly (the executor substitutes a template; the LLM's own text is
    kept only in the reasoning trace as a draft).

    Regulatory basis: TRAI mandates all commercial SMS/WhatsApp content be
    pre-registered on the DLT platform (ENHANCEMENTS.md §2.2)."""
    templates = DLT_APPROVED_TEMPLATES.get(proposed_action)
    if not templates:
        return GuardrailCheck(
            "dlt_template_compliance", True, "action has no customer-facing message"
        )
    return GuardrailCheck(
        "dlt_template_compliance",
        True,
        f"{len(templates)} DLT-registered template(s) available for {proposed_action}",
    )


def check_dispute_freeze(event: dict) -> GuardrailCheck:
    """Once a payment is disputed/charged back, all further agent action on
    it stops pending resolution — regardless of what action was proposed.

    Regulatory basis / policy: standard chargeback-handling practice — a
    merchant continuing to chase or retry a disputed payment can itself be
    read as an attempt to pressure the customer during an open dispute
    (ENHANCEMENTS.md §2.2)."""
    if event.get("dispute_opened"):
        return GuardrailCheck(
            "dispute_freeze",
            False,
            "payment is under dispute/chargeback; all agent action frozen pending resolution",
        )
    return GuardrailCheck("dispute_freeze", True, "no open dispute on this payment")


def check_economic_stopping_rule(
    event: dict, proposed_action: str, root_cause: Optional[str]
) -> GuardrailCheck:
    """Force no_action_recommended whenever expected recovery is too small
    to justify the action's cost — a retry/nudge that's mathematically not
    worth sending shouldn't be sent just because it's cheap (ENHANCEMENTS.md
    §2.3). `ECONOMIC_MULTIPLIER` and the cost figures in
    app/recovery/cost_model.py are stated explicitly so the number can be
    argued with, exactly like the outcome model's probabilities."""
    if proposed_action in ("flag_for_human_review", "no_action_recommended"):
        return GuardrailCheck(
            "economic_stopping_rule", True, "no execution attempted; economics not applicable"
        )

    probability = expected_recovery_probability(proposed_action, event, root_cause)
    amount = event.get("amount") or event.get("cart_value") or 0.0
    expected_recovery = amount * probability
    threshold = ECONOMIC_MULTIPLIER * cost_model.total_action_cost(proposed_action)

    if expected_recovery < threshold:
        return GuardrailCheck(
            "economic_stopping_rule",
            False,
            f"expected recovery ₹{expected_recovery:,.2f} (amount ₹{amount:,.2f} x "
            f"p={probability}) is below {ECONOMIC_MULTIPLIER}x action cost "
            f"₹{threshold:,.2f}; not worth acting",
        )
    return GuardrailCheck(
        "economic_stopping_rule",
        True,
        f"expected recovery ₹{expected_recovery:,.2f} clears {ECONOMIC_MULTIPLIER}x cost "
        f"₹{threshold:,.2f}",
    )


def check_retry_rate_limit(
    event: dict, now: datetime, past_decisions: list[PastDecision]
) -> GuardrailCheck:
    """No more than 1 retry attempt per payment per 30 minutes.

    This is the rule that prevents the retry-storm failure mode (PRD §11) —
    deliberately removed and reinstated as part of the Day 3 failure story.
    Regulatory basis for the cap itself: card network rules (same basis as
    max_retry_attempts above); this rule adds the *timing* dimension.
    """
    event_id = event.get("event_id")
    recent_retries = [
        d
        for d in past_decisions
        if d.event_id == event_id
        and d.action_type in RETRY_ACTIONS
        and d.action_status == "executed"
        and (now - d.timestamp) < RETRY_RATE_LIMIT_WINDOW
    ]
    if recent_retries:
        last = max(recent_retries, key=lambda d: d.timestamp)
        elapsed = now - last.timestamp
        return GuardrailCheck(
            "retry_rate_limit",
            False,
            f"retried {elapsed} ago for this payment, rate limit is "
            f"{RETRY_RATE_LIMIT_WINDOW}; reason=rate_limited",
        )
    return GuardrailCheck("retry_rate_limit", True, "no retry for this payment in the last 30m")


def check_reliability_floor(event: dict) -> GuardrailCheck:
    """B2B chase tone: score < 0.3 → firmer tier, >= 0.7 → soft reminder only."""
    if event.get("event_type") != "invoice_overdue":
        return GuardrailCheck("reliability_floor", True, "not an invoice event")

    score = event.get("payment_reliability_score")
    if score is None:
        return GuardrailCheck("reliability_floor", True, "no reliability score on event")

    if score < RELIABILITY_FIRM_THRESHOLD:
        tier = "firm"
    elif score >= RELIABILITY_SOFT_THRESHOLD:
        tier = "soft"
    else:
        tier = "standard"
    return GuardrailCheck(
        "reliability_floor", True, f"reliability_score={score} -> chase tier={tier}"
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class GuardrailResult:
    checks: list[GuardrailCheck]
    action_status: str  # 'executed' | 'blocked_by_guardrail' | 'skipped_opt_out'
    block_reason: Optional[str]

    def to_dict(self) -> dict:
        return {
            "checks": [c.to_dict() for c in self.checks],
            "action_status": self.action_status,
            "block_reason": self.block_reason,
        }


def run_guardrails(
    event: dict,
    proposed_action: str,
    past_decisions: list[PastDecision],
    now: Optional[datetime] = None,
    root_cause: Optional[str] = None,
    action_params: Optional[dict] = None,
) -> GuardrailResult:
    """Run every applicable rule and decide the final action_status.

    Every check is run and logged regardless of whether an earlier one
    already failed (PRD §7: "every rule check ... is written to the audit
    trail whether or not it blocked anything").

    `root_cause` and `action_params` are optional and only feed the
    economic stopping rule and the e-mandate pre-debit notice rule
    respectively — every existing caller that doesn't pass them keeps
    working exactly as before (root_cause falls back to the event's own
    `failure_reason_code`; action_params defaults to empty).
    """
    now = now or datetime.now(timezone.utc)
    customer_id = event.get("customer", {}).get("customer_id", "")
    root_cause = root_cause or event.get("failure_reason_code")
    action_params = action_params or {}

    checks = [
        check_max_retry_attempts(event),
        check_cool_down_window(customer_id, now, past_decisions),
        check_daily_contact_cap(customer_id, now, past_decisions),
        check_opt_out(event, proposed_action),
        check_invoice_spend_cap(event, proposed_action),
        check_promise_to_pay(event, now),
        check_retry_rate_limit(event, now, past_decisions),
        check_reliability_floor(event),
        check_contact_window(proposed_action, now),
        check_mandate_pre_debit_notice(event, proposed_action, action_params),
        check_dlt_template_compliance(proposed_action),
        check_dispute_freeze(event),
        check_economic_stopping_rule(event, proposed_action, root_cause),
    ]

    failed = [c for c in checks if not c.passed]

    if not failed:
        return GuardrailResult(checks=checks, action_status="executed", block_reason=None)

    opt_out_failure = next((c for c in failed if c.rule_name == "opt_out_enforcement"), None)
    if opt_out_failure and len(failed) == 1:
        return GuardrailResult(
            checks=checks, action_status="skipped_opt_out", block_reason=opt_out_failure.detail
        )

    return GuardrailResult(
        checks=checks,
        action_status="blocked_by_guardrail",
        block_reason="; ".join(f"{c.rule_name}: {c.detail}" for c in failed),
    )
