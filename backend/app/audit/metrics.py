"""Reads the computed-on-read metrics views (PRD §6.3, supabase/migrations/0001_init.sql).
No aggregation logic lives here — it's all in the SQL views, this just fetches.
"""

from __future__ import annotations

from typing import Optional

from app.audit.supabase_client import get_supabase


def get_latest_batch_id() -> Optional[str]:
    """The batch_id of the most recently-written event, or None if the
    table is empty (or predates migration 0005 and every row has a null
    batch_id — in which case there's nothing meaningful to scope to and
    callers should fall back to the unscoped view)."""
    supabase = get_supabase()
    response = (
        supabase.table("events")
        .select("batch_id")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0].get("batch_id") if rows else None


# Superset of columns every metric function below needs, so one fetch of
# the latest batch's events/decisions (see _fetch_latest_batch_data) can
# feed all four of them — each used to independently re-fetch the latest
# batch_id and re-query events/decisions with its own narrower column
# list, which was up to ~10 sequential Supabase round trips for a single
# /api/metrics call. Every field a Fake* test table returns is ignored by
# the real Supabase client's .select() filtering client-side, so widening
# these lists doesn't change what any existing caller sees.
_EVENT_COLUMNS = "event_id, event_type, amount"
_DECISION_COLUMNS = (
    "decision_id, event_id, customer_id, timestamp, root_cause, recovered, "
    "amount_recovered, action_status, action_type, reasoning_text, outcome_notes"
)


def _fetch_latest_batch_data() -> tuple[list[dict], list[dict]]:
    """One round trip for the latest batch_id, then one each for its
    events and decisions — the shared dataset behind get_dashboard_metrics
    below."""
    batch_id = get_latest_batch_id()
    supabase = get_supabase()
    events_query = supabase.table("events").select(_EVENT_COLUMNS)
    decisions_query = supabase.table("decisions").select(_DECISION_COLUMNS)
    if batch_id:
        events_query = events_query.eq("batch_id", batch_id)
        decisions_query = decisions_query.eq("batch_id", batch_id)
    events = events_query.execute().data or []
    decisions = decisions_query.execute().data or []
    return events, decisions


def get_metrics_overview(
    events: Optional[list[dict]] = None, decisions: Optional[list[dict]] = None
) -> dict:
    """Scoped to the latest batch (see supabase/migrations/0005_batch_scoping.sql)
    so the dashboard describes the run that just happened rather than the
    sum of every batch anyone has ever kicked off. Recomputed here in
    Python rather than via the `metrics_overview` SQL view, since that view
    aggregates the whole table with no per-batch filter. Callers that
    already have the latest batch's events/decisions (get_dashboard_metrics)
    pass them in directly instead of triggering another fetch."""
    if events is None or decisions is None:
        events, decisions = _fetch_latest_batch_data()

    total_decisions = len(decisions)
    recovered_count = sum(1 for d in decisions if d.get("recovered"))
    exception_count = sum(
        1
        for d in decisions
        if d.get("action_type") in ("flag_for_human_review", "no_action_recommended")
        or d.get("action_status") in ("blocked_by_guardrail", "skipped_opt_out")
    )

    return {
        "total_exposure": sum(e.get("amount") or 0 for e in events),
        "total_recovered": sum(
            d.get("amount_recovered") or 0 for d in decisions if d.get("recovered")
        ),
        "total_decisions": total_decisions,
        "recovered_count": recovered_count,
        "recovery_rate_pct": (
            round(recovered_count / total_decisions * 100, 2) if total_decisions else None
        ),
        "guardrail_block_count": sum(
            1 for d in decisions if d.get("action_status") == "blocked_by_guardrail"
        ),
        "opt_out_respected_count": sum(
            1 for d in decisions if d.get("action_status") == "skipped_opt_out"
        ),
        "exception_count": exception_count,
    }


def get_metrics_by_root_cause(decisions: Optional[list[dict]] = None) -> list[dict]:
    """Scoped to the latest batch, same reasoning as get_metrics_overview."""
    if decisions is None:
        _, decisions = _fetch_latest_batch_data()

    by_cause: dict[str, dict] = {}
    for d in decisions:
        cause = d["root_cause"]
        bucket = by_cause.setdefault(
            cause, {"root_cause": cause, "decision_count": 0, "recovered_count": 0, "amount_recovered": 0.0}
        )
        bucket["decision_count"] += 1
        if d.get("recovered"):
            bucket["recovered_count"] += 1
            bucket["amount_recovered"] += d.get("amount_recovered") or 0

    result = []
    for bucket in by_cause.values():
        bucket["recovery_rate_pct"] = (
            round(bucket["recovered_count"] / bucket["decision_count"] * 100, 2)
            if bucket["decision_count"]
            else None
        )
        result.append(bucket)
    result.sort(key=lambda b: b["decision_count"], reverse=True)
    return result


def get_exceptions(decisions: Optional[list[dict]] = None) -> list[dict]:
    """Scoped to the latest batch, same reasoning as get_metrics_overview."""
    if decisions is None:
        _, decisions = _fetch_latest_batch_data()
    exceptions = [
        d
        for d in decisions
        if d.get("action_type") in ("flag_for_human_review", "no_action_recommended")
        or d.get("action_status") in ("blocked_by_guardrail", "skipped_opt_out")
    ]
    exceptions.sort(key=lambda d: d["timestamp"], reverse=True)
    return exceptions


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


def get_cash_flow_metrics(
    events: Optional[list[dict]] = None, decisions: Optional[list[dict]] = None
) -> dict:
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
    if events is None or decisions is None:
        events, decisions = _fetch_latest_batch_data()
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


def get_dashboard_metrics() -> dict:
    """The actual /api/metrics response. Fetches the latest batch's
    events/decisions exactly once (3 Supabase round trips total) and
    hands that same data to all four metric functions, instead of each
    one independently re-fetching the latest batch_id and re-querying
    events/decisions (previously ~10 sequential round trips for one page
    load — a real chunk of the dashboard's load time on top of whatever
    the backend's cold-start latency already costs)."""
    events, decisions = _fetch_latest_batch_data()
    return {
        "overview": get_metrics_overview(events, decisions),
        "by_root_cause": get_metrics_by_root_cause(decisions),
        "exceptions": get_exceptions(decisions),
        "cash_flow": get_cash_flow_metrics(events, decisions),
    }
