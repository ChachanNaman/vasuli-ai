"""Multi-seed stability report — pure computation, no DB/LLM."""

from __future__ import annotations

from app.eval.stability import _derive_seed, run_stability_report


def test_derive_seed_is_deterministic():
    assert _derive_seed(42, 0) == _derive_seed(42, 0)
    assert _derive_seed(42, 0) != _derive_seed(42, 1)
    assert _derive_seed(42, 0) != _derive_seed(7, 0)


def test_run_stability_report_shape():
    report = run_stability_report(cases_per_seed=30, n_seeds=3, base_seed=1)

    assert report["n_seeds"] == 3
    assert report["cases_per_seed"] == 30
    assert set(report["arms"].keys()) == {
        "do_nothing",
        "fixed_dunning",
        "vasuli",
        "max_pressure",
    }
    for arm_stats in report["arms"].values():
        for metric_stats in arm_stats.values():
            assert "mean" in metric_stats
            assert "std" in metric_stats
            assert "stable" in metric_stats
            assert isinstance(metric_stats["stable"], bool)


def test_run_stability_report_is_reproducible():
    a = run_stability_report(cases_per_seed=20, n_seeds=3, base_seed=99)
    b = run_stability_report(cases_per_seed=20, n_seeds=3, base_seed=99)
    assert a == b


def test_do_nothing_incremental_recovery_is_always_zero_and_stable():
    """do_nothing's incremental recovery is tautologically zero every
    seed (it's compared against itself) — this should show up as exactly
    stable, not as an undefined/NaN coefficient of variation."""
    report = run_stability_report(cases_per_seed=20, n_seeds=5, base_seed=1)
    do_nothing_incremental = report["arms"]["do_nothing"]["incremental_recovered"]
    assert do_nothing_incremental["mean"] == 0.0
    assert do_nothing_incremental["std"] == 0.0
    assert do_nothing_incremental["stable"] is True
    assert do_nothing_incremental["cv_pct"] == 0.0
