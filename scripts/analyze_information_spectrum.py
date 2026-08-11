#!/usr/bin/env python3
"""Audit the no-communication--CARE--continuous-sync spectrum."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


RADII = (1, 2, 3)
PLANNERS = ("astar", "dstar_lite")
POLICIES = ("no_communication", "certificate_repair", "periodic_full_sync")
METRICS = (
    "completion_success_rate", "episode_length", "attempted_bytes",
    "attempted_data_bytes", "attempted_control_bytes", "attempted_repair_bytes",
    "mean_replica_error", "mean_path_truth_error", "episode_cpu_ms",
)
BOOTSTRAP_DRAWS = 20_000


def bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(values), (BOOTSTRAP_DRAWS, len(values)))
    means = values[indices].mean(axis=1)
    return tuple(float(value) for value in np.quantile(means, (.025, .975)))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def analyze(input_directory: Path, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader((input_directory / "results.csv").open()))
    run_summary = json.loads((input_directory / "summary.json").read_text())
    expected = 100 * len(RADII) * len(PLANNERS) * len(POLICIES)
    if len(rows) != expected or run_summary.get("rows") != expected:
        raise ValueError(f"expected {expected} complete episodes")
    if run_summary.get("workers") != 32:
        raise ValueError("frozen information-spectrum run must use 32 workers")
    config = run_summary.get("config", {})
    if config.get("sync_interval_steps") != 1:
        raise ValueError("Always Communicate requires full synchronization every step")
    fixed = {
        (float(row["density"]), float(row["loss_probability"]), int(row["delay_steps"]))
        for row in rows
    }
    if fixed != {(.2, .3, 0)}:
        raise ValueError(f"unexpected fixed conditions: {fixed}")

    keys = tuple((str(seed), str(seed)) for seed in range(100))
    expected_keys = set(keys)
    groups: dict[tuple[int, str, str], dict[tuple[str, str], dict]] = defaultdict(dict)
    layouts: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        condition = int(row["observation_radius"]), row["planner"], row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate trial: {condition}, {key}")
        groups[condition][key] = row
        layouts[row["layout_seed"]].add(row["layout_fingerprint"])
    for condition in (
        (radius, planner, policy)
        for radius in RADII for planner in PLANNERS for policy in POLICIES
    ):
        if set(groups[condition]) != expected_keys:
            raise ValueError(f"incomplete matched condition: {condition}")
    if set(layouts) != {str(seed) for seed in range(100)}:
        raise ValueError("layout seeds are not exactly 0..99")
    if any(len(fingerprints) != 1 for fingerprints in layouts.values()):
        raise ValueError("one layout seed maps to multiple physical layouts")
    if len({next(iter(value)) for value in layouts.values()}) != 100:
        raise ValueError("matrix does not contain 100 unique physical layouts")

    no_communication = (
        row for row in rows if row["policy"] == "no_communication"
    )
    if any(int(row["attempted_bytes"]) != 0 for row in no_communication):
        raise ValueError("No Communication attempted a non-zero packet")

    summary = []
    for condition_index, condition in enumerate(sorted(groups)):
        radius, planner, policy = condition
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([
                float(groups[condition][key][metric]) for key in keys
            ])
            low, high = bootstrap(values, condition_index * 100 + metric_index)
            summary.append({
                "observation_radius": radius,
                "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                "planner": planner, "policy": policy, "metric": metric,
                "independent_maps": 100, "mean": float(values.mean()),
                "std": float(values.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
                "ci_method": f"{BOOTSTRAP_DRAWS}-draw map-cluster bootstrap",
            })

    paired = []
    comparisons = (
        ("certificate_repair", "no_communication"),
        ("periodic_full_sync", "certificate_repair"),
        ("periodic_full_sync", "no_communication"),
    )
    pair_index = 0
    for radius in RADII:
        for planner in PLANNERS:
            for left_policy, right_policy in comparisons:
                for metric_index, metric in enumerate(METRICS):
                    differences = np.asarray([
                        float(groups[(radius, planner, left_policy)][key][metric])
                        - float(groups[(radius, planner, right_policy)][key][metric])
                        for key in keys
                    ])
                    low, high = bootstrap(
                        differences, 100_000 + pair_index * 100 + metric_index,
                    )
                    std = float(differences.std(ddof=1))
                    paired.append({
                        "observation_radius": radius,
                        "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                        "planner": planner, "left": left_policy,
                        "right": right_policy, "metric": metric,
                        "paired_maps": 100,
                        "mean_difference": float(differences.mean()),
                        "std_difference": std,
                        "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                        "ci95_low": low, "ci95_high": high,
                        "ci_method": f"{BOOTSTRAP_DRAWS}-draw paired map-cluster bootstrap",
                    })
                pair_index += 1

    write_csv(output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(output_directory / "paired_comparisons.csv", paired)
    manifest = {
        "complete": True, "episodes": expected, "workers": 32,
        "trace_rows": run_summary["trace_rows"],
        "independent_maps_per_condition": 100,
        "unique_physical_layouts": 100,
        "fovs": ["3x3", "5x5", "7x7"],
        "planners": list(PLANNERS), "policies": list(POLICIES),
        "loss_probability": .3, "delay_steps": 0,
        "always_communicate_contract": (
            "continuous full-replica synchronization every step (K=1), under "
            "the same lossy link, delay, data cap, cell codec and byte accounting"
        ),
        "confidence_interval": (
            f"{BOOTSTRAP_DRAWS}-draw map-cluster bootstrap; paired differences "
            "preserve map and deterministic loss trace"
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
    print("information-spectrum analysis complete")


if __name__ == "__main__":
    main()
