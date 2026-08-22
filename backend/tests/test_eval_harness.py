"""Tests for the evaluation harness (ENHANCEMENTS.md §2.1). No mocking
needed — the harness only calls deterministic code (the heuristic agent,
the guardrail engine, the outcome model), never the LLM or Supabase."""

from __future__ import annotations

from app.data.generator import generate_batch
from app.eval.policies import ARMS, run_do_nothing, run_vasuli
from app.eval.run_comparison import build_report


def test_common_random_numbers_reproducible_across_repeated_runs():
    """Same master_seed + same case must produce the exact same draw every
    time — the whole "common random numbers" contract depends on this."""
    events = [e.to_dict() for e in generate_batch(20, seed=1)]
    first_pass = [run_vasuli(e, master_seed=99) for e in events]
    second_pass = [run_vasuli(e, master_seed=99) for e in events]
    assert [r.recovered for r in first_pass] == [r.recovered for r in second_pass]


def test_deferred_no_action_matches_do_nothing_for_the_same_case():
    """A case where Vasuli takes no real action (blocked, skipped, or a
    genuine no-op diagnosis) must recover identically to do_nothing on
    that same case — this is the regression test for the bug where 'no
    action' was scored as a hard zero instead of deferring to the
    organic-recovery draw, which made restraint look like a loss instead
    of a wash."""
    events = [e.to_dict() for e in generate_batch(100, seed=7)]
    deferred_cases_checked = 0
    for event in events:
        vasuli_result = run_vasuli(event, master_seed=42)
        if vasuli_result.cost == 0.0:  # nothing executed -> deferred to organic recovery
            do_nothing_result = run_do_nothing(event, master_seed=42)
            assert vasuli_result.recovered == do_nothing_result.recovered
            deferred_cases_checked += 1
    assert deferred_cases_checked > 0, "expected at least one deferred case in this batch"


def test_incremental_recovery_never_negative_for_any_arm():
    """No arm should ever recover *less* than doing nothing, in aggregate —
    every arm is do_nothing's organic draw plus, at best, additional
    action-driven recovery on top. A negative number here means a case is
    being penalized for restraint (the exact bug this harness caught once
    already)."""
    report = build_report(n_cases=200, seed=11)
    for arm_name, summary in report["arms"].items():
        assert summary["incremental_recovered"] >= 0, f"{arm_name} had negative incremental recovery"


def test_all_four_arms_run_without_error():
    events = [e.to_dict() for e in generate_batch(30, seed=3)]
    for event in events:
        for arm_name, arm_fn in ARMS.items():
            result = arm_fn(event, master_seed=5)
            assert result.case_id == event["event_id"]
            assert result.amount_recovered >= 0
            assert result.cost >= 0


def test_report_has_expected_shape():
    report = build_report(n_cases=50, seed=21)
    assert report["n_cases"] == 50
    assert set(report["arms"].keys()) == {"do_nothing", "fixed_dunning", "vasuli", "max_pressure"}
    for summary in report["arms"].values():
        assert "incremental_recovered" in summary
        assert "cost_per_rupee_recovered" in summary
        assert "contacts_per_case" in summary
        assert "guardrail_violations" in summary


def test_vasuli_has_fewer_or_equal_guardrail_violations_than_naive_arms():
    """The headline compliance comparison: Vasuli's guardrailed policy
    should never rack up more violations than an arm that doesn't check
    guardrails at all."""
    report = build_report(n_cases=300, seed=13)
    vasuli_violations = report["arms"]["vasuli"]["guardrail_violations"]
    for arm_name in ("fixed_dunning", "max_pressure"):
        assert vasuli_violations <= report["arms"][arm_name]["guardrail_violations"]
