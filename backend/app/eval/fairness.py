"""FEATURES.md #6: fairness/consistency check.

Does recommended-action *assignment* (not outcome — outcomes are properly
probabilistic, app/recovery/outcome_model.py) differ across customer
segments that shouldn't matter: language preference, preferred channel,
and tenure bucket?

Deliberately not a rigorous causal-fairness paper — a small, honest,
clearly-labeled proportion-delta check with a stated threshold, in the
same spirit as ECONOMIC_MULTIPLIER in app/guardrails/rules.py: a number
that can be argued with, not one dressed up as more rigorous than it is.
Reports the result as found, either way — an overclaimed "proven fair"
would read worse than not having this feature at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from app.audit.supabase_client import get_supabase

# A restrictive/no-action outcome (routed to a human, or nothing sent) as
# opposed to a direct recovery action — the thing we compare across
# segments. If one segment gets routed to "flag for human review" at a
# meaningfully higher rate than another for no operational reason, that's
# the kind of inconsistency this check exists to catch.
RESTRICTIVE_ACTIONS = {"flag_for_human_review", "no_action_recommended"}

# Stated, arguable threshold, not a fairness-literature standard — same
# transparency convention as every other constant in this codebase that's
# a judgment call rather than a derived figure.
FLAG_RATE_DELTA_THRESHOLD_PP = 15.0


@dataclass
class SegmentStat:
    segment_value: str
    decision_count: int
    restrictive_count: int
    restrictive_rate_pct: float

    def to_dict(self) -> dict:
        return {
            "segment_value": self.segment_value,
            "decision_count": self.decision_count,
            "restrictive_count": self.restrictive_count,
            "restrictive_rate_pct": self.restrictive_rate_pct,
        }


@dataclass
class FairnessDimensionResult:
    dimension: str
    segments: list[SegmentStat]
    max_delta_pp: Optional[float]
    flagged: bool
    summary: str

    def to_dict(self) -> dict:
        return {
            "dimension": self.dimension,
            "segments": [s.to_dict() for s in self.segments],
            "max_delta_pp": self.max_delta_pp,
            "flagged": self.flagged,
            "summary": self.summary,
        }


def _tenure_bucket(tenure_months: Optional[float]) -> str:
    if tenure_months is None:
        return "unknown"
    return "new (<6mo)" if tenure_months < 6 else "long-standing (>=6mo)"


def _compute_dimension(
    rows: list[dict], dimension: str, key_fn: Callable[[dict], str]
) -> FairnessDimensionResult:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(key_fn(row), []).append(row)

    segments = []
    for value, group_rows in sorted(groups.items()):
        count = len(group_rows)
        restrictive = sum(1 for r in group_rows if r["action_type"] in RESTRICTIVE_ACTIONS)
        rate = round(restrictive / count * 100, 1) if count else 0.0
        segments.append(SegmentStat(value, count, restrictive, rate))

    # Segments with too little data to mean anything shouldn't drive the
    # comparison or the headline finding.
    comparable = [s for s in segments if s.decision_count >= 5]
    rates = [s.restrictive_rate_pct for s in comparable]
    max_delta = round(max(rates) - min(rates), 1) if len(rates) >= 2 else None
    flagged = max_delta is not None and max_delta > FLAG_RATE_DELTA_THRESHOLD_PP

    if max_delta is None:
        summary = (
            f"Not enough decisions per {dimension} segment yet (need >=5 each) to "
            "compare honestly."
        )
    elif flagged:
        summary = (
            f"Flag-rate gap of {max_delta}pp across {dimension} segments exceeds the "
            f"{FLAG_RATE_DELTA_THRESHOLD_PP}pp threshold — evidence of differential "
            f"treatment by {dimension} in this batch, worth investigating."
        )
    else:
        summary = (
            f"Flag-rate gap of {max_delta}pp across {dimension} segments is within the "
            f"{FLAG_RATE_DELTA_THRESHOLD_PP}pp threshold — no evidence of differential "
            f"treatment by {dimension} in this batch."
        )

    return FairnessDimensionResult(
        dimension=dimension, segments=segments, max_delta_pp=max_delta, flagged=flagged,
        summary=summary,
    )


def run_fairness_check() -> dict:
    """Computed over every decision currently on record — "a completed
    batch" in practice means whatever has been run and written so far."""
    supabase = get_supabase()
    decisions = supabase.table("decisions").select("event_id, action_type").execute().data or []
    events = supabase.table("events").select("event_id, customer").execute().data or []
    event_by_id = {e["event_id"]: e for e in events}

    rows = []
    for d in decisions:
        event = event_by_id.get(d["event_id"])
        if not event:
            continue
        customer = event.get("customer") or {}
        rows.append(
            {
                "action_type": d["action_type"],
                "language_pref": customer.get("language_pref") or "unknown",
                "preferred_channel": customer.get("preferred_channel") or "unknown",
                "tenure_bucket": _tenure_bucket(customer.get("tenure_months")),
            }
        )

    dimensions = [
        _compute_dimension(rows, "language preference", lambda r: r["language_pref"]),
        _compute_dimension(rows, "preferred channel", lambda r: r["preferred_channel"]),
        _compute_dimension(rows, "tenure", lambda r: r["tenure_bucket"]),
    ]

    return {
        "threshold_pp": FLAG_RATE_DELTA_THRESHOLD_PP,
        "sample_size": len(rows),
        "dimensions": [d.to_dict() for d in dimensions],
    }
