"""Reads the computed-on-read metrics views (PRD §6.3, supabase/migrations/0001_init.sql).
No aggregation logic lives here — it's all in the SQL views, this just fetches.
"""

from __future__ import annotations

from app.audit.supabase_client import get_supabase


def get_metrics_overview() -> dict:
    supabase = get_supabase()
    response = supabase.table("metrics_overview").select("*").execute()
    return response.data[0] if response.data else {}


def get_metrics_by_root_cause() -> list[dict]:
    supabase = get_supabase()
    response = supabase.table("metrics_by_root_cause").select("*").execute()
    return response.data or []


def get_exceptions() -> list[dict]:
    supabase = get_supabase()
    response = supabase.table("metrics_exceptions").select("*").execute()
    return response.data or []


# ---------------------------------------------------------------------------
# Cash-flow-language framing (FEATURES.md #3). Same numbers already in
# metrics_overview, restated in terms a merchant CFO or ops lead would
# actually use. No schema changes — this reads the raw `decisions`/`events`
# tables directly (not a SQL view) and does the grouping in Python.
# ---------------------------------------------------------------------------

# Illustrative constant, not a real merchant's figure — we have no revenue
# data for the demo merchant, so this is stated explicitly (same
# transparency convention as ECONOMIC_MULTIPLIER in guardrails/rules.py and
# the outcome-model probabilities): a mid-sized Indian SME merchant on
# Razorpay doing roughly this much GMV/day.
AVERAGE_DAILY_REVENUE_INR = 800_000


def get_cash_flow_metrics() -> dict:
    """Derived-metrics-only — no new tables, no new columns. Computes:

    - days_of_reduced_receivables: total recovered / assumed avg daily
      revenue, i.e. "recovering this much money is worth about N days of
      receivables to the business".
    - pct_at_risk_mrr_prevented: for subscription_charge_failed events
      specifically, (amount recovered) / (amount at risk in the batch) —
      "prevented an estimated N% of at-risk MRR from churning".

    Both are None when there's no data yet to divide by, rather than a
    misleading 0%.
    """
    supabase = get_supabase()
    decisions = (
        supabase.table("decisions")
        .select("event_id, recovered, amount_recovered")
        .execute()
        .data
        or []
    )
    events = (
        supabase.table("events").select("event_id, event_type, amount").execute().data or []
    )
    event_by_id = {e["event_id"]: e for e in events}

    total_recovered = sum(d["amount_recovered"] for d in decisions if d.get("recovered"))
    days_of_reduced_receivables = (
        round(total_recovered / AVERAGE_DAILY_REVENUE_INR, 1)
        if AVERAGE_DAILY_REVENUE_INR
        else None
    )

    subscription_at_risk = 0.0
    subscription_recovered = 0.0
    for d in decisions:
        event = event_by_id.get(d["event_id"])
        if event is None or event.get("event_type") != "subscription_charge_failed":
            continue
        subscription_at_risk += event.get("amount") or 0.0
        if d.get("recovered"):
            subscription_recovered += d["amount_recovered"]

    pct_at_risk_mrr_prevented = (
        round(subscription_recovered / subscription_at_risk * 100, 1)
        if subscription_at_risk
        else None
    )

    return {
        "average_daily_revenue_assumed": AVERAGE_DAILY_REVENUE_INR,
        "days_of_reduced_receivables": days_of_reduced_receivables,
        "subscription_mrr_at_risk": subscription_at_risk,
        "subscription_mrr_recovered": subscription_recovered,
        "pct_at_risk_mrr_prevented": pct_at_risk_mrr_prevented,
    }
