#!/usr/bin/env python3
"""Audit and analyze CARE across matched 3x3, 5x5 and 7x7 observations."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

try:
    from bootstrap_ci import bootstrap_mean_ci, bootstrap_ratio_ci
except ModuleNotFoundError:
    from scripts.bootstrap_ci import bootstrap_mean_ci, bootstrap_ratio_ci

try:
    from structured_role_metrics import ROLE_PROVENANCE, metric_value
except ModuleNotFoundError:  # Imported as ``scripts.analyze_*`` in tests.
    from scripts.structured_role_metrics import ROLE_PROVENANCE, metric_value


RADII = (1, 2, 3)
PLANNERS = ("astar", "dstar_lite")
POLICIES = (
    "one_shot_delta", "retry_all_arq", "path_weighted_arq",
    "periodic_full_sync", "mismatch_triggered_full_repair",
    "action_triggered_repair", "full_replica_repair",
    "utility_triggered_repair", "deadline_aware_repair", "certificate_repair",
)
METRICS = (
    "seeker_success_rate", "completion_success_rate", "instance_success_rate", "episode_length",
    "attempted_bytes", "attempted_control_bytes", "attempted_repair_bytes",
    "mean_replica_error", "mean_path_repairable_error", "mean_path_truth_error",
    "planning_cpu_ms", "utility_trigger_cpu_ms", "certificate_cpu_ms",
    "episode_cpu_ms", "certificate_candidate_cap_hit_rate",
    "mean_uncapped_certificate_candidates",
)
EVENT_METRICS = (
    ("critical_peer_observation_step", "mean_critical_peer_observation_step", "critical_peer_observation_events"),
    ("critical_self_observation_step", "mean_critical_self_observation_step", "critical_self_observation_events"),
    ("route_commitment_step", "mean_route_commitment_step", "critical_route_commitment_events"),
    ("visibility_gap_steps", "mean_visibility_gap_steps", "critical_self_observation_events"),
    ("usable_communication_window_steps", "mean_usable_communication_window_steps", "critical_route_commitment_events"),
    ("decision_before_self_observation_rate", "decision_before_self_observation_rate", "critical_self_observation_events"),
)


def bootstrap_mean(values: np.ndarray, seed: int) -> tuple[float, float]:
    del seed
    return bootstrap_mean_ci(values)


def bootstrap_ratio(numerators: np.ndarray, denominators: np.ndarray, seed: int) -> tuple[float, float]:
    del seed
    return bootstrap_ratio_ci(numerators, denominators)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def analyze(input_directory: Path, output_directory: Path) -> dict:
    output_directory.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader((input_directory / "results.csv").open()))
    expected = 100 * len(RADII) * len(PLANNERS) * len(POLICIES)
    if len(rows) != expected:
        raise ValueError(f"expected {expected} complete rows, found {len(rows)}")
    if {(float(row["density"]), float(row["loss_probability"]), int(row["delay_steps"])) for row in rows} != {(.2, .3, 0)}:
        raise ValueError("unexpected density, loss or delay in observation-radius matrix")

    ordered_keys = tuple((str(seed), str(seed)) for seed in range(100))
    expected_keys = set(ordered_keys)
    groups: dict[tuple[int, str, str], dict[tuple[str, str], dict]] = defaultdict(dict)
    layout_by_seed: dict[str, set[str]] = defaultdict(set)
    instance_by_seed: dict[str, set[tuple[int, str]]] = defaultdict(set)
    for row in rows:
        radius = int(row["observation_radius"])
        condition = radius, row["planner"], row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate row for {condition}, {key}")
        groups[condition][key] = row
        layout_by_seed[row["layout_seed"]].add(row["layout_fingerprint"])
        instance_by_seed[row["layout_seed"]].add((radius, row["instance_fingerprint"]))
    for condition in ((r, p, m) for r in RADII for p in PLANNERS for m in POLICIES):
        if set(groups[condition]) != expected_keys:
            raise ValueError(f"incomplete matched condition {condition}")
    if set(layout_by_seed) != {str(seed) for seed in range(100)}:
        raise ValueError("layout seeds are not exactly 0..99")
    if any(len(values) != 1 for values in layout_by_seed.values()):
        raise ValueError("sensor-radius conditions do not share identical layouts")
    if len({next(iter(values)) for values in layout_by_seed.values()}) != 100:
        raise ValueError("fewer than 100 unique map layouts")
    if any(len(values) != 3 or {radius for radius, _ in values} != set(RADII) for values in instance_by_seed.values()):
        raise ValueError("each layout must have three sensor-specific instance fingerprints")

    summary = []
    for condition_index, condition in enumerate(sorted(groups)):
        radius, planner, policy = condition
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([
                metric_value(groups[condition][key], metric)
                for key in ordered_keys
                if metric == "seeker_success_rate"
                or groups[condition][key].get(metric, "") != ""
            ])
            if not len(values):
                continue
            low, high = bootstrap_mean(values, condition_index * 100 + metric_index)
            summary.append({
                "observation_radius": radius, "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                "planner": planner, "policy": policy, "metric": metric,
                "independent_maps": len(values), "mean": float(values.mean()),
                "std": float(values.std(ddof=1)) if len(values) > 1 else 0.0,
                "ci95_low": low, "ci95_high": high,
            })

    event_summary = []
    event_index = 0
    for condition in sorted(groups):
        radius, planner, policy = condition
        condition_rows = [groups[condition][key] for key in ordered_keys]
        total_pairs = sum(int(row["critical_pair_count"]) for row in condition_rows)
        for label, mean_field, count_field in EVENT_METRICS:
            denominators = np.asarray([int(row[count_field]) for row in condition_rows], dtype=float)
            numerators = np.asarray([
                (float(row[mean_field]) * int(row[count_field])) if row[mean_field] != "" else 0.0
                for row in condition_rows
            ])
            denominator = float(denominators.sum())
            if not denominator:
                event_index += 1
                continue
            mean = float(numerators.sum() / denominator)
            low, high = bootstrap_ratio(numerators, denominators, 100_000 + event_index)
            event_summary.append({
                "observation_radius": radius, "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                "planner": planner, "policy": policy, "metric": label,
                "observed_events": int(denominator), "possible_events": total_pairs,
                "coverage": denominator / total_pairs if total_pairs else 0.0,
                "event_weighted_mean": mean, "ci95_low": low, "ci95_high": high,
            })
            event_index += 1
        hits = np.asarray([int(row["certificate_candidate_cap_hits"]) for row in condition_rows], dtype=float)
        checks = np.asarray([int(row["certificate_candidate_cap_checks"]) for row in condition_rows], dtype=float)
        if checks.sum():
            low, high = bootstrap_ratio(hits, checks, 200_000 + event_index)
            event_summary.append({
                "observation_radius": radius, "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                "planner": planner, "policy": policy, "metric": "certificate_candidate_cap_hit_rate",
                "observed_events": int(checks.sum()), "possible_events": int(checks.sum()),
                "coverage": 1.0, "event_weighted_mean": float(hits.sum() / checks.sum()),
                "ci95_low": low, "ci95_high": high,
            })
        event_index += 1

    paired = []
    comparison_index = 0
    for radius in RADII:
        for planner in PLANNERS:
            care = groups[(radius, planner, "certificate_repair")]
            for comparator in POLICIES[:-1]:
                other = groups[(radius, planner, comparator)]
                for metric_index, metric in enumerate((
                    "seeker_success_rate", "completion_success_rate",
                    "instance_success_rate", "episode_length", "attempted_bytes",
                    "attempted_control_bytes", "attempted_repair_bytes",
                    "mean_replica_error", "mean_path_repairable_error",
                    "mean_path_truth_error", "planning_cpu_ms",
                    "utility_trigger_cpu_ms", "certificate_cpu_ms",
                )):
                    differences = np.asarray([
                        metric_value(care[key], metric) - metric_value(other[key], metric)
                        for key in ordered_keys
                    ])
                    low, high = bootstrap_mean(differences, 300_000 + comparison_index * 100 + metric_index)
                    std = float(differences.std(ddof=1))
                    paired.append({
                        "observation_radius": radius, "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                        "planner": planner, "left": "certificate_repair", "right": comparator,
                        "metric": metric, "paired_maps": 100,
                        "mean_difference": float(differences.mean()), "std_difference": std,
                        "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                        "ci95_low": low, "ci95_high": high,
                    })
                comparison_index += 1

    interactions = []
    for planner_index, planner in enumerate(PLANNERS):
        for metric_index, metric in enumerate(("seeker_success_rate", "attempted_bytes")):
            gains = {
                radius: np.asarray([
                    metric_value(groups[(radius, planner, "certificate_repair")][key], metric)
                    - metric_value(groups[(radius, planner, "one_shot_delta")][key], metric)
                    for key in ordered_keys
                ]) for radius in RADII
            }
            for pair_index, (left, right) in enumerate(((1, 2), (2, 3), (1, 3))):
                values = gains[left] - gains[right]
                low, high = bootstrap_mean(values, 500_000 + planner_index * 100 + metric_index * 10 + pair_index)
                interactions.append({
                    "planner": planner, "metric": metric,
                    "left_radius": left, "right_radius": right,
                    "interpretation": "(CARE-One-shot at left) - (CARE-One-shot at right)",
                    "paired_maps": 100, "mean_difference": float(values.mean()),
                    "std_difference": float(values.std(ddof=1)),
                    "ci95_low": low, "ci95_high": high,
                })

    write_csv(output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(output_directory / "paired_comparisons.csv", paired)
    write_csv(output_directory / "causal_timing_and_cap.csv", event_summary)
    write_csv(output_directory / "radius_interactions.csv", interactions)
    manifest = {
        "complete": True, "episodes": expected, "independent_layouts": 100,
        "fovs": ["3x3", "5x5", "7x7"], "primary_fov": "5x5",
        "planners": list(PLANNERS), "policies": list(POLICIES),
        "matching": "layout fingerprint and network seed held fixed across observation radii and policies",
        "confidence_interval": "20,000-draw map-cluster bootstrap; paired differences preserve layout and loss trace",
        "primary_reliability_endpoint": "derived seeker CSR",
        "role_metric_provenance": ROLE_PROVENANCE,
    }
    (output_directory / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.input_directory, args.output_directory), indent=2))


if __name__ == "__main__":
    main()
