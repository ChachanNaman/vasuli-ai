"""The batch pipeline: generate -> guardrail-check the LLM's proposed action
-> (Day 2: execute) -> write decision. This is the thing Day 1 task 4 asks
to prove end-to-end.

Execution (Recovery executors + outcome probability model, PRD §9) is a Day
2 module (app/recovery/) — for now, an action that clears guardrails is
recorded as 'executed' with a placeholder outcome so the full pipeline shape
is provable before the outcome model exists.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from app.agents.diagnosis_agent import DiagnosisValidationError, diagnose
from app.agents.llm_client import LLMClientError
from app.audit.logger import DecisionRecord, write_decision, write_event, write_llm_fallback_event
from app.audit.supabase_client import get_supabase
from app.data.generator import generate_batch
from app.guardrails.rules import PastDecision, run_guardrails

logger = logging.getLogger("vasuli.pipeline")


def _event_to_row(event) -> dict:
    d = event.to_dict()
    return {
        "event_id": d["event_id"],
        "event_type": d["event_type"],
        "timestamp": d["timestamp"],
        "merchant_id": d["merchant_id"],
        "amount": d["amount"],
        "currency": d["currency"],
        "customer_id": d["customer"]["customer_id"],
        "customer": d["customer"],
        "payload": d,
    }


def _fetch_past_decisions(customer_id: str) -> list[PastDecision]:
    supabase = get_supabase()
    response = (
        supabase.table("decisions")
        .select("event_id, customer_id, timestamp, action_type, action_status")
        .eq("customer_id", customer_id)
        .order("timestamp", desc=True)
        .limit(50)
        .execute()
    )
    out = []
    for row in response.data or []:
        ts = row["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        out.append(
            PastDecision(
                event_id=row["event_id"],
                customer_id=row["customer_id"],
                timestamp=ts,
                action_type=row["action_type"],
                action_status=row["action_status"],
            )
        )
    return out


def process_event(event_dict: dict) -> dict:
    """Diagnose -> guardrail-check -> write one decision. Returns the row."""
    customer_id = event_dict["customer"]["customer_id"]
    past_decisions = _fetch_past_decisions(customer_id)

    fallback_reason: Optional[str] = None

    def on_fallback(reason: str, from_provider: str) -> None:
        nonlocal fallback_reason
        fallback_reason = reason
        write_llm_fallback_event(event_dict["event_id"], reason, from_provider)

    try:
        diagnosis = diagnose(event_dict, on_fallback=on_fallback)
        proposed_action = diagnosis.recommended_action
    except (DiagnosisValidationError, LLMClientError) as e:
        logger.error("diagnosis failed for %s, flagging for human review: %s", event_dict["event_id"], e)
        proposed_action = "flag_for_human_review"
        diagnosis = None

    guardrail_result = run_guardrails(event_dict, proposed_action, past_decisions)

    if diagnosis is None:
        root_cause = event_dict.get("failure_reason_code", "unknown")
        confidence = 0.0
        reasoning_text = f"Diagnosis agent unavailable (both LLM providers failed): routed to human review."
        action_params: dict = {}
        customer_message = None
        llm_provider = None
        llm_fallback_used = fallback_reason is not None
    else:
        root_cause = diagnosis.root_cause
        confidence = diagnosis.confidence
        reasoning_text = diagnosis.reasoning
        action_params = diagnosis.action_params
        customer_message = diagnosis.customer_message
        llm_provider = diagnosis.llm_provider
        llm_fallback_used = diagnosis.llm_fallback_used

    action_type = proposed_action

    # Day 2 will replace this with app/recovery/executors.py + outcome_model.py.
    recovered = False
    amount_recovered = 0.0
    outcome_notes = (
        "Recovery execution not yet implemented (Day 2)."
        if guardrail_result.action_status == "executed"
        else guardrail_result.block_reason
    )

    record = DecisionRecord(
        event_id=event_dict["event_id"],
        customer_id=customer_id,
        root_cause=root_cause,
        confidence=confidence,
        reasoning_text=reasoning_text,
        guardrail_result=guardrail_result,
        action_type=action_type,
        action_params=action_params,
        recovered=recovered,
        amount_recovered=amount_recovered,
        outcome_notes=outcome_notes,
        razorpay_payment_link=None,
        is_live_integration=False,
        llm_provider=llm_provider,
        llm_fallback_used=llm_fallback_used,
        customer_message=customer_message,
    )
    return write_decision(record)


def run_batch(n: int = 20, seed: Optional[int] = None) -> list[dict]:
    events = generate_batch(n, seed=seed)
    decisions = []
    for event in events:
        row = _event_to_row(event)
        write_event(row)
        decisions.append(process_event(row["payload"]))
    return decisions
