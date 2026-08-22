"""Baseline-comparison evaluation harness (ENHANCEMENTS.md §2.1).

Runs the same batch of synthetic cases through four policies —
`do_nothing`, `fixed_dunning`, `vasuli`, `max_pressure` — using common
random numbers (see policies.py's module docstring), and reports
**incremental** recovery (recovered_under_policy - recovered_under_do_nothing)
as the headline number, not raw recovery. Raw recovery on its own flatters
any recovery product, since a chunk of at-risk value comes back with zero
intervention (see outcome_model.natural_recovery_probability).

The `vasuli` arm uses the heuristic diagnosis agent (app/agents/
heuristic_agent.py), not the live Groq/Gemini LLM. Evaluating hundreds of
cases against a live LLM would be slow (rate-limited, ~2-3s/call), cost
API quota, and — critically — introduce its own stochasticity into which
action gets chosen, which would confound the very comparison this harness
exists to make. The heuristic agent already picks from the exact same
allowed action set under the exact same guardrail engine, so this arm is
measuring "Vasuli's guardrailed decision logic" honestly; it is a
deliberately separate question whether the LLM's diagnoses beat the
heuristic's on the cases where they'd disagree (see the LLM-vs-heuristic
comparison in the README, if run).

Usage:
    python -m app.eval.run_comparison --cases 500 [--seed 42] [--out report.json]
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

from app.data.generator import generate_batch
from app.eval.policies import ARMS, ArmResult

ARM_ORDER = ["do_nothing", "fixed_dunning", "vasuli", "max_pressure"]


def run_all_arms(n_cases: int, seed: int) -> dict[str, list[ArmResult]]:
    events = [e.to_dict() for e in generate_batch(n_cases, seed=seed)]
    results: dict[str, list[ArmResult]] = {arm: [] for arm in ARM_ORDER}
    for event in events:
        for arm_name in ARM_ORDER:
            results[arm_name].append(ARMS[arm_name](event, seed))
    return results


def summarize_arm(arm_results: list[ArmResult], do_nothing_results: list[ArmResult]) -> dict:
    n = len(arm_results)
    total_exposure = sum(r.amount for r in arm_results)
    raw_recovered = sum(r.amount_recovered for r in arm_results)
    incremental_recovered = sum(
        r.amount_recovered - dn.amount_recovered for r, dn in zip(arm_results, do_nothing_results)
    )
    total_cost = sum(r.cost for r in arm_results)
    contacts = sum(1 for r in arm_results if r.contacted)
    violations = sum(r.guardrail_violations for r in arm_results)
    executed = sum(1 for r in arm_results if r.action_type not in ("do_nothing",))

    return {
        "cases": n,
        "total_exposure": round(total_exposure, 2),
        "raw_recovered": round(raw_recovered, 2),
        "raw_recovery_rate_pct": round(100 * raw_recovered / total_exposure, 2) if total_exposure else 0.0,
        "incremental_recovered": round(incremental_recovered, 2),
        "incremental_recovery_rate_pct": (
            round(100 * incremental_recovered / total_exposure, 2) if total_exposure else 0.0
        ),
        "total_cost": round(total_cost, 2),
        "cost_per_rupee_recovered": (
            round(total_cost / raw_recovered, 4) if raw_recovered else None
        ),
        "contacts": contacts,
        "contacts_per_case": round(contacts / n, 3) if n else 0.0,
        "guardrail_violations": violations,
        "guardrail_violations_per_case": round(violations / n, 3) if n else 0.0,
    }


def summarize_by_cause(arm_results: list[ArmResult]) -> dict[str, dict]:
    by_type: dict[str, list[ArmResult]] = defaultdict(list)
    for r in arm_results:
        by_type[r.event_type].append(r)
    out = {}
    for event_type, rows in by_type.items():
        total = sum(r.amount for r in rows)
        recovered = sum(r.amount_recovered for r in rows)
        out[event_type] = {
            "cases": len(rows),
            "recovery_rate_pct": round(100 * recovered / total, 2) if total else 0.0,
        }
    return out


def build_report(n_cases: int, seed: int) -> dict:
    all_results = run_all_arms(n_cases, seed)
    do_nothing = all_results["do_nothing"]

    report = {
        "n_cases": n_cases,
        "seed": seed,
        "arms": {
            arm_name: summarize_arm(all_results[arm_name], do_nothing) for arm_name in ARM_ORDER
        },
        "recovery_by_cause": {
            arm_name: summarize_by_cause(all_results[arm_name]) for arm_name in ARM_ORDER
        },
    }
    return report


def print_markdown_report(report: dict) -> None:
    print(f"# Vasuli evaluation harness — {report['n_cases']} cases, seed={report['seed']}\n")
    print(
        "Common random numbers across all arms — each case's \"luck\" is identical "
        "regardless of which policy acts on it.\n"
    )

    print("| Arm | Incremental recovered | Incremental rate | Raw recovered | Raw rate | "
          "Cost | Cost/₹ recovered | Contacts/case | Guardrail violations |")
    print("|---|---|---|---|---|---|---|---|---|")
    for arm_name in ARM_ORDER:
        a = report["arms"][arm_name]
        cost_per_rupee = f"₹{a['cost_per_rupee_recovered']:.4f}" if a["cost_per_rupee_recovered"] is not None else "n/a"
        print(
            f"| {arm_name} | ₹{a['incremental_recovered']:,.2f} | "
            f"{a['incremental_recovery_rate_pct']:.2f}% | ₹{a['raw_recovered']:,.2f} | "
            f"{a['raw_recovery_rate_pct']:.2f}% | ₹{a['total_cost']:,.2f} | {cost_per_rupee} | "
            f"{a['contacts_per_case']:.2f} | {a['guardrail_violations']} |"
        )

    print("\n## Headline: incremental recovery (the number that matters)\n")
    do_nothing_rate = report["arms"]["do_nothing"]["raw_recovery_rate_pct"]
    print(
        f"`do_nothing` recovers {do_nothing_rate:.2f}% of at-risk value with **zero** "
        "intervention — that's the organic baseline every other arm's raw recovery number "
        "already includes for free. Incremental recovery nets this out.\n"
    )
    vasuli = report["arms"]["vasuli"]
    fixed = report["arms"]["fixed_dunning"]
    print(
        f"Vasuli: **₹{vasuli['incremental_recovered']:,.2f}** incremental "
        f"({vasuli['incremental_recovery_rate_pct']:.2f}% of exposure) at "
        f"{vasuli['guardrail_violations']} guardrail violations and "
        f"{vasuli['contacts_per_case']:.2f} contacts/case.\n"
    )
    print(
        f"fixed_dunning: ₹{fixed['incremental_recovered']:,.2f} incremental "
        f"({fixed['incremental_recovery_rate_pct']:.2f}%) at "
        f"{fixed['guardrail_violations']} guardrail violations it never checked for.\n"
    )
    if "max_pressure" in report["arms"]:
        mp = report["arms"]["max_pressure"]
        print(
            f"max_pressure: ₹{mp['incremental_recovered']:,.2f} incremental "
            f"({mp['incremental_recovery_rate_pct']:.2f}%) at **{mp['guardrail_violations']} "
            f"guardrail violations** ({mp['guardrail_violations_per_case']:.2f}/case) — this is "
            "the \"contact/retry as often as technically possible, ignoring guardrails\" arm."
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=None)
    args = parser.parse_args()

    report = build_report(args.cases, args.seed)
    print_markdown_report(report)

    if args.out:
        with open(args.out, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nFull JSON report written to {args.out}")


if __name__ == "__main__":
    main()
