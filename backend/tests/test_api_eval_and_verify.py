"""Tests for the /api/audit/verify and /api/eval/comparison routes
(ENHANCEMENTS.md §2.4, §2.1 surfaced to the frontend)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app


def test_eval_comparison_endpoint_returns_all_arms():
    client = TestClient(app)
    response = client.get("/api/eval/comparison", params={"cases": 20, "seed": 1})
    assert response.status_code == 200
    body = response.json()
    assert body["n_cases"] == 20
    assert set(body["arms"].keys()) == {"do_nothing", "fixed_dunning", "vasuli", "max_pressure"}


def test_eval_comparison_endpoint_rejects_out_of_range_cases():
    client = TestClient(app)
    response = client.get("/api/eval/comparison", params={"cases": 5})  # below min of 10
    assert response.status_code == 422


def test_audit_verify_endpoint_shape(monkeypatch):
    import app.api.main as main_module

    monkeypatch.setattr(main_module, "verify_chain", lambda: (True, 42, None))
    client = TestClient(app)
    response = client.get("/api/audit/verify")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "records_checked": 42, "error": None}


def test_audit_verify_endpoint_reports_broken_chain(monkeypatch):
    import app.api.main as main_module

    monkeypatch.setattr(
        main_module, "verify_chain", lambda: (False, 3, "position 3: mismatch")
    )
    client = TestClient(app)
    response = client.get("/api/audit/verify")
    body = response.json()
    assert body["ok"] is False
    assert body["records_checked"] == 3
    assert "mismatch" in body["error"]
