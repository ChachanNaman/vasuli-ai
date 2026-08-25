"""The batch pipeline: generate -> guardrail-check the LLM's proposed action
-> execute (if cleared) -> write decision.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from app.agents.diagnosis_agent import DiagnosisValidationError, diagnose
from app.agents.heuristic_agent import diagnose_heuristic
from app.agents.llm_client import LLMClientError
from app.api import batch_state
from app.audit.logger import DecisionRecord, write_decision, write_event, write_llm_fallback_event
from app.audit.supabase_client import get_supabase
from app.data.generator import generate_batch
from app.guardrails.rules import PastDecision, run_guardrails
from app.recovery.executors import execute

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

    def on_fallback(reason: str, from_provider: str) -> None:
        write_llm_fallback_event(event_dict["event_id"], reason, from_provider)

    try:
        diagnosis = diagnose(event_dict, on_fallback=on_fallback)
    except (DiagnosisValidationError, LLMClientError) as e:
        # Three-way degradation (ENHANCEMENTS.md §2.5): Groq -> Gemini ->
        # heuristic. Only if *both* LLM providers fail do we drop to the
        # deterministic rule-based agent — never a hard failure, never a
        # silent no-op.
        logger.warning(
            "both LLM providers failed for %s, falling back to heuristic agent: %s",
            event_dict["event_id"],
            e,
        )
        write_llm_fallback_event(event_dict["event_id"], str(e), "gemini")
        diagnosis = diagnose_heuristic(event_dict)

    root_cause = diagnosis.root_cause
    confidence = diagnosis.confidence
    reasoning_text = diagnosis.reasoning
    action_params = diagnosis.action_params
    customer_message = diagnosis.customer_message
    llm_provider = diagnosis.llm_provider
    llm_fallback_used = diagnosis.llm_fallback_used
    proposed_action = diagnosis.recommended_action

    guardrail_result = run_guardrails(
        event_dict,
        proposed_action,
        past_decisions,
        root_cause=root_cause,
        action_params=action_params,
    )

    action_type = proposed_action

    if guardrail_result.action_status == "executed":
        result = execute(action_type, event_dict, root_cause)
        recovered = result.recovered
        amount_recovered = result.amount_recovered
        outcome_notes = result.notes
        razorpay_payment_link = result.razorpay_payment_link
        is_live_integration = result.is_live_integration
    else:
        recovered = False
        amount_recovered = 0.0
        outcome_notes = guardrail_result.block_reason
        razorpay_payment_link = None
        is_live_integration = False

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
        razorpay_payment_link=razorpay_payment_link,
        is_live_integration=is_live_integration,
        llm_provider=llm_provider,
        llm_fallback_used=llm_fallback_used,
        customer_message=customer_message,
    )
    return write_decision(record)


# Spacing between LLM calls. Groq's free tier is ~8000 tokens/minute and a
# diagnosis call uses roughly 1500-2000 tokens, so back-to-back calls burn
# through that budget in 4-5 requests and the rest of the batch falls back
# to Gemini (or, if that's also saturated, to an honest "both providers
# failed" human-review routing). Kept small rather than zero purely to
# smooth out bursts — the three-way degradation (Groq -> Gemini ->
# heuristic) is what actually absorbs rate limiting, not this delay, so
# there's no correctness reason to make it large. A 12-event demo batch at
# the old 2.5s spent 27.5s just sleeping, on top of real LLM latency.
LLM_CALL_SPACING_SECONDS = 0.5


def run_batch(
    n: int = 20, seed: Optional[int] = None, batch_id: Optional[str] = None
) -> list[dict]:
    """Generate `n` events and process them one at a time.

    `batch_id` is optional and only used by `start_batch` below (the
    pause/resume kill switch, FEATURES.md #2) — every existing caller that
    doesn't pass it (including the synchronous tests) runs exactly as
    before.
    """
    state = batch_state.get(batch_id) if batch_id else None
    events = generate_batch(n, seed=seed)
    if state:
        state.total = len(events)

    decisions = []
    for i, event in enumerate(events):
        if state:
            # Checked at an event boundary, before starting the next one —
            # never mid-decision. An already-in-flight diagnose/guardrail/
            # execute sequence always runs to completion.
            batch_state.wait_if_paused(state)
        if i > 0:
            time.sleep(LLM_CALL_SPACING_SECONDS)
        row = _event_to_row(event)
        write_event(row)
        decision = process_event(row["payload"])
        decisions.append(decision)
        if state:
            state.decisions.append(decision)
            state.processed = i + 1
    if state:
        state.status = "completed"
    return decisions


def start_batch(n: int = 20, seed: Optional[int] = None) -> str:
    """Kick off a batch run on a background thread and return its batch_id
    immediately, so the pause/resume endpoints can act on it while it's
    still in progress (FEATURES.md #2). FastAPI already runs sync route
    handlers in a thread pool, so a separate pause/resume POST reaches this
    thread's `batch_state` entry concurrently without extra plumbing."""
    state = batch_state.create(n, seed)

    def _worker() -> None:
        try:
            run_batch(n=n, seed=seed, batch_id=state.batch_id)
        except Exception as exc:  # pragma: no cover - defensive, logged not swallowed
            logger.exception("batch %s failed", state.batch_id)
            state.status = "error"
            state.error = str(exc)

    threading.Thread(target=_worker, daemon=True).start()
    return state.batch_id
