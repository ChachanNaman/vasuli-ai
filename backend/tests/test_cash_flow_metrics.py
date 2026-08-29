"""FEATURES.md #3: cash-flow-language derived metrics. Pure computation
over decisions/events rows — no view, no live Supabase needed."""

from __future__ import annotations

from app.audit import metrics


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def execute(self):
        return _Result(self._rows)


class _FakeSupabase:
    def __init__(self, decisions, events):
        self._decisions = decisions
        self._events = events

    def table(self, name):
        if name == "decisions":
            return _FakeTable(self._decisions)
        if name == "events":
            return _FakeTable(self._events)
        raise AssertionError(f"unexpected table {name!r}")


def test_cash_flow_metrics_computes_days_and_mrr_pct(monkeypatch):
    events = [
        {"event_id": "e1", "event_type": "subscription_charge_failed", "amount": 1000.0},
        {"event_id": "e2", "event_type": "subscription_charge_failed", "amount": 2000.0},
        {"event_id": "e3", "event_type": "payment_failed", "amount": 5000.0},
    ]
    decisions = [
        {"event_id": "e1", "recovered": True, "amount_recovered": 1000.0},
        {"event_id": "e2", "recovered": False, "amount_recovered": 0.0},
        {"event_id": "e3", "recovered": True, "amount_recovered": 5000.0},
    ]
    fake = _FakeSupabase(decisions, events)
    monkeypatch.setattr(metrics, "get_supabase", lambda: fake)

    result = metrics.get_cash_flow_metrics()

    assert result["average_daily_revenue_assumed"] == metrics.AVERAGE_DAILY_REVENUE_INR
    assert result["days_of_reduced_receivables"] == round(
        6000.0 / metrics.AVERAGE_DAILY_REVENUE_INR, 1
    )
    assert result["subscription_mrr_at_risk"] == 3000.0
    assert result["subscription_mrr_recovered"] == 1000.0
    # 1000 recovered of 3000 at-risk subscription MRR
    assert result["pct_at_risk_mrr_prevented"] == round(1000.0 / 3000.0 * 100, 1)


def test_cash_flow_metrics_handles_no_data(monkeypatch):
    fake = _FakeSupabase([], [])
    monkeypatch.setattr(metrics, "get_supabase", lambda: fake)

    result = metrics.get_cash_flow_metrics()

    assert result["days_of_reduced_receivables"] == 0.0
    assert result["pct_at_risk_mrr_prevented"] is None


def test_cash_flow_metrics_no_subscription_events_gives_none_pct(monkeypatch):
    events = [{"event_id": "e1", "event_type": "payment_failed", "amount": 500.0}]
    decisions = [{"event_id": "e1", "recovered": True, "amount_recovered": 500.0}]
    fake = _FakeSupabase(decisions, events)
    monkeypatch.setattr(metrics, "get_supabase", lambda: fake)

    result = metrics.get_cash_flow_metrics()

    assert result["subscription_mrr_at_risk"] == 0.0
    assert result["pct_at_risk_mrr_prevented"] is None
