#!/usr/bin/env python3
"""Analyze CARE against matched communication baselines across loss rates."""

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


PLANNERS = ("astar", "dstar_lite")
LOSSES = (0.0, .1, .2, .3, .4, .5)
POLICIES = (
    "one_shot_delta", "retry_all_arq", "path_weighted_arq",
    "periodic_full_sync", "mismatch_triggered_full_repair",
    "utility_triggered_repair", "deadline_aware_repair", "certificate_repair",
)
METRICS = (
    "seeker_success_rate", "critical_pair_success_rate",
    "observer_success_rate", "completion_success_rate", "all_seekers_success",
    "instance_success_rate", "episode_length",
    "attempted_bytes", "attempted_control_bytes", "attempted_repair_bytes",
    "mean_path_truth_error", "planning_cpu_ms", "episode_cpu_ms",
)


def bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    """Cluster bootstrap over independent maps (the experimental unit)."""
    del seed  # retained for call-site compatibility; the ordered data key the RNG.
    return bootstrap_mean_ci(values)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def analyze(input_directory: Path, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader((input_directory / "results.csv").open()))
    expected = 100 * len(PLANNERS) * len(LOSSES) * len(POLICIES)
    if len(rows) != expected:
        raise ValueError(f"expected {expected} complete rows, found {len(rows)}")
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
        condition = row["planner"], float(row["loss_probability"]), row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate trial {condition}, {key}")
        groups[condition][key] = row
    ordered_keys = tuple((str(seed), str(seed)) for seed in range(100))
    keys = set(ordered_keys)
    for condition in ((p, loss, m) for p in PLANNERS for loss in LOSSES for m in POLICIES):
        if set(groups[condition]) != keys:
            raise ValueError(f"incomplete condition {condition}")

    summary = []
    for condition_index, condition in enumerate(sorted(groups)):
        planner, loss, policy = condition
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([float(groups[condition][key][metric]) for key in ordered_keys])
            low, high = bootstrap(values, condition_index * 100 + metric_index)
            summary.append({
                "planner": planner, "loss_probability": loss, "policy": policy,
                "metric": metric, "independent_maps": 100,
                "ci_method": "20000-draw map-cluster bootstrap",
                "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
            })

    paired = []
    comparison_index = 0
    for planner in PLANNERS:
        for loss in LOSSES:
            left = groups[(planner, loss, "certificate_repair")]
            for comparator in POLICIES[:-1]:
                right = groups[(planner, loss, comparator)]
                for metric_index, metric in enumerate(METRICS):
                    differences = np.asarray([
                        float(left[key][metric]) - float(right[key][metric])
                        for key in ordered_keys
                    ])
                    low, high = bootstrap(differences, 80_000 + comparison_index * 100 + metric_index)
                    std = float(differences.std(ddof=1))
                    paired.append({
                        "planner": planner, "loss_probability": loss,
                        "left": "certificate_repair", "right": comparator,
                        "metric": metric, "paired_maps": 100,
                        "ci_method": "20000-draw paired map-cluster bootstrap",
                        "mean_difference": float(differences.mean()),
                        "std_difference": std,
                        "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                        "ci95_low": low, "ci95_high": high,
                    })
                comparison_index += 1
    write_csv(output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(output_directory / "paired_comparisons.csv", paired)

    summary_lookup = {
        (row["planner"], row["loss_probability"], row["policy"], row["metric"]): row
        for row in summary
    }
    pareto = []
    for planner in PLANNERS:
        for loss in LOSSES:
            points = {
                policy: (
                    float(summary_lookup[(planner, loss, policy, "attempted_bytes")]["mean"]),
                    float(summary_lookup[(planner, loss, policy, "seeker_success_rate")]["mean"]),
                )
                for policy in POLICIES
            }
            for policy, (traffic, reliability) in points.items():
                dominators = tuple(sorted(
                    other for other, (other_traffic, other_reliability) in points.items()
                    if other != policy
                    and other_traffic <= traffic and other_reliability >= reliability
                    and (other_traffic < traffic or other_reliability > reliability)
                ))
                pareto.append({
                    "planner": planner, "loss_probability": loss,
                    "policy": policy, "attempted_bytes": traffic,
                    "seeker_success_rate": reliability,
                    "pareto_efficient": not dominators,
                    "dominated_by": ";".join(dominators),
                })
    write_csv(output_directory / "pareto_frontier.csv", pareto)
    manifest = {
        "complete": True,
        "episodes": expected,
        "independent_maps_per_condition": 100,
        "unique_physical_layouts": 100,
        "primary_endpoint": "seeker_success_rate",
        "overall_csr_note": (
            "diagnostic only: the structured suite contains one annotated "
            "observer for each seeker"
        ),
        "planners": list(PLANNERS),
        "loss_probabilities": list(LOSSES),
        "policies": list(POLICIES),
        "confidence_interval": (
            "20,000-draw cluster bootstrap over independent maps; paired "
            "comparisons preserve the matched map and loss trace"
        ),
    }
    (output_directory / "analysis_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.input_directory, args.output_directory)
    print({"conditions": len(PLANNERS) * len(LOSSES) * len(POLICIES)})


if __name__ == "__main__":
    main()
