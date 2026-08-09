#!/usr/bin/env python3
"""Analyze the preregistered 100-map deadline-aware CARE planner matrix."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


METRICS = (
    "completion_success_rate", "instance_success_rate", "episode_length",
    "attempted_bytes", "attempted_control_bytes", "attempted_repair_bytes",
    "mean_path_repairable_error", "mean_path_truth_error", "planning_cpu_ms",
    "utility_trigger_cpu_ms", "episode_cpu_ms",
)
POLICIES = (
    "one_shot_delta", "action_triggered_repair", "utility_triggered_repair",
    "deadline_aware_repair",
)
PLANNERS = ("astar", "dstar_lite")
DELAYS = (0, 1, 2, 4)
DIAGNOSTICS = (
    "deadline_trigger_checks", "deadline_ambiguous_receivers",
    "deadline_feasible_receivers", "deadline_infeasible_receivers",
    "deadline_query_cells", "mean_decision_slack",
)


def _bootstrap_mean(values: np.ndarray, *, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(20_000, len(values)), replace=True).mean(axis=1)
    return tuple(float(item) for item in np.quantile(samples, (0.025, 0.975)))


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(input_directory: Path, output_directory: Path) -> dict:
    output_directory.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader((input_directory / "results.csv").open()))
    expected = 100 * len(POLICIES) * len(PLANNERS) * len(DELAYS)
    if len(rows) != expected:
        raise ValueError(f"expected {expected} complete rows, found {len(rows)}")
    groups: dict[tuple[str, int, str], dict[tuple[str, str], dict]] = defaultdict(dict)
    for row in rows:
        key = row["layout_seed"], row["network_seed"]
        condition = row["planner"], int(row["delay_steps"]), row["policy"]
        if key in groups[condition]:
            raise ValueError(f"duplicate matched trial: {condition}, {key}")
        groups[condition][key] = row
    expected_keys = {(str(seed), str(seed)) for seed in range(100)}
    for condition in ((p, d, m) for p in PLANNERS for d in DELAYS for m in POLICIES):
        if set(groups[condition]) != expected_keys:
            raise ValueError(f"incomplete independent-map condition: {condition}")

    summary_rows: list[dict] = []
    for condition_index, condition in enumerate(sorted(groups)):
        planner, delay, policy = condition
        group = groups[condition]
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([float(group[key][metric]) for key in sorted(group)])
            low, high = _bootstrap_mean(values, seed=condition_index * 100 + metric_index)
            summary_rows.append({
                "planner": planner, "delay_steps": delay, "policy": policy,
                "metric": metric, "independent_maps": 100,
                "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
            })

    comparisons = []
    pairs = (
        ("deadline_aware_repair", "one_shot_delta"),
        ("deadline_aware_repair", "action_triggered_repair"),
        ("deadline_aware_repair", "utility_triggered_repair"),
    )
    comparison_index = 0
    for planner in PLANNERS:
        for delay in DELAYS:
            for left, right in pairs:
                left_rows, right_rows = groups[(planner, delay, left)], groups[(planner, delay, right)]
                for metric_index, metric in enumerate(METRICS):
                    differences = np.asarray([
                        float(left_rows[key][metric]) - float(right_rows[key][metric])
                        for key in sorted(expected_keys)
                    ])
                    low, high = _bootstrap_mean(
                        differences, seed=50_000 + comparison_index * 100 + metric_index,
                    )
                    std = float(differences.std(ddof=1))
                    comparisons.append({
                        "planner": planner, "delay_steps": delay,
                        "left": left, "right": right, "metric": metric,
                        "paired_maps": 100, "mean_difference": float(differences.mean()),
                        "std_difference": std, "paired_effect_dz": (
                            float(differences.mean() / std) if std > 0 else 0.0
                        ),
                        "ci95_low": low, "ci95_high": high,
                    })
                comparison_index += 1

    # Cross-planner sensitivity is paired on every map/policy/delay.
    planner_rows = []
    for delay in DELAYS:
        for policy in POLICIES:
            left_rows = groups[("dstar_lite", delay, policy)]
            right_rows = groups[("astar", delay, policy)]
            for metric_index, metric in enumerate(METRICS):
                differences = np.asarray([
                    float(left_rows[key][metric]) - float(right_rows[key][metric])
                    for key in sorted(expected_keys)
                ])
                low, high = _bootstrap_mean(
                    differences, seed=90_000 + delay * 1_000 + POLICIES.index(policy) * 100 + metric_index,
                )
                planner_rows.append({
                    "delay_steps": delay, "policy": policy, "metric": metric,
                    "left": "dstar_lite", "right": "astar", "paired_maps": 100,
                    "mean_difference": float(differences.mean()),
                    "std_difference": float(differences.std(ddof=1)),
                    "ci95_low": low, "ci95_high": high,
                })

    _write_csv(output_directory / "summary_mean_std_ci.csv", summary_rows)
    _write_csv(output_directory / "paired_policy_comparisons.csv", comparisons)
    _write_csv(output_directory / "paired_planner_sensitivity.csv", planner_rows)
    diagnostic_rows = []
    for planner in PLANNERS:
        for delay in DELAYS:
            group = groups[(planner, delay, "deadline_aware_repair")]
            for metric_index, metric in enumerate(DIAGNOSTICS):
                values = np.asarray([
                    float(group[key][metric]) for key in sorted(group)
                    if group[key][metric] not in {"", "None"}
                ])
                low, high = _bootstrap_mean(
                    values, seed=120_000 + delay * 100 + metric_index,
                )
                diagnostic_rows.append({
                    "planner": planner, "delay_steps": delay,
                    "metric": metric, "independent_maps": len(values),
                    "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                    "ci95_low": low, "ci95_high": high,
                })
    _write_csv(output_directory / "deadline_diagnostics.csv", diagnostic_rows)

    lookup = {
        (row["planner"], row["delay_steps"], row["left"], row["right"], row["metric"]): row
        for row in comparisons
    }
    gates = []
    for planner in PLANNERS:
        csr = lookup[(planner, 0, "deadline_aware_repair", "utility_triggered_repair", "completion_success_rate")]
        traffic = lookup[(planner, 0, "deadline_aware_repair", "utility_triggered_repair", "attempted_bytes")]
        baseline = lookup[(planner, 0, "deadline_aware_repair", "one_shot_delta", "completion_success_rate")]
        gates.append({
            "planner": planner,
            "csr_noninferior_to_psr_ut_at_delay0": csr["ci95_low"] >= -0.02,
            "traffic_no_higher_than_psr_ut_at_delay0": traffic["ci95_high"] <= 0.0,
            "csr_improves_over_one_shot_at_delay0": baseline["ci95_low"] > 0.0,
            "csr_vs_psr_ut_mean": csr["mean_difference"],
            "bytes_vs_psr_ut_mean": traffic["mean_difference"],
            "csr_vs_one_shot_mean": baseline["mean_difference"],
        })
    decision = {
        "gate_definition": {
            "csr_noninferiority_margin": -0.02,
            "traffic_rule": "paired 95% CI upper bound <= 0 bytes",
            "baseline_rule": "paired CSR 95% CI lower bound > 0",
        },
        "planners": gates,
        "promote_deadline_aware_care": all(
            gate["csr_noninferior_to_psr_ut_at_delay0"]
            and gate["traffic_no_higher_than_psr_ut_at_delay0"]
            and gate["csr_improves_over_one_shot_at_delay0"]
            for gate in gates
        ),
    }
    (output_directory / "gate_decision.json").write_text(json.dumps(decision, indent=2) + "\n")

    lines = [
        "# Deadline-aware CARE: paired 100-map cross-planner result", "",
        "Differences are `deadline_aware_repair - comparator` on identical maps and link traces.", "",
        "| Planner | Gate | CSR vs PSR-UT | Bytes vs PSR-UT | CSR vs One-shot |", "|---|---:|---:|---:|---:|",
    ]
    for gate in gates:
        passed = all(
            gate[key] for key in (
                "csr_noninferior_to_psr_ut_at_delay0",
                "traffic_no_higher_than_psr_ut_at_delay0",
                "csr_improves_over_one_shot_at_delay0",
            )
        )
        lines.append(
            f"| {gate['planner']} | {'PASS' if passed else 'FAIL'} | "
            f"{gate['csr_vs_psr_ut_mean']:+.4f} | {gate['bytes_vs_psr_ut_mean']:+.1f} | "
            f"{gate['csr_vs_one_shot_mean']:+.4f} |"
        )
    (output_directory / "RESULT.md").write_text("\n".join(lines) + "\n")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.input_directory, args.output_directory), indent=2))


if __name__ == "__main__":
    main()
