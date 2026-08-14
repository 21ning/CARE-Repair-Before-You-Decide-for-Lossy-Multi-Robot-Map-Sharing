#!/usr/bin/env python3
"""Audit and analyze published reconciliation baselines against CARE."""

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


PLANNERS = ("astar", "dstar_lite")
LOSSES = (0.0, .1, .2, .3, .4, .5)
POLICIES = (
    "one_shot_delta", "retry_all_arq", "scuttlebutt_depth",
    "merkle_anti_entropy", "iblt_reconciliation", "certificate_repair",
)
EXTERNAL = ("scuttlebutt_depth", "merkle_anti_entropy", "iblt_reconciliation")
METRICS = (
    "seeker_success_rate", "completion_success_rate", "instance_success_rate", "episode_length",
    "attempted_bytes", "attempted_data_bytes", "attempted_control_bytes",
    "attempted_repair_bytes", "mean_replica_error", "mean_path_truth_error",
    "scuttle_digest_exchanges", "scuttle_patch_updates",
    "merkle_nodes_compared", "merkle_leaf_repairs",
    "iblt_decode_attempts", "iblt_decode_successes", "iblt_patch_updates",
    "episode_cpu_ms",
)
BOOTSTRAP_DRAWS = 20_000


def bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    del seed
    return bootstrap_mean_ci(values, draws=BOOTSTRAP_DRAWS)


def bootstrap_ratio(
    numerators: np.ndarray, denominators: np.ndarray, seed: int,
) -> tuple[float, float]:
    del seed
    return bootstrap_ratio_ci(numerators, denominators, draws=BOOTSTRAP_DRAWS)


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
    radii = tuple(sorted({int(row["observation_radius"]) for row in rows}))
    if not radii or any(radius not in {1, 2, 3} for radius in radii):
        raise ValueError(f"unexpected observation radii: {radii}")
    expected = 100 * len(radii) * len(PLANNERS) * len(LOSSES) * len(POLICIES)
    if len(rows) != expected:
        raise ValueError(f"expected {expected} complete rows, found {len(rows)}")

    fingerprints_by_seed: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        fingerprints_by_seed[row["layout_seed"]].add(row["layout_fingerprint"])
    if set(fingerprints_by_seed) != {str(seed) for seed in range(100)}:
        raise ValueError("layout seed set is not exactly 0..99")
    if any(len(values) != 1 for values in fingerprints_by_seed.values()):
        raise ValueError("one layout seed maps to multiple physical layouts")
    if len({next(iter(values)) for values in fingerprints_by_seed.values()}) != 100:
        raise ValueError("the matrix does not contain 100 unique physical layouts")

    groups: dict[tuple[int, str, float, str], dict[tuple[str, str], dict]] = defaultdict(dict)
    for row in rows:
        condition = (
            int(row["observation_radius"]), row["planner"],
            float(row["loss_probability"]), row["policy"],
        )
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate trial {condition}, {key}")
        groups[condition][key] = row
    ordered_keys = tuple((str(seed), str(seed)) for seed in range(100))
    expected_keys = set(ordered_keys)
    for condition in (
        (radius, planner, loss, policy)
        for radius in radii for planner in PLANNERS
        for loss in LOSSES for policy in POLICIES
    ):
        if set(groups[condition]) != expected_keys:
            raise ValueError(f"incomplete condition: {condition}")

    summary = []
    for condition_index, condition in enumerate(sorted(groups)):
        radius, planner, loss, policy = condition
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([
                metric_value(groups[condition][key], metric) for key in ordered_keys
            ])
            low, high = bootstrap(values, condition_index * 100 + metric_index)
            summary.append({
                "observation_radius": radius, "planner": planner,
                "loss_probability": loss, "policy": policy,
                "metric": metric, "independent_maps": 100,
                "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
                "ci_method": f"{BOOTSTRAP_DRAWS}-draw map-cluster bootstrap",
            })

    comparisons = (
        tuple(("certificate_repair", policy) for policy in POLICIES[:-1])
        + tuple((policy, "one_shot_delta") for policy in EXTERNAL)
    )
    paired = []
    comparison_index = 0
    for radius in radii:
        for planner in PLANNERS:
            for loss in LOSSES:
                for left_policy, right_policy in comparisons:
                    left = groups[(radius, planner, loss, left_policy)]
                    right = groups[(radius, planner, loss, right_policy)]
                    for metric_index, metric in enumerate(METRICS):
                        differences = np.asarray([
                            metric_value(left[key], metric) - metric_value(right[key], metric)
                            for key in ordered_keys
                        ])
                        low, high = bootstrap(
                            differences,
                            100_000 + comparison_index * len(METRICS) + metric_index,
                        )
                        std = float(differences.std(ddof=1))
                        paired.append({
                            "observation_radius": radius, "planner": planner,
                            "loss_probability": loss,
                            "left": left_policy, "right": right_policy,
                            "metric": metric, "paired_maps": 100,
                            "mean_difference": float(differences.mean()),
                            "std_difference": std,
                            "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                            "ci95_low": low, "ci95_high": high,
                            "ci_method": f"{BOOTSTRAP_DRAWS}-draw paired map-cluster bootstrap",
                        })
                    comparison_index += 1

    diagnostics = []
    for radius_index, radius in enumerate(radii):
        for planner_index, planner in enumerate(PLANNERS):
            for loss_index, loss in enumerate(LOSSES):
                trials = groups[(radius, planner, loss, "iblt_reconciliation")]
                successes = np.asarray([
                    float(trials[key]["iblt_decode_successes"]) for key in ordered_keys
                ])
                attempts = np.asarray([
                    float(trials[key]["iblt_decode_attempts"]) for key in ordered_keys
                ])
                low, high = bootstrap_ratio(
                    successes, attempts,
                    500_000 + radius_index * 1_000 + planner_index * 100 + loss_index,
                )
                total_attempts = float(attempts.sum())
                diagnostics.append({
                    "observation_radius": radius, "planner": planner,
                    "loss_probability": loss,
                    "diagnostic": "iblt_decode_success_rate",
                    "numerator": float(successes.sum()), "denominator": total_attempts,
                    "ratio": float(successes.sum() / total_attempts) if total_attempts else 0.0,
                    "ci95_low": low, "ci95_high": high,
                    "ci_method": f"{BOOTSTRAP_DRAWS}-draw map-cluster ratio bootstrap",
                })

    write_csv(output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(output_directory / "paired_comparisons.csv", paired)
    write_csv(output_directory / "protocol_diagnostics.csv", diagnostics)
    manifest = {
        "complete": True,
        "episodes": expected,
        "independent_maps_per_condition": 100,
        "unique_physical_layouts": 100,
        "observation_radii": list(radii),
        "planners": list(PLANNERS), "loss_probabilities": list(LOSSES),
        "policies": list(POLICIES), "external_published_baselines": list(EXTERNAL),
        "confidence_interval": (
            f"{BOOTSTRAP_DRAWS}-draw map-cluster bootstrap; paired comparisons "
            "preserve map and deterministic loss trace"
        ),
        "primary_reliability_endpoint": "derived seeker CSR",
        "role_metric_provenance": ROLE_PROVENANCE,
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
    print("external reconciliation analysis complete")


if __name__ == "__main__":
    main()
