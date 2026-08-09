#!/usr/bin/env python3
"""Audit CARE's 100-map ablations and generalization extensions."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np


METRICS = (
    "completion_success_rate", "instance_success_rate", "episode_length",
    "attempted_bytes", "mean_path_truth_error", "certificate_candidate_cap_hit_rate",
    "episode_cpu_ms",
)
ABLATION_METRICS = (
    "completion_success_rate", "attempted_bytes", "mean_path_truth_error",
    "certificate_candidate_cap_hit_rate", "episode_cpu_ms",
)


def bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(values, (20_000, len(values)), replace=True).mean(axis=1)
    return tuple(float(value) for value in np.quantile(means, (.025, .975)))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def _trial_count(config: dict) -> int:
    seeds = len(config.get("seeds", ())) or int(config["seed_count"])
    return (
        seeds * len(config["obstacle_densities"]) * len(config["loss_probabilities"])
        * len(config["delay_steps"]) * len(config.get("planners", [config.get("planner", "astar")]))
        * len(config["policies"]) * len(config.get("observation_radii", [config.get("observation_radius")]))
    )


def _groups(rows: list[dict]) -> dict[tuple, dict[tuple[str, str], dict]]:
    groups: dict[tuple, dict[tuple[str, str], dict]] = defaultdict(dict)
    for row in rows:
        condition = (
            row["planner"], float(row["density"]), float(row["loss_probability"]),
            int(row["delay_steps"]), int(row["observation_radius"]), row["policy"],
        )
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate condition/key: {condition}, {key}")
        groups[condition][key] = row
    return groups


def analyze(input_directory: Path, primary_directory: Path, output_directory: Path) -> dict:
    output_directory.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((input_directory / "manifest.json").read_text())
    expected_keys = {(str(seed), str(seed)) for seed in range(100)}
    summary, paired = [], []
    study_groups: dict[str, dict] = {}
    summary_index = paired_index = 0
    total_rows = 0
    for record in manifest["studies"]:
        name, config = record["study"], record["config"]
        rows = list(csv.DictReader((input_directory / name / "results.csv").open()))
        expected_rows = _trial_count(config)
        if len(rows) != expected_rows or record["rows"] != expected_rows:
            raise ValueError(f"{name}: expected {expected_rows} rows, found {len(rows)}")
        total_rows += len(rows)
        layout_by_seed: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            layout_by_seed[row["layout_seed"]].add(row["layout_fingerprint"])
        if set(layout_by_seed) != {str(seed) for seed in range(100)}:
            raise ValueError(f"{name}: layout seeds are not exactly 0..99")
        if any(len(values) != 1 for values in layout_by_seed.values()):
            raise ValueError(f"{name}: a layout seed maps to multiple layouts")
        if len({next(iter(values)) for values in layout_by_seed.values()}) != 100:
            raise ValueError(f"{name}: fewer than 100 independent layouts")
        groups = _groups(rows)
        study_groups[name] = groups
        for condition, trials in sorted(groups.items()):
            if set(trials) != expected_keys:
                raise ValueError(f"{name}: incomplete condition {condition}")
            planner, density, loss, delay, radius, policy = condition
            for metric_index, metric in enumerate(METRICS):
                values = np.asarray([float(trials[key][metric]) for key in sorted(expected_keys)])
                low, high = bootstrap(values, summary_index * 100 + metric_index)
                summary.append({
                    "study": name, "planner": planner, "density": density,
                    "loss_probability": loss, "delay_steps": delay,
                    "observation_radius": radius, "policy": policy, "metric": metric,
                    "independent_maps": 100, "mean": float(values.mean()),
                    "std": float(values.std(ddof=1)), "ci95_low": low, "ci95_high": high,
                })
            summary_index += 1
        by_context: dict[tuple, dict[str, dict]] = defaultdict(dict)
        for condition, trials in groups.items():
            by_context[condition[:-1]][condition[-1]] = trials
        for context, policies in sorted(by_context.items()):
            if "certificate_repair" not in policies:
                continue
            care = policies["certificate_repair"]
            for comparator, other in sorted(policies.items()):
                if comparator == "certificate_repair":
                    continue
                for metric_index, metric in enumerate(ABLATION_METRICS):
                    differences = np.asarray([
                        float(care[key][metric]) - float(other[key][metric]) for key in sorted(expected_keys)
                    ])
                    low, high = bootstrap(differences, 200_000 + paired_index * 100 + metric_index)
                    std = float(differences.std(ddof=1))
                    paired.append({
                        "study": name, "planner": context[0], "density": context[1],
                        "loss_probability": context[2], "delay_steps": context[3],
                        "observation_radius": context[4], "left": "certificate_repair",
                        "right": comparator, "metric": metric, "paired_maps": 100,
                        "mean_difference": float(differences.mean()), "std_difference": std,
                        "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                        "ci95_low": low, "ci95_high": high,
                    })
                paired_index += 1

    primary_rows = [
        row for row in csv.DictReader((primary_directory / "results.csv").open())
        if int(row["observation_radius"]) == 2 and row["policy"] in {
            "action_triggered_repair", "full_replica_repair", "utility_triggered_repair",
            "deadline_aware_repair", "certificate_repair",
        }
    ]
    primary = _groups(primary_rows)
    ablations = []
    for planner in ("astar", "dstar_lite"):
        context = (planner, .2, .3, 0, 2)
        full = primary[context + ("certificate_repair",)]
        comparisons = {
            "trigger_to_action": primary[context + ("action_triggered_repair",)],
            "scope_to_full_replica": primary[context + ("full_replica_repair",)],
            "utility_heuristic": primary[context + ("utility_triggered_repair",)],
            "deadline_heuristic": primary[context + ("deadline_aware_repair",)],
        }
        for study in (
            "certificate_cadence_k4", "certificate_q1_cap8",
            "certificate_q2_cap4", "certificate_q2_cap12",
        ):
            only_condition = next(
                condition for condition in study_groups[study]
                if condition[0] == planner
            )
            comparisons[study] = study_groups[study][only_condition]
        for comparison_index, (label, ablated) in enumerate(comparisons.items()):
            for metric_index, metric in enumerate(ABLATION_METRICS):
                differences = np.asarray([
                    float(full[key][metric]) - float(ablated[key][metric]) for key in sorted(expected_keys)
                ])
                low, high = bootstrap(differences, 500_000 + comparison_index * 100 + metric_index)
                std = float(differences.std(ddof=1))
                ablations.append({
                    "planner": planner, "full_method": "certificate_q2_cap8_k1",
                    "ablation": label, "metric": metric, "paired_maps": 100,
                    "mean_difference": float(differences.mean()), "std_difference": std,
                    "paired_effect_dz": float(differences.mean() / std) if std else 0.0,
                    "ci95_low": low, "ci95_high": high,
                })

    write_csv(output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(output_directory / "paired_extension_comparisons.csv", paired)
    write_csv(output_directory / "paired_full_method_ablations.csv", ablations)
    result = {
        "complete": True, "studies": len(manifest["studies"]),
        "episodes": total_rows, "independent_maps_per_condition": 100,
        "primary_fov": "5x5",
        "confidence_interval": "20,000-draw map-cluster bootstrap; all comparisons paired by layout and loss trace",
    }
    (output_directory / "analysis_manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, required=True)
    parser.add_argument("--primary-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.input_directory, args.primary_directory, args.output_directory), indent=2))


if __name__ == "__main__":
    main()
