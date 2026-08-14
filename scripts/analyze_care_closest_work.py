#!/usr/bin/env python3
"""Audit codec-matched adaptations of CARE's closest conceptual baselines."""

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


RADII = (1, 2, 3)
PLANNERS = ("astar", "dstar_lite")
POLICIES = (
    "one_shot_delta", "retry_all_arq", "path_aware_top_k_repair",
    "single_cell_sensitivity_repair", "deadline_aware_repair",
    "ocbc_forward_simulation", "path_guided_compression",
    "rate_distortion_compression", "voi_repair", "certificate_repair",
)
METRICS = (
    "seeker_success_rate", "critical_pair_success_rate",
    "observer_success_rate", "completion_success_rate", "all_seekers_success",
    "episode_length", "attempted_bytes", "delivered_bytes",
    "attempted_control_bytes", "attempted_repair_bytes",
    "mean_path_truth_error", "task_aware_query_cells",
    "closest_work_planning_calls", "closest_work_simulation_samples",
    "task_aware_cpu_ms", "certificate_cpu_ms", "episode_cpu_ms",
)
PAIRED_METRICS = (
    "seeker_success_rate", "critical_pair_success_rate",
    "completion_success_rate", "episode_length", "attempted_bytes",
    "attempted_repair_bytes", "episode_cpu_ms",
)
COMPARISONS = tuple(
    [("certificate_repair", policy) for policy in POLICIES[:-1]]
    + [(policy, "one_shot_delta") for policy in POLICIES[2:-1]]
)
BOOTSTRAP_DRAWS = 20_000


def _bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    del seed
    return bootstrap_mean_ci(values, draws=BOOTSTRAP_DRAWS)


def _write(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty artifact: {path}")
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(input_directory: Path, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader((input_directory / "results.csv").open()))
    run = json.loads((input_directory / "summary.json").read_text())
    expected = 100 * len(RADII) * len(PLANNERS) * len(POLICIES)
    if len(rows) != expected or run.get("rows") != expected:
        raise ValueError(f"expected {expected} complete episodes, found {len(rows)}")
    if run.get("workers") != 32:
        raise ValueError("closest-work matrix was not executed with 32 workers")
    config = run.get("config", {})
    frozen = {
        "instance_family": "multifork_cluttered", "seed_count": 100,
        "map_size": 32, "num_agents": 8, "max_episode_steps": 25,
        "workers": 32, "certificate_max_cells": 8,
        "certificate_uncertainty_order": 2,
        "external_candidate_multiplier": 2, "ocbc_samples": 128,
        "algorithm_seed": 20260813, "digest_base_bytes": 16,
        "digest_entry_bytes": 6, "patch_base_bytes": 4,
    }
    for field, expected_value in frozen.items():
        if config.get(field) != expected_value:
            raise ValueError(
                f"unexpected frozen closest-work config "
                f"{field}={config.get(field)!r}"
            )
    sequence_checks = {
        "observation_radii": RADII, "planners": PLANNERS,
        "policies": POLICIES, "delay_steps": (0,),
    }
    for field, expected_values in sequence_checks.items():
        if tuple(config.get(field, ())) != expected_values:
            raise ValueError(f"closest-work config {field} differs from frozen design")
    if tuple(map(float, config.get("obstacle_densities", ()))) != (.2,):
        raise ValueError("closest-work matrix requires density 0.20")
    if tuple(map(float, config.get("loss_probabilities", ()))) != (.3,):
        raise ValueError("closest-work matrix requires 30% packet loss")
    # The task-aware cap is min(certificate_max_cells, wire budget capacity).
    query_cap_cells = min(
        int(config["certificate_max_cells"]),
        (int(config["control_bytes_per_agent_per_step"])
         - int(config["digest_base_bytes"]))
        // int(config["digest_entry_bytes"]),
    )
    if int(config["digest_base_bytes"]) + int(config["digest_entry_bytes"]) * query_cap_cells != 64:
        raise ValueError("closest-work matrix no longer has the declared 64-byte query cap")
    required = set(METRICS) | {"layout_seed", "network_seed", "layout_fingerprint"}
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"result schema lacks required fields: {sorted(missing)}")

    ordered_keys = tuple((str(seed), str(seed)) for seed in range(100))
    expected_keys = set(ordered_keys)
    groups: dict[tuple[int, str, str], dict[tuple[str, str], dict]] = defaultdict(dict)
    layouts: dict[tuple[int, str], set[str]] = defaultdict(set)
    layouts_across_radii: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        condition = int(row["observation_radius"]), row["planner"], row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate matched episode: {condition}, {key}")
        groups[condition][key] = row
        layouts[(int(row["observation_radius"]), row["layout_seed"])].add(row["layout_fingerprint"])
        layouts_across_radii[row["layout_seed"]].add(row["layout_fingerprint"])
        if (
            row["topology_family"] != "multifork_cluttered"
            or int(row["map_size"]) != 32 or int(row["num_agents"]) != 8
            or float(row["density"]) != .2
            or float(row["loss_probability"]) != .3
            or int(row["delay_steps"]) != 0
        ):
            raise ValueError("closest-work result row violates its frozen condition")
    expected_conditions = {
        (radius, planner, policy)
        for radius in RADII for planner in PLANNERS for policy in POLICIES
    }
    if set(groups) != expected_conditions:
        raise ValueError("condition grid differs from the frozen closest-work matrix")
    for condition, trials in groups.items():
        if set(trials) != expected_keys:
            raise ValueError(f"incomplete matched maps for {condition}")
    if any(len(values) != 1 for values in layouts.values()):
        raise ValueError("one radius/layout seed generated multiple physical maps")
    if set(layouts_across_radii) != {str(seed) for seed in range(100)}:
        raise ValueError("closest-work layout seeds are not exactly 0..99")
    if any(len(values) != 1 for values in layouts_across_radii.values()):
        raise ValueError("a layout seed changes physical geometry across FOV radii")
    for radius in RADII:
        fingerprints = {
            next(iter(layouts[(radius, str(seed))])) for seed in range(100)
        }
        if len(fingerprints) != 100:
            raise ValueError(f"radius {radius} does not contain 100 physical maps")

    summary: list[dict] = []
    for condition_index, condition in enumerate(sorted(groups)):
        radius, planner, policy = condition
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([float(groups[condition][key][metric]) for key in ordered_keys])
            low, high = _bootstrap(values, condition_index * 1000 + metric_index)
            summary.append({
                "observation_radius": radius, "fov": f"{2*radius+1}x{2*radius+1}",
                "planner": planner, "policy": policy, "metric": metric,
                "independent_maps": 100, "mean": float(values.mean()),
                "std": float(values.std(ddof=1)), "ci95_low": low,
                "ci95_high": high,
                "ci_method": f"{BOOTSTRAP_DRAWS}-draw map-cluster bootstrap",
            })

    paired: list[dict] = []
    comparison_index = 0
    for radius in RADII:
        for planner in PLANNERS:
            for left, right in COMPARISONS:
                for metric_index, metric in enumerate(PAIRED_METRICS):
                    differences = np.asarray([
                        float(groups[(radius, planner, left)][key][metric])
                        - float(groups[(radius, planner, right)][key][metric])
                        for key in ordered_keys
                    ])
                    low, high = _bootstrap(
                        differences, 1_000_000 + comparison_index * 100 + metric_index,
                    )
                    std = float(differences.std(ddof=1))
                    paired.append({
                        "observation_radius": radius,
                        "fov": f"{2*radius+1}x{2*radius+1}",
                        "planner": planner, "left": left, "right": right,
                        "metric": metric, "paired_maps": 100,
                        "mean_difference": float(differences.mean()),
                        "std_difference": std,
                        "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                        "ci95_low": low, "ci95_high": high,
                        "ci_method": f"{BOOTSTRAP_DRAWS}-draw paired map-cluster bootstrap",
                    })
                comparison_index += 1

    _write(output_directory / "summary_mean_std_ci.csv", summary)
    _write(output_directory / "paired_comparisons.csv", paired)
    manifest = {
        "complete": True, "episodes": expected, "workers": 32,
        "independent_maps_per_condition": 100,
        "primary_endpoint": "seeker_success_rate",
        "secondary_endpoint": "critical_pair_success_rate",
        "fovs": ["3x3", "5x5", "7x7"], "planners": list(PLANNERS),
        "policies": list(POLICIES), "loss_probability": .3, "delay_steps": 0,
        "comparison_scope": (
            "codec-matched adaptations, not exact reproductions of source systems; "
            "all use the same explicit binary map, query-patch codec, 64-byte query "
            "cap, link trace, planner and byte accounting"
        ),
        "confidence_interval": f"{BOOTSTRAP_DRAWS}-draw paired map-cluster bootstrap",
    }
    (output_directory / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.input_directory, args.output_directory)
    print("closest-work analysis complete")


if __name__ == "__main__":
    main()
