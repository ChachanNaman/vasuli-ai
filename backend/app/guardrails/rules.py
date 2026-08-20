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

COOL_DOWN_WINDOW = timedelta(hours=4)
DAILY_CONTACT_CAP = 2
DAILY_CONTACT_WINDOW = timedelta(hours=24)
RETRY_RATE_LIMIT_WINDOW = timedelta(minutes=30)
INVOICE_AUTO_ESCALATE_CAP = 100_000
RELIABILITY_FIRM_THRESHOLD = 0.3
RELIABILITY_SOFT_THRESHOLD = 0.7


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
    """Block retry if attempt_number >= 3 for payments, >= 4 for subscriptions."""
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
    """No repeat contact to the same customer within 4h of the last attempt."""
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
    """Max 2 recovery touches per customer per 24h across all channels."""
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
    """If customer opted out of recovery comms, no comms action is permitted."""
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
    """Invoices over ₹1,00,000 cannot be auto-escalated; human review only."""
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


def check_retry_rate_limit(
    event: dict, now: datetime, past_decisions: list[PastDecision]
) -> GuardrailCheck:
    """No more than 1 retry attempt per payment per 30 minutes.

    This is the rule that prevents the retry-storm failure mode (PRD §11) —
    deliberately removed and reinstated as part of the Day 3 failure story.
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
) -> GuardrailResult:
    """Run every applicable rule and decide the final action_status.

    Every check is run and logged regardless of whether an earlier one
    already failed (PRD §7: "every rule check ... is written to the audit
    trail whether or not it blocked anything").
    """
    now = now or datetime.now(timezone.utc)
    customer_id = event.get("customer", {}).get("customer_id", "")

    checks = [
        check_max_retry_attempts(event),
        check_cool_down_window(customer_id, now, past_decisions),
        check_daily_contact_cap(customer_id, now, past_decisions),
        check_opt_out(event, proposed_action),
        check_invoice_spend_cap(event, proposed_action),
        check_retry_rate_limit(event, now, past_decisions),
        check_reliability_floor(event),
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
