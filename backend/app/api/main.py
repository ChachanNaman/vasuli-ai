"""FastAPI app: run-batch, get-events, get-decisions, get-metrics (PRD §13).

Run locally with: uvicorn app.api.main:app --reload
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Repo-root .env (backend/app/api/main.py -> backend/app/api -> backend/app -> backend -> repo root),
# loaded before any app import so module-level `os.environ.get(...)` reads (e.g. llm_client's
# GROQ_MODEL/GEMINI_MODEL) see it. No-op if the file doesn't exist — deployed environments (Render)
# set real env vars directly instead of shipping a .env.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agents.prompts import ALLOWED_ACTIONS
from app.api import batch_state
from app.api.pipeline import _fetch_past_decisions, start_batch
from app.audit.metrics import (
    get_cash_flow_metrics,
    get_exceptions,
    get_metrics_by_root_cause,
    get_metrics_overview,
)
from app.audit.supabase_client import get_supabase
from app.audit.verify import verify_chain
from app.eval.fairness import run_fairness_check
from app.eval.run_comparison import build_report
from app.guardrails.rules import run_guardrails
from app.recovery.outcome_model import expected_recovery_probability

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Vasuli — AI Revenue Recovery Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # single-merchant demo, no auth (PRD §3.2)
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunBatchRequest(BaseModel):
    n: int = 20
    seed: Optional[int] = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/run-batch")
def api_run_batch(req: RunBatchRequest):
    """Starts the batch on a background thread and returns immediately
    with a batch_id (FEATURES.md #2 — pause/resume needs a live, in-flight
    batch to act on; a request that blocks until the whole batch finishes
    can't be paused from another request). Poll
    GET /api/batches/{batch_id}/status for progress; individual decisions
    still stream in over the existing Supabase Realtime channel as each
    one is written."""
    if req.n < 1 or req.n > 200:
        raise HTTPException(400, "n must be between 1 and 200")
    batch_id = start_batch(n=req.n, seed=req.seed)
    return {"batch_id": batch_id, "n": req.n}


@app.get("/api/batches/{batch_id}/status")
def api_batch_status(batch_id: str):
    state = batch_state.get(batch_id)
    if state is None:
        raise HTTPException(404, "unknown batch_id")
    return batch_state.to_status_dict(state)


@app.post("/api/batches/{batch_id}/pause")
def api_batch_pause(batch_id: str):
    state = batch_state.pause(batch_id)
    if state is None:
        raise HTTPException(404, "unknown batch_id")
    return batch_state.to_status_dict(state)


@app.post("/api/batches/{batch_id}/resume")
def api_batch_resume(batch_id: str):
    state = batch_state.resume(batch_id)
    if state is None:
        raise HTTPException(404, "unknown batch_id")
    return batch_state.to_status_dict(state)


@app.get("/api/events")
def api_get_events(limit: int = Query(50, le=500)):
    supabase = get_supabase()
    response = (
        supabase.table("events").select("*").order("timestamp", desc=True).limit(limit).execute()
    )
    return response.data or []


@app.get("/api/decisions")
def api_get_decisions(limit: int = Query(50, le=500)):
    supabase = get_supabase()
    response = (
        supabase.table("decisions")
        .select("*")
        .order("timestamp", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


@app.get("/api/decisions/{event_id}")
def api_get_decision_for_event(event_id: str):
    supabase = get_supabase()
    response = supabase.table("decisions").select("*").eq("event_id", event_id).execute()
    if not response.data:
        raise HTTPException(404, "no decision found for this event_id")
    return response.data


@app.get("/api/customers/{customer_id}/timeline")
def api_customer_timeline(customer_id: str):
    """FEATURES.md #4: one customer's full recovery journey — every decision
    on record for them, oldest first, with the event_type each one belongs
    to so the frontend can render `payment_failed -> nudge sent -> ...`
    without a second round trip per step."""
    supabase = get_supabase()
    decisions_response = (
        supabase.table("decisions")
        .select("*")
        .eq("customer_id", customer_id)
        .order("timestamp")
        .execute()
    )
    decisions = decisions_response.data or []
    if not decisions:
        raise HTTPException(404, "no decisions found for this customer_id")

    events_response = (
        supabase.table("events")
        .select("event_id, event_type, amount, currency, customer")
        .eq("customer_id", customer_id)
        .execute()
    )
    events_by_id = {e["event_id"]: e for e in (events_response.data or [])}

    customer_context = next(iter(events_by_id.values()))["customer"] if events_by_id else None

    steps = []
    for d in decisions:
        event = events_by_id.get(d["event_id"])
        steps.append(
            {
                **d,
                "event_type": event["event_type"] if event else None,
                "event_amount": event["amount"] if event else None,
                "event_currency": event["currency"] if event else None,
            }
        )

    return {"customer_id": customer_id, "customer": customer_context, "steps": steps}


class CounterfactualRequest(BaseModel):
    action: str


@app.post("/api/events/{event_id}/counterfactual")
def api_counterfactual(event_id: str, req: CounterfactualRequest):
    """FEATURES.md #5: run a judge-selected action through the *real*
    guardrail engine and outcome model for this event's actual state — no
    duplicated business logic, and never a real Razorpay call. If the
    action clears guardrails, the "recovery probability" comes from
    `expected_recovery_probability`, the same deterministic lookup the
    guardrail engine's own economic-stopping-rule check uses to estimate
    expected value — it's a probability lookup, not a random draw, so
    this endpoint is side-effect-free and can be called repeatedly."""
    if req.action not in ALLOWED_ACTIONS:
        raise HTTPException(400, f"action must be one of {sorted(ALLOWED_ACTIONS)}")

    supabase = get_supabase()
    event_response = supabase.table("events").select("*").eq("event_id", event_id).execute()
    if not event_response.data:
        raise HTTPException(404, "unknown event_id")
    event_row = event_response.data[0]
    event_payload = event_row.get("payload") or event_row

    decision_response = (
        supabase.table("decisions")
        .select("root_cause")
        .eq("event_id", event_id)
        .order("timestamp", desc=True)
        .limit(1)
        .execute()
    )
    root_cause = (
        decision_response.data[0]["root_cause"]
        if decision_response.data
        else event_payload.get("failure_reason_code")
    )

    customer_id = event_row.get("customer_id") or event_payload.get("customer", {}).get(
        "customer_id"
    )
    past_decisions = _fetch_past_decisions(customer_id) if customer_id else []

    guardrail_result = run_guardrails(
        event_payload, req.action, past_decisions, root_cause=root_cause
    )

    response: dict = {
        "event_id": event_id,
        "action": req.action,
        "root_cause_used": root_cause,
        "simulated": True,
        "checks": [c.to_dict() for c in guardrail_result.checks],
        "action_status": guardrail_result.action_status,
        "block_reason": guardrail_result.block_reason,
        "simulated_recovery_probability": None,
        "simulated_expected_recovery_amount": None,
    }

    if guardrail_result.action_status == "executed":
        probability = expected_recovery_probability(req.action, event_payload, root_cause)
        amount = event_payload.get("amount") or event_payload.get("cart_value") or 0.0
        response["simulated_recovery_probability"] = probability
        response["simulated_expected_recovery_amount"] = round(amount * probability, 2)

    return response


@app.get("/api/eval/fairness")
def api_eval_fairness():
    """FEATURES.md #6: fairness/consistency check over every decision on
    record — does action *assignment* differ across customer segments that
    shouldn't matter? Reported honestly either way, see
    app/eval/fairness.py."""
    return run_fairness_check()


@app.get("/api/metrics")
def api_get_metrics():
    return {
        "overview": get_metrics_overview(),
        "by_root_cause": get_metrics_by_root_cause(),
        "exceptions": get_exceptions(),
        "cash_flow": get_cash_flow_metrics(),
    }


@app.get("/api/audit/verify")
def api_audit_verify():
    """ENHANCEMENTS.md §2.4/§2.5 dashboard indicator: walks the hash chain
    and reports whether every decision on record is provably unaltered."""
    ok, records_checked, error = verify_chain()
    return {"ok": ok, "records_checked": records_checked, "error": error}


@app.get("/api/eval/comparison")
def api_eval_comparison(
    cases: int = Query(300, ge=10, le=2000), seed: int = Query(42)
):
    """ENHANCEMENTS.md §2.1: the baseline-comparison evaluation harness,
    on demand. Pure Python, no LLM/DB calls, so this is fast even at the
    upper end of the case range (500 cases runs in well under a second)."""
    return build_report(n_cases=cases, seed=seed)
