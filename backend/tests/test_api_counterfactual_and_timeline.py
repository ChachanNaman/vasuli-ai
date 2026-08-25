"""FEATURES.md #4 (customer timeline) and #5 (counterfactual sandbox) API
routes. Reuses the real guardrail engine and outcome model (no duplicated
logic) against a fake Supabase client."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
        self._filters = []
        self._order_field = None
        self._order_desc = False
        self._limit = None

    def select(self, *_a, **_k):
        return self

    def eq(self, field, value):
        self._filters.append((field, value))
        return self

    def order(self, field, desc=False, **_k):
        self._order_field = field
        self._order_desc = desc
        return self

    def limit(self, n, **_k):
        self._limit = n
        return self

    def execute(self):
        rows = self._rows
        for field, value in self._filters:
            rows = [r for r in rows if r.get(field) == value]
        if self._order_field is not None:
            rows = sorted(
                rows, key=lambda r: r.get(self._order_field) or 0, reverse=self._order_desc
            )
        if self._limit is not None:
            rows = rows[: self._limit]
        self._filters = []
        return _Result(rows)


class _FakeSupabase:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeTable(self._tables.get(name, []))


def _payment_failed_event(event_id="e1", customer_id="cust_1", attempt_number=1):
    return {
        "event_id": event_id,
        "customer_id": customer_id,
        "amount": 1000.0,
        "currency": "INR",
        "payload": {
            "event_id": event_id,
            "event_type": "payment_failed",
            "amount": 1000.0,
            "attempt_number": attempt_number,
            "failure_reason_code": "network_error",
            "dispute_opened": False,
            "customer": {
                "customer_id": customer_id,
                "name": "Test Customer",
                "opted_out_of_recovery_comms": False,
                "language_pref": "english",
                "preferred_channel": "sms",
            },
        },
    }


def test_counterfactual_clears_and_returns_simulated_probability(monkeypatch):
    import app.api.main as main_module

    event = _payment_failed_event()
    fake = _FakeSupabase({"events": [event], "decisions": []})
    monkeypatch.setattr(main_module, "get_supabase", lambda: fake)

    import app.api.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "get_supabase", lambda: fake)

    client = TestClient(app)
    response = client.post("/api/events/e1/counterfactual", json={"action": "smart_retry"})

    assert response.status_code == 200
    body = response.json()
    assert body["simulated"] is True
    assert body["action_status"] == "executed"
    assert len(body["checks"]) == 12
    assert body["simulated_recovery_probability"] is not None
    assert body["simulated_expected_recovery_amount"] is not None


def test_counterfactual_reports_which_rule_blocked_it(monkeypatch):
    import app.api.main as main_module

    # attempt_number=3 trips max_retry_attempts for a payment event.
    event = _payment_failed_event(attempt_number=3)
    fake = _FakeSupabase({"events": [event], "decisions": []})
    monkeypatch.setattr(main_module, "get_supabase", lambda: fake)

    import app.api.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "get_supabase", lambda: fake)

    client = TestClient(app)
    response = client.post("/api/events/e1/counterfactual", json={"action": "smart_retry"})

    assert response.status_code == 200
    body = response.json()
    assert body["action_status"] == "blocked_by_guardrail"
    assert body["simulated_recovery_probability"] is None
    assert "max_retry_attempts" in body["block_reason"]


def test_counterfactual_rejects_unknown_action():
    client = TestClient(app)
    response = client.post("/api/events/e1/counterfactual", json={"action": "not_a_real_action"})
    assert response.status_code == 400


def test_counterfactual_unknown_event_id_404s(monkeypatch):
    import app.api.main as main_module

    fake = _FakeSupabase({"events": [], "decisions": []})
    monkeypatch.setattr(main_module, "get_supabase", lambda: fake)

    client = TestClient(app)
    response = client.post("/api/events/nope/counterfactual", json={"action": "smart_retry"})
    assert response.status_code == 404


def test_customer_timeline_returns_ordered_steps_with_event_type(monkeypatch):
    import app.api.main as main_module

    events = [
        {
            "event_id": "e1",
            "event_type": "payment_failed",
            "amount": 500.0,
            "currency": "INR",
            "customer_id": "cust_1",
            "customer": {"customer_id": "cust_1", "name": "Aarav Sharma"},
        },
        {
            "event_id": "e2",
            "event_type": "subscription_charge_failed",
            "amount": 700.0,
            "currency": "INR",
            "customer_id": "cust_1",
            "customer": {"customer_id": "cust_1", "name": "Aarav Sharma"},
        },
    ]
    decisions = [
        {"decision_id": "d1", "event_id": "e1", "customer_id": "cust_1", "timestamp": 1},
        {"decision_id": "d2", "event_id": "e2", "customer_id": "cust_1", "timestamp": 2},
    ]
    fake = _FakeSupabase({"events": events, "decisions": decisions})
    monkeypatch.setattr(main_module, "get_supabase", lambda: fake)

    client = TestClient(app)
    response = client.get("/api/customers/cust_1/timeline")

    assert response.status_code == 200
    body = response.json()
    assert body["customer"]["name"] == "Aarav Sharma"
    assert [s["event_type"] for s in body["steps"]] == [
        "payment_failed",
        "subscription_charge_failed",
    ]


def test_customer_timeline_unknown_customer_404s(monkeypatch):
    import app.api.main as main_module

    fake = _FakeSupabase({"events": [], "decisions": []})
    monkeypatch.setattr(main_module, "get_supabase", lambda: fake)

    client = TestClient(app)
    response = client.get("/api/customers/does-not-exist/timeline")
    assert response.status_code == 404
