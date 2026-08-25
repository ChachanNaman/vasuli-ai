"""Multi-seed stability report — a second, harder question on top of
run_comparison.py's single-seed comparison: "if a judge re-ran this with a
different seed, would the headline number still say the same thing?"

A single point estimate (even a reproducible one) can't answer that on its
own — reproducibility means *the same seed* always gives *the same
number*, not that the number is representative of typical variation across
seeds. This runs the full 4-arm comparison across N independent seeds and
reports mean/std/coefficient-of-variation per arm per metric, with an
explicit stable/noisy flag at a stated threshold — so a metric that swings
wildly seed-to-seed is labeled as such rather than silently presented with
the same confidence as a stable one.

Usage:
    python -m app.eval.stability --cases 200 --seeds 20 --base-seed 42
"""

from __future__ import annotations

import argparse
import json
import statistics

from app.eval.run_comparison import ARM_ORDER, build_report

# A metric whose seed-to-seed coefficient of variation exceeds this is
# flagged "noisy" rather than presented as if it were a stable estimate.
# Stated explicitly, same convention as ECONOMIC_MULTIPLIER
# (guardrails/rules.py) and FLAG_RATE_DELTA_THRESHOLD_PP (eval/fairness.py)
# — an arguable round number, not a derived statistical standard.
NOISE_THRESHOLD_CV_PCT = 25.0

# Metrics worth tracking stability for per arm. Absolute rupee figures are
# the ones most likely to be noisy (a handful of large invoices can swing
# a small batch's total); rates and counts are usually steadier.
TRACKED_METRICS = [
    "incremental_recovered",
    "incremental_recovery_rate_pct",
    "guardrail_violations",
    "contacts_per_case",
]


def _derive_seed(base_seed: int, index: int) -> int:
    """Deterministic per-run seed, so `--base-seed 42 --seeds 20` always
    produces the exact same 20 seeds in the exact same order — the
    stability report is itself reproducible, not just each individual run
    within it."""
    import hashlib

    digest = hashlib.sha256(f"{base_seed}:{index}".encode()).hexdigest()
    return int(digest[:8], 16)


def _metric_stats(values: list[float]) -> dict:
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    if mean:
        cv_pct = round(abs(std / mean) * 100, 1)
        stable = cv_pct <= NOISE_THRESHOLD_CV_PCT
    elif std == 0:
        # Mean is exactly zero AND there's no spread at all (e.g.
        # do_nothing's incremental recovery, which is tautologically zero
        # every seed) — genuinely, perfectly stable, not an undefined
        # ratio. Only a zero mean WITH nonzero spread is undefined.
        cv_pct = 0.0
        stable = True
    else:
        cv_pct = None
        stable = False
    return {
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "cv_pct": cv_pct,
        "stable": stable,
    }


def run_stability_report(cases_per_seed: int, n_seeds: int, base_seed: int = 42) -> dict:
    seeds = [_derive_seed(base_seed, i) for i in range(n_seeds)]
    per_arm_metric_values: dict[str, dict[str, list[float]]] = {
        arm: {metric: [] for metric in TRACKED_METRICS} for arm in ARM_ORDER
    }

    for seed in seeds:
        report = build_report(cases_per_seed, seed)
        for arm in ARM_ORDER:
            arm_summary = report["arms"][arm]
            for metric in TRACKED_METRICS:
                per_arm_metric_values[arm][metric].append(arm_summary[metric])

    arms_out = {}
    for arm in ARM_ORDER:
        arms_out[arm] = {
            metric: _metric_stats(values)
            for metric, values in per_arm_metric_values[arm].items()
        }

    return {
        "n_seeds": n_seeds,
        "cases_per_seed": cases_per_seed,
        "base_seed": base_seed,
        "noise_threshold_cv_pct": NOISE_THRESHOLD_CV_PCT,
        "arms": arms_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=200)
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--base-seed", type=int, default=42)
    args = parser.parse_args()

    report = run_stability_report(args.cases, args.seeds, args.base_seed)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
