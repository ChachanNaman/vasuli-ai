"""FEATURES.md #6: fairness/consistency check."""

from __future__ import annotations

from app.eval import fairness


class _Result:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *_a, **_k):
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


def _customer(language_pref="english", preferred_channel="sms", tenure_months=12):
    return {
        "language_pref": language_pref,
        "preferred_channel": preferred_channel,
        "tenure_months": tenure_months,
    }


def test_fairness_reports_no_evidence_when_rates_are_close(monkeypatch):
    events = []
    decisions = []
    for i in range(20):
        eid = f"e{i}"
        lang = "hinglish" if i % 2 == 0 else "english"
        events.append({"event_id": eid, "customer": _customer(language_pref=lang)})
        # Within each language group, flag exactly 1 in 5 -> identical 20%
        # rate for both segments, 0pp gap.
        group_index = i // 2
        action = "flag_for_human_review" if group_index % 5 == 0 else "smart_retry"
        decisions.append({"event_id": eid, "action_type": action})

    fake = _FakeSupabase(decisions, events)
    monkeypatch.setattr(fairness, "get_supabase", lambda: fake)

    result = fairness.run_fairness_check()

    lang_dim = next(d for d in result["dimensions"] if d["dimension"] == "language preference")
    assert lang_dim["flagged"] is False
    assert "no evidence" in lang_dim["summary"]


def test_fairness_flags_a_real_gap(monkeypatch):
    events = []
    decisions = []
    # hinglish speakers: always flagged. english speakers: never flagged.
    for i in range(6):
        eid = f"h{i}"
        events.append({"event_id": eid, "customer": _customer(language_pref="hinglish")})
        decisions.append({"event_id": eid, "action_type": "flag_for_human_review"})
    for i in range(6):
        eid = f"en{i}"
        events.append({"event_id": eid, "customer": _customer(language_pref="english")})
        decisions.append({"event_id": eid, "action_type": "smart_retry"})

    fake = _FakeSupabase(decisions, events)
    monkeypatch.setattr(fairness, "get_supabase", lambda: fake)

    result = fairness.run_fairness_check()

    lang_dim = next(d for d in result["dimensions"] if d["dimension"] == "language preference")
    assert lang_dim["flagged"] is True
    assert lang_dim["max_delta_pp"] == 100.0
    assert "evidence of differential treatment" in lang_dim["summary"]


def test_fairness_handles_too_little_data(monkeypatch):
    events = [{"event_id": "e1", "customer": _customer()}]
    decisions = [{"event_id": "e1", "action_type": "smart_retry"}]
    fake = _FakeSupabase(decisions, events)
    monkeypatch.setattr(fairness, "get_supabase", lambda: fake)

    result = fairness.run_fairness_check()

    for dim in result["dimensions"]:
        assert dim["max_delta_pp"] is None
        assert dim["flagged"] is False
