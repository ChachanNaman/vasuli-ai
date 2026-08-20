"""FastAPI app: run-batch, get-events, get-decisions, get-metrics (PRD §13).

Run locally with: uvicorn app.api.main:app --reload
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.pipeline import run_batch
from app.audit.metrics import get_exceptions, get_metrics_by_root_cause, get_metrics_overview
from app.audit.supabase_client import get_supabase

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
    if req.n < 1 or req.n > 200:
        raise HTTPException(400, "n must be between 1 and 200")
    decisions = run_batch(n=req.n, seed=req.seed)
    return {"decisions_written": len(decisions), "decisions": decisions}


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


@app.get("/api/metrics")
def api_get_metrics():
    return {
        "overview": get_metrics_overview(),
        "by_root_cause": get_metrics_by_root_cause(),
        "exceptions": get_exceptions(),
    }
