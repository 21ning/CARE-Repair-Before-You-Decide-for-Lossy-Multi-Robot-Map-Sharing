#!/usr/bin/env python3
"""Audit the matched CARE commitment-gate ablation with paired map inference."""

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
DELAYS = (0, 1, 2, 4)
POLICIES = (
    "certificate_repair_route_gate",
    "certificate_repair_no_commitment_gate",
)
GATED = "certificate_repair_route_gate"
UNGATED = "certificate_repair_no_commitment_gate"
METRICS = (
    "seeker_success_rate", "critical_pair_success_rate",
    "completion_success_rate", "observer_success_rate", "all_seekers_success",
    "instance_success_rate", "episode_length", "attempted_bytes",
    "delivered_bytes", "attempted_control_bytes", "delivered_control_bytes",
    "attempted_repair_bytes", "delivered_repair_bytes",
    "commitment_gate_checks", "commitment_gate_closed",
    "commitment_raw_query_cells", "commitment_suppressed_query_cells",
    "planning_cpu_ms", "certificate_cpu_ms", "episode_cpu_ms",
)
TIMING_FIELDS = {
    "planning_cpu_ms", "utility_trigger_cpu_ms", "certificate_cpu_ms",
    "task_aware_cpu_ms", "episode_cpu_ms",
}
BOOTSTRAP_DRAWS = 20_000
NONINFERIORITY_MARGIN = -0.02


def bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    """Bootstrap independent maps while preserving each policy pairing."""
    del seed
    return bootstrap_mean_ci(values, draws=BOOTSTRAP_DRAWS)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty analysis artifact: {path}")
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _validate_frozen_config(run: dict, rows: list[dict[str, str]]) -> None:
    expected = 100 * len(PLANNERS) * len(DELAYS) * len(POLICIES)
    if len(rows) != expected or run.get("rows") != expected:
        raise ValueError(f"expected {expected} complete episodes, found {len(rows)}")
    if run.get("workers") != 32:
        raise ValueError("commitment-gate ablation must execute with 32 workers")
    config = run.get("config", {})
    expected_config = {
        "seed_count": 100,
        "observation_radius": 2,
        "num_agents": 8,
        "workers": 32,
    }
    for field, expected_value in expected_config.items():
        if config.get(field) != expected_value:
            raise ValueError(f"unexpected frozen config {field}={config.get(field)!r}")
    if tuple(float(value) for value in config.get("obstacle_densities", ())) != (.2,):
        raise ValueError("commitment-gate ablation requires density 0.20")
    if tuple(float(value) for value in config.get("loss_probabilities", ())) != (.3,):
        raise ValueError("commitment-gate ablation requires 30% packet loss")
    if tuple(int(value) for value in config.get("delay_steps", ())) != DELAYS:
        raise ValueError("delay grid differs from the frozen 0/1/2/4 design")
    if tuple(config.get("planners", ())) != PLANNERS:
        raise ValueError("planner grid differs from the frozen A*/D* Lite design")
    if tuple(config.get("policies", ())) != POLICIES:
        raise ValueError("policy grid is not the strict CARE/gate-off pair")


def _negative_control(
    groups: dict[tuple[str, int, str], dict[tuple[str, str], dict[str, str]]],
    ordered_keys: tuple[tuple[str, str], ...],
) -> dict:
    """Require delay-zero policy outputs to match except CPU timing and label."""
    checked_fields: tuple[str, ...] | None = None
    compared_rows = 0
    for planner in PLANNERS:
        gated = groups[(planner, 0, GATED)]
        ungated = groups[(planner, 0, UNGATED)]
        for key in ordered_keys:
            left = gated[key]
            right = ungated[key]
            if set(left) != set(right):
                raise ValueError("delay-zero policy rows have different schemas")
            fields = tuple(sorted(set(left) - TIMING_FIELDS - {"policy"}))
            if checked_fields is None:
                checked_fields = fields
            elif fields != checked_fields:
                raise ValueError("delay-zero negative-control schema is not stable")
            mismatches = [field for field in fields if left[field] != right[field]]
            if mismatches:
                raise ValueError(
                    "delay-zero gate-off negative control failed for "
                    f"{planner}, map={key}: {mismatches[:8]}"
                )
            compared_rows += 1
    return {
        "pass": True,
        "delay_steps": 0,
        "matched_policy_pairs": compared_rows,
        "non_timing_differences": 0,
        "excluded_fields": sorted(TIMING_FIELDS | {"policy"}),
        "compared_fields": list(checked_fields or ()),
    }


def analyze(input_directory: Path, output_directory: Path) -> None:
    output_directory.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader((input_directory / "results.csv").open()))
    run = json.loads((input_directory / "summary.json").read_text())
    _validate_frozen_config(run, rows)
    required = set(METRICS) | {
        "layout_seed", "network_seed", "layout_fingerprint", "planner",
        "policy", "observation_radius", "density", "loss_probability",
        "delay_steps",
    }
    missing = required - set(rows[0])
    if missing:
        raise ValueError(f"result schema lacks gate-ablation fields: {sorted(missing)}")
    fixed = {
        (
            int(row["observation_radius"]), float(row["density"]),
            float(row["loss_probability"]),
        )
        for row in rows
    }
    if fixed != {(2, .2, .3)}:
        raise ValueError(f"unexpected fixed experimental conditions: {fixed}")

    ordered_keys = tuple((str(seed), str(seed)) for seed in range(100))
    expected_keys = set(ordered_keys)
    groups: dict[
        tuple[str, int, str], dict[tuple[str, str], dict[str, str]]
    ] = defaultdict(dict)
    layouts: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        condition = row["planner"], int(row["delay_steps"]), row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate matched episode: {condition}, {key}")
        groups[condition][key] = row
        layouts[row["layout_seed"]].add(row["layout_fingerprint"])
    expected_conditions = {
        (planner, delay, policy)
        for planner in PLANNERS for delay in DELAYS for policy in POLICIES
    }
    if set(groups) != expected_conditions:
        raise ValueError("condition grid differs from the frozen gate ablation")
    for condition, trials in groups.items():
        if set(trials) != expected_keys:
            raise ValueError(f"incomplete paired-map condition: {condition}")
    if set(layouts) != {str(seed) for seed in range(100)}:
        raise ValueError("layout seeds are not exactly 0..99")
    if any(len(fingerprints) != 1 for fingerprints in layouts.values()):
        raise ValueError("one layout seed generated multiple physical maps")
    if len({next(iter(value)) for value in layouts.values()}) != 100:
        raise ValueError("matrix does not contain 100 unique physical maps")

    for row in rows:
        checks = float(row["commitment_gate_checks"])
        closed = float(row["commitment_gate_closed"])
        raw = float(row["commitment_raw_query_cells"])
        suppressed = float(row["commitment_suppressed_query_cells"])
        if min(checks, closed, raw, suppressed) < 0 or closed > checks or suppressed > raw:
            raise ValueError("invalid commitment-gate counter values")
        if row["policy"] == UNGATED and suppressed != 0:
            raise ValueError("gate-off policy suppressed commitment query cells")

    negative_control = _negative_control(groups, ordered_keys)

    summary: list[dict] = []
    for condition_index, condition in enumerate(sorted(groups)):
        planner, delay, policy = condition
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([
                float(groups[condition][key][metric]) for key in ordered_keys
            ])
            low, high = bootstrap(values, condition_index * 1000 + metric_index)
            summary.append({
                "planner": planner, "delay_steps": delay, "policy": policy,
                "metric": metric, "independent_maps": 100,
                "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
                "ci_method": f"{BOOTSTRAP_DRAWS}-draw map-cluster bootstrap",
            })

    paired: list[dict] = []
    pair_index = 0
    for planner in PLANNERS:
        for delay in DELAYS:
            left = groups[(planner, delay, GATED)]
            right = groups[(planner, delay, UNGATED)]
            for metric_index, metric in enumerate(METRICS):
                differences = np.asarray([
                    float(left[key][metric]) - float(right[key][metric])
                    for key in ordered_keys
                ])
                low, high = bootstrap(
                    differences, 1_000_000 + pair_index * 100 + metric_index,
                )
                std = float(differences.std(ddof=1))
                paired.append({
                    "planner": planner, "delay_steps": delay,
                    "left": GATED, "right": UNGATED, "metric": metric,
                    "paired_maps": 100, "mean_difference": float(differences.mean()),
                    "std_difference": std,
                    "paired_effect_dz": (
                        float(differences.mean() / std) if std else 0.0
                    ),
                    "ci95_low": low, "ci95_high": high,
                    "ci_method": (
                        f"{BOOTSTRAP_DRAWS}-draw paired map-cluster bootstrap"
                    ),
                })
            pair_index += 1

    paired_lookup = {
        (row["planner"], row["delay_steps"], row["metric"]): row
        for row in paired
    }
    summary_lookup = {
        (row["planner"], row["delay_steps"], row["policy"], row["metric"]): row
        for row in summary
    }
    positive_delay_audit = []
    for planner in PLANNERS:
        for delay in DELAYS[1:]:
            seeker = paired_lookup[(planner, delay, "seeker_success_rate")]
            traffic = paired_lookup[(planner, delay, "attempted_bytes")]
            closed = summary_lookup[(planner, delay, GATED, "commitment_gate_closed")]
            suppressed = summary_lookup[
                (planner, delay, GATED, "commitment_suppressed_query_cells")
            ]
            seeker_noninferior = seeker["ci95_low"] >= NONINFERIORITY_MARGIN
            traffic_no_higher = traffic["ci95_high"] <= 0.0
            traffic_reduction_detected = traffic["ci95_high"] < 0.0
            gate_active = closed["mean"] > 0.0 and suppressed["mean"] > 0.0
            positive_delay_audit.append({
                "planner": planner, "delay_steps": delay,
                "seeker_noninferiority_margin": NONINFERIORITY_MARGIN,
                "delta_seeker_success": seeker["mean_difference"],
                "delta_seeker_ci95_low": seeker["ci95_low"],
                "delta_seeker_ci95_high": seeker["ci95_high"],
                "seeker_noninferior": bool(seeker_noninferior),
                "delta_attempted_bytes": traffic["mean_difference"],
                "delta_attempted_bytes_ci95_low": traffic["ci95_low"],
                "delta_attempted_bytes_ci95_high": traffic["ci95_high"],
                "traffic_no_higher": bool(traffic_no_higher),
                "traffic_reduction_detected": bool(traffic_reduction_detected),
                "mean_gate_closed": closed["mean"],
                "mean_suppressed_query_cells": suppressed["mean"],
                "gate_active": bool(gate_active),
                "condition_pass": bool(seeker_noninferior and traffic_no_higher),
            })
    gate_audit = {
        "delay_zero_negative_control": negative_control,
        "positive_delay_conditions": positive_delay_audit,
        "decision_rule": {
            "seeker_noninferiority": "paired 95% CI lower bound >= -0.02",
            "traffic_nonincrease": "paired attempted-byte 95% CI upper bound <= 0",
            "incremental_gate_value": (
                "all positive-delay cells pass noninferiority and traffic "
                "nonincrease; at least one closed-gate cell has a strict "
                "traffic reduction"
            ),
        },
        "all_positive_delay_conditions_pass": all(
            row["condition_pass"] for row in positive_delay_audit
        ),
        "any_gate_active": any(row["gate_active"] for row in positive_delay_audit),
        "any_strict_traffic_reduction": any(
            row["traffic_reduction_detected"] for row in positive_delay_audit
        ),
    }
    gate_audit["supports_incremental_commitment_gate_value"] = bool(
        gate_audit["all_positive_delay_conditions_pass"]
        and gate_audit["any_gate_active"]
        and gate_audit["any_strict_traffic_reduction"]
    )

    write_csv(output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(output_directory / "paired_comparisons.csv", paired)
    (output_directory / "gate_audit.json").write_text(
        json.dumps(gate_audit, indent=2) + "\n"
    )
    manifest = {
        "complete": True, "episodes": len(rows), "workers": 32,
        "independent_maps_per_condition": 100, "unique_physical_layouts": 100,
        "fov": "5x5", "loss_probability": .3,
        "delays": list(DELAYS), "planners": list(PLANNERS),
        "policies": list(POLICIES),
        "primary_endpoints": [
            "seeker_success_rate", "critical_pair_success_rate",
        ],
        "comparison": (
            "RouteWitness-Gated minus RouteWitness-Ungated; neither variant "
            "is final CARE"
        ),
        "confidence_interval": (
            f"{BOOTSTRAP_DRAWS}-draw map-cluster bootstrap; paired differences "
            "preserve map and deterministic loss trace"
        ),
        "seeker_noninferiority_margin": NONINFERIORITY_MARGIN,
        "delay_zero_negative_control": "all non-CPU-timing fields exactly equal",
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
    print("commitment-gate analysis complete")


if __name__ == "__main__":
    main()
