"""Recovery execution layer (PRD §9). Dispatches an already-guardrail-cleared
action to its executor, which produces an `ExecutionResult` — a probabilistic
outcome via app/recovery/outcome_model.py, plus a real Razorpay link for
smart_retry / generate_payment_link.

This module never decides *whether* to execute — that's already been
decided by the guardrail engine before this is called. It only decides
*what happens* once an action is cleared to run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.guardrails.rules import DLT_APPROVED_TEMPLATES
from app.recovery import outcome_model
from app.recovery.razorpay_client import create_payment_link


def _fill_dlt_template(action_type: str, event: dict, **extra: object) -> str:
    """Format a fixed, pre-registered DLT template rather than sending the
    LLM's freeform draft directly (TRAI DLT compliance, ENHANCEMENTS.md
    §2.2 — guardrails.check_dlt_template_compliance is what asserts this
    template set exists; this is where it's actually used). Picks the
    customer's language preference where a matching template exists,
    otherwise the first template in the set."""
    templates = DLT_APPROVED_TEMPLATES.get(action_type)
    if not templates:
        return ""

    customer = event.get("customer", {})
    language_pref = customer.get("language_pref", "english")
    template = templates[1] if (language_pref == "hinglish" and len(templates) > 1) else templates[0]

    fields = {
        "name": customer.get("name", "Customer"),
        "amount": f"{event.get('amount', 0):,.2f}",
        "link": "<generated at send time>",
        "invoice_id": event.get("invoice_id", ""),
        "days_overdue": event.get("days_overdue", ""),
        "plan_name": event.get("plan_name", ""),
    }
    fields.update(extra)
    try:
        return template.format(**fields)
    except KeyError:
        return template


@dataclass
class ExecutionResult:
    recovered: bool
    amount_recovered: float
    notes: str
    razorpay_payment_link: Optional[str]
    is_live_integration: bool


def _execute_smart_retry(event: dict, root_cause: str) -> ExecutionResult:
    draw = outcome_model.smart_retry_outcome(root_cause)
    link_result = create_payment_link(
        amount=event["amount"],
        currency=event.get("currency", "INR"),
        customer_name=event["customer"]["name"],
        customer_contact=None,
        description=f"Vasuli smart retry — {event['event_id']}",
        reference_id=f"retry_{event['event_id']}",
    )
    amount_recovered = event["amount"] if draw.recovered else 0.0
    return ExecutionResult(
        recovered=draw.recovered,
        amount_recovered=amount_recovered,
        notes=draw.notes,
        razorpay_payment_link=link_result.url,
        is_live_integration=link_result.is_live,
    )


def _execute_generate_payment_link(event: dict, root_cause: str) -> ExecutionResult:
    draw = outcome_model.generate_payment_link_outcome(root_cause)
    link_result = create_payment_link(
        amount=event["amount"],
        currency=event.get("currency", "INR"),
        customer_name=event["customer"]["name"],
        customer_contact=None,
        description=f"Vasuli payment link — {event['event_id']}",
        reference_id=f"link_{event['event_id']}",
    )
    amount_recovered = event["amount"] if draw.recovered else 0.0
    return ExecutionResult(
        recovered=draw.recovered,
        amount_recovered=amount_recovered,
        notes=draw.notes,
        razorpay_payment_link=link_result.url,
        is_live_integration=link_result.is_live,
    )


def _execute_send_nudge(event: dict) -> ExecutionResult:
    channel = event["customer"].get("preferred_channel", "sms")
    minutes_since_abandon = event.get("minutes_since_abandon")
    draw = outcome_model.send_nudge_outcome(channel, minutes_since_abandon)
    amount = event.get("amount") or event.get("cart_value") or 0.0
    amount_recovered = amount if draw.recovered else 0.0
    message = _fill_dlt_template("send_nudge", event)
    return ExecutionResult(
        recovered=draw.recovered,
        amount_recovered=amount_recovered,
        notes=f"{draw.notes} | sent (DLT template): {message}",
        razorpay_payment_link=None,
        is_live_integration=False,
    )


def _execute_escalate_b2b_chase(event: dict) -> ExecutionResult:
    draw = outcome_model.escalate_b2b_chase_outcome(
        event.get("payment_reliability_score"), event.get("days_overdue")
    )
    amount_recovered = event["amount"] if draw.recovered else 0.0
    message = _fill_dlt_template("escalate_b2b_chase", event)
    return ExecutionResult(
        recovered=draw.recovered,
        amount_recovered=amount_recovered,
        notes=f"{draw.notes} | sent (DLT template): {message}",
        razorpay_payment_link=None,
        is_live_integration=False,
    )


def _execute_initiate_mandate_reauth(event: dict) -> ExecutionResult:
    draw = outcome_model.initiate_mandate_reauth_outcome()
    amount_recovered = event["amount"] if draw.recovered else 0.0
    message = _fill_dlt_template("initiate_mandate_reauth", event)
    return ExecutionResult(
        recovered=draw.recovered,
        amount_recovered=amount_recovered,
        notes=f"{draw.notes} | sent (DLT template): {message}",
        razorpay_payment_link=None,
        is_live_integration=False,
    )


def _execute_no_action(action_type: str) -> ExecutionResult:
    draw = outcome_model.no_execution_outcome(action_type)
    return ExecutionResult(
        recovered=False,
        amount_recovered=0.0,
        notes=draw.notes,
        razorpay_payment_link=None,
        is_live_integration=False,
    )


def execute(action_type: str, event: dict, root_cause: str) -> ExecutionResult:
    """Run the executor for one guardrail-cleared action."""
    if action_type == "smart_retry":
        return _execute_smart_retry(event, root_cause)
    if action_type == "generate_payment_link":
        return _execute_generate_payment_link(event, root_cause)
    if action_type == "send_nudge":
        return _execute_send_nudge(event)
    if action_type == "escalate_b2b_chase":
        return _execute_escalate_b2b_chase(event)
    if action_type == "initiate_mandate_reauth":
        return _execute_initiate_mandate_reauth(event)
    # flag_for_human_review, no_action_recommended, and anything blocked
    # upstream by the guardrail engine never reach an executor with intent
    # to act — treat unrecognized/no-op types the same honest way.
    return _execute_no_action(action_type)
