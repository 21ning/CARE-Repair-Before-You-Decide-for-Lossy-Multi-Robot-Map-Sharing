#!/usr/bin/env python3
"""Paired analysis and promotion gate for scenario-certificate CARE."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from bootstrap_ci import bootstrap_mean_ci
except ModuleNotFoundError:
    from scripts.bootstrap_ci import bootstrap_mean_ci

try:
    from structured_role_metrics import ROLE_PROVENANCE, metric_value
except ModuleNotFoundError:  # Imported as ``scripts.analyze_*`` in tests.
    from scripts.structured_role_metrics import ROLE_PROVENANCE, metric_value


PLANNERS = ("astar", "dstar_lite")
DELAYS = (0, 1, 2, 4)
POLICIES = (
    "one_shot_delta", "utility_triggered_repair", "deadline_aware_repair",
    "certificate_repair",
)
METRICS = (
    "seeker_success_rate", "completion_success_rate", "instance_success_rate", "episode_length",
    "attempted_bytes", "attempted_control_bytes", "attempted_repair_bytes",
    "mean_path_truth_error", "planning_cpu_ms", "certificate_cpu_ms",
    "episode_cpu_ms",
)
DIAGNOSTICS = (
    "certificate_checks", "certificate_scenario_planning_calls",
    "certificate_conflicting_pairs", "certificate_feasible_pairs",
    "certificate_infeasible_pairs", "certificate_candidate_cells",
    "certificate_query_cells",
)


def bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    del seed
    return bootstrap_mean_ci(values)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def analyze(
    input_directory: Path, output_directory: Path,
    certificate_directory: Path | None = None,
) -> dict:
    output_directory.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader((input_directory / "results.csv").open()))
    direct_role_metrics = all(
        row.get("seeker_success_rate", "") not in (None, "") for row in rows
    )
    if certificate_directory is not None:
        replacements = list(csv.DictReader((certificate_directory / "results.csv").open()))
        replacement_conditions = {
            (row["planner"], row["delay_steps"], row["policy"])
            for row in replacements
        }
        rows = [
            row for row in rows
            if (row["planner"], row["delay_steps"], row["policy"])
            not in replacement_conditions
        ]
        rows.extend(replacements)
    expected_count = 100 * len(PLANNERS) * len(DELAYS) * len(POLICIES)
    if len(rows) != expected_count:
        raise ValueError(f"expected {expected_count} complete episodes, found {len(rows)}")
    fingerprints_by_seed = defaultdict(set)
    for row in rows:
        fingerprints_by_seed[row["layout_seed"]].add(row["layout_fingerprint"])
    if set(fingerprints_by_seed) != {str(seed) for seed in range(100)}:
        raise ValueError("layout seed set is not exactly 0..99")
    if any(len(values) != 1 for values in fingerprints_by_seed.values()):
        raise ValueError("a layout seed maps to multiple physical layouts")
    if len({next(iter(values)) for values in fingerprints_by_seed.values()}) != 100:
        raise ValueError("the matrix does not contain 100 unique physical layouts")
    groups = defaultdict(dict)
    for row in rows:
        condition = row["planner"], int(row["delay_steps"]), row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate trial {condition}, {key}")
        groups[condition][key] = row
    ordered_keys = tuple((str(seed), str(seed)) for seed in range(100))
    keys = set(ordered_keys)
    for condition in ((p, d, m) for p in PLANNERS for d in DELAYS for m in POLICIES):
        if set(groups[condition]) != keys:
            raise ValueError(f"incomplete matched condition: {condition}")

    summary = []
    for condition_index, condition in enumerate(sorted(groups)):
        planner, delay, policy = condition
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([
                metric_value(groups[condition][key], metric) for key in ordered_keys
            ])
            low, high = bootstrap(values, condition_index * 100 + metric_index)
            summary.append({
                "planner": planner, "delay_steps": delay, "policy": policy,
                "metric": metric, "independent_maps": 100,
                "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
            })

    paired = []
    comparison_index = 0
    for planner in PLANNERS:
        for delay in DELAYS:
            left = groups[(planner, delay, "certificate_repair")]
            for comparator in POLICIES[:-1]:
                right = groups[(planner, delay, comparator)]
                for metric_index, metric in enumerate(METRICS):
                    differences = np.asarray([
                        metric_value(left[key], metric) - metric_value(right[key], metric)
                        for key in ordered_keys
                    ])
                    low, high = bootstrap(differences, 50_000 + comparison_index * 100 + metric_index)
                    std = float(differences.std(ddof=1))
                    paired.append({
                        "planner": planner, "delay_steps": delay,
                        "left": "certificate_repair", "right": comparator,
                        "metric": metric, "paired_maps": 100,
                        "mean_difference": float(differences.mean()),
                        "std_difference": std,
                        "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                        "ci95_low": low, "ci95_high": high,
                    })
                comparison_index += 1

    diagnostics = []
    for planner in PLANNERS:
        for delay in DELAYS:
            group = groups[(planner, delay, "certificate_repair")]
            for metric_index, metric in enumerate(DIAGNOSTICS):
                values = np.asarray([float(group[key][metric]) for key in ordered_keys])
                low, high = bootstrap(values, 90_000 + delay * 100 + metric_index)
                diagnostics.append({
                    "planner": planner, "delay_steps": delay, "metric": metric,
                    "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                    "ci95_low": low, "ci95_high": high,
                })
    write_csv(output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(output_directory / "paired_comparisons.csv", paired)
    write_csv(output_directory / "certificate_diagnostics.csv", diagnostics)

    lookup = {
        (row["planner"], row["delay_steps"], row["right"], row["metric"]): row
        for row in paired
    }
    summary_lookup = {
        (row["planner"], row["delay_steps"], row["policy"], row["metric"]): row
        for row in summary
    }
    gates = []
    for planner in PLANNERS:
        reliability = lookup[(planner, 0, "deadline_aware_repair", "seeker_success_rate")]
        delayed_reliability = lookup[(planner, 1, "deadline_aware_repair", "seeker_success_rate")]
        traffic = lookup[(planner, 0, "deadline_aware_repair", "attempted_bytes")]
        baseline = lookup[(planner, 0, "one_shot_delta", "seeker_success_rate")]
        certificate_cpu = float(summary_lookup[(planner, 0, "certificate_repair", "episode_cpu_ms")]["mean"])
        care_lite_cpu = float(summary_lookup[(planner, 0, "deadline_aware_repair", "episode_cpu_ms")]["mean"])
        gate = {
            "planner": planner,
            "noninferior_to_care_lite": reliability["ci95_low"] >= -0.02,
            "noninferior_to_care_lite_at_delay1": delayed_reliability["ci95_low"] >= -0.02,
            "traffic_no_higher_than_care_lite": traffic["ci95_high"] <= 0.0,
            "improves_over_one_shot": baseline["ci95_low"] > 0.0,
            "episode_cpu_ratio_vs_care_lite": certificate_cpu / care_lite_cpu,
            "cpu_ratio_below_3": certificate_cpu / care_lite_cpu <= 3.0,
            "csr_vs_care_lite": reliability["mean_difference"],
            "csr_vs_care_lite_at_delay1": delayed_reliability["mean_difference"],
            "bytes_vs_care_lite": traffic["mean_difference"],
        }
        gate["pass"] = all(gate[key] for key in (
            "noninferior_to_care_lite", "noninferior_to_care_lite_at_delay1",
            "traffic_no_higher_than_care_lite",
            "improves_over_one_shot", "cpu_ratio_below_3",
        ))
        gates.append(gate)
    decision = {
        "scope": "q-sparse scenario family with q=2 and at most 8 candidate cells",
        "gate": {
            "csr_noninferiority_margin": -0.02,
            "csr_noninferiority_checked_at_delays": [0, 1],
            "traffic": "paired 95% CI upper bound <= 0",
            "one_shot": "paired CSR 95% CI lower bound > 0",
            "episode_cpu_ratio": "<= 3x CARE-Lite",
        },
        "comparator": "CARE-Lite (deadline_aware_repair)",
        "planners": gates,
        "promote_certificate_as_care": all(gate["pass"] for gate in gates),
        "primary_reliability_endpoint": "seeker CSR",
        "role_metric_provenance": (
            "Direct seeker_success_rate serialized by the role-aware runner."
            if direct_role_metrics else ROLE_PROVENANCE
        ),
    }
    (output_directory / "gate_decision.json").write_text(json.dumps(decision, indent=2) + "\n")
    return decision


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--certificate-directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(analyze(
        args.input_directory, args.output_directory, args.certificate_directory,
    ), indent=2))


if __name__ == "__main__":
    main()
