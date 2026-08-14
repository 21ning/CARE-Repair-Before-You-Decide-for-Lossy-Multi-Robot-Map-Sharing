#!/usr/bin/env python3
"""Analyze natural non-tiled CARE validity and scale experiments."""

from __future__ import annotations

import argparse
import csv
from hashlib import sha256
import json
from collections import defaultdict
from pathlib import Path
import shutil
import sys

import numpy as np

try:
    from bootstrap_ci import bootstrap_mean_ci
except ModuleNotFoundError:
    from scripts.bootstrap_ci import bootstrap_mean_ci

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmvr.env import load_instance, natural_bitmap_sha256
from cmvr.env.natural_critical import sample_natural_occupancy_bitmap


BOOTSTRAP_DRAWS = 20_000
PRIMARY_POLICIES = (
    "no_communication", "one_shot_delta", "retry_all_arq",
    "periodic_full_sync", "path_aware_top_k_repair",
    "single_cell_sensitivity_repair", "deadline_aware_repair",
    "certificate_repair",
)
METRICS = (
    "seeker_success_rate", "critical_pair_success_rate",
    "completion_success_rate", "all_seekers_success", "episode_length",
    "mean_seeker_completion_step_censored",
    "attempted_bytes", "delivered_bytes", "attempted_repair_bytes",
    "mean_path_truth_error", "episode_cpu_ms",
)


def _bootstrap(values: np.ndarray, seed: int) -> tuple[float, float]:
    del seed
    return bootstrap_mean_ci(values, draws=BOOTSTRAP_DRAWS)


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def _rows(directory: Path) -> list[dict[str, str]]:
    return list(csv.DictReader((directory / "results.csv").open()))


def _audit_manifest(
    directory: Path, expected_maps: int, rows: list[dict[str, str]], *,
    expected_agents: int, expected_map_size: int,
    expected_policies: tuple[str, ...],
) -> dict:
    run = json.loads((directory / "summary.json").read_text())
    config = run.get("config", {})
    expected_rows = expected_maps * 2 * len(expected_policies)
    expected_config = {
        "instance_family": "natural_critical_random", "seed_count": expected_maps,
        "num_agents": expected_agents, "map_size": expected_map_size,
        "observation_radius": 2, "workers": 32,
    }
    if run.get("rows") != expected_rows or run.get("workers") != 32:
        raise ValueError("natural run summary has an unexpected row/worker count")
    for field, expected in expected_config.items():
        if config.get(field) != expected:
            raise ValueError(f"unexpected natural config {field}={config.get(field)!r}")
    if tuple(config.get("policies", ())) != expected_policies:
        raise ValueError("natural run policy grid differs from the frozen design")
    if tuple(config.get("planners", ())) != ("astar", "dstar_lite"):
        raise ValueError("natural run planner grid differs from the frozen design")
    if tuple(map(float, config.get("loss_probabilities", ()))) != (.3,):
        raise ValueError("natural run must use the frozen 30% loss condition")
    if tuple(map(int, config.get("delay_steps", ()))) != (0,):
        raise ValueError("natural run must use the frozen zero-delay condition")
    if tuple(map(float, config.get("obstacle_densities", ()))) != (.2,):
        raise ValueError("natural run must use the frozen Bernoulli density")

    manifest = json.loads((directory / "accepted_layout_manifest.json").read_text())
    records = manifest["records"]
    # One record per map/radius/density; these frozen suites have one of each.
    if len(records) != expected_maps:
        raise ValueError(f"expected {expected_maps} accepted-map records, got {len(records)}")
    if not manifest["selection_precedes_all_policy_execution"] or manifest["selection_uses_policy_or_link_outcomes"]:
        raise ValueError("natural selector manifest does not establish outcome independence")
    layouts = {record["layout_fingerprint"] for record in records}
    starts_goals = {
        json.dumps((record["starts"], record["goals"]), separators=(",", ":"))
        for record in records
    }
    critical = {record["metadata"]["critical_decision_pairs"] for record in records}
    raw = {record["metadata"]["raw_bitmap_sha256"] for record in records}
    if not all(len(values) == expected_maps for values in (layouts, starts_goals, critical, raw)):
        raise ValueError("natural suite lacks unique layout/start-goal/critical/raw signatures")
    if any(record["metadata"]["raw_bitmap_sha256"] != record["metadata"]["post_selection_bitmap_sha256"] for record in records):
        raise ValueError("a selected natural bitmap differs from its raw sample")
    attempts = np.asarray([int(record["metadata"]["selection_attempt"]) for record in records])
    result_signatures: dict[int, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        if (
            row["topology_family"] != "natural_critical_random"
            or int(row["num_agents"]) != expected_agents
            or int(row["map_size"]) != expected_map_size
            or int(row["observation_radius"]) != 2
            or float(row["density"]) != .2
            or float(row["loss_probability"]) != .3
            or int(row["delay_steps"]) != 0
        ):
            raise ValueError("natural result row violates its frozen condition")
        result_signatures[int(row["layout_seed"])].add(
            (row["instance_fingerprint"], row["layout_fingerprint"])
        )
    if set(result_signatures) != set(range(expected_maps)):
        raise ValueError("natural results do not cover layout seeds 0..99")

    densities = []
    path_steps = []
    observer_steps = []
    windows = []
    for record in records:
        seed = int(record["layout_seed"])
        candidates = tuple(
            (directory / "instances").glob(
                f"density-0p20_radius-2_layout-{seed}_*.json"
            )
        )
        if len(candidates) != 1:
            raise ValueError(f"cannot resolve exactly one saved instance for seed {seed}")
        instance = load_instance(candidates[0])
        metadata = dict(instance.package_metadata)
        if (
            instance.generation_seed != seed
            or instance.fingerprint() != record["instance_fingerprint"]
            or instance.layout_fingerprint() != record["layout_fingerprint"]
            or [list(cell) for cell in instance.starts] != record["starts"]
            or [list(cell) for cell in instance.goals] != record["goals"]
            or metadata != record["metadata"]
            or result_signatures[seed]
            != {(instance.fingerprint(), instance.layout_fingerprint())}
        ):
            raise ValueError(f"manifest/result/serialized-instance mismatch for seed {seed}")
        raw_digest = natural_bitmap_sha256(instance.obstacle_map)
        if (
            raw_digest != metadata["raw_bitmap_sha256"]
            or raw_digest != metadata["post_selection_bitmap_sha256"]
        ):
            raise ValueError(f"saved bitmap digest mismatch for seed {seed}")
        reproduced = sample_natural_occupancy_bitmap(
            raw_seed=int(metadata["raw_bitmap_seed"]),
            map_size=instance.map_size,
            obstacle_density=float(metadata["target_obstacle_density"]),
        )
        if not np.array_equal(reproduced, instance.obstacle_map):
            raise ValueError(f"saved bitmap is not the declared raw sample for seed {seed}")
        diagnostics = json.loads(record["metadata"]["natural_pair_diagnostics"])
        path_steps.extend(float(item["seeker_truth_path_steps"]) for item in diagnostics)
        observer_steps.extend(float(item["observer_truth_path_steps"]) for item in diagnostics)
        windows.extend(float(item["zero_delay_communication_window_steps"]) for item in diagnostics)
        densities.append(float(record["metadata"]["target_obstacle_density"]))
    return {
        "accepted_maps": expected_maps,
        "unique_layouts": len(layouts),
        "unique_start_goal_signatures": len(starts_goals),
        "unique_critical_signatures": len(critical),
        "unique_raw_bitmaps": len(raw),
        "raw_bitmap_immutable": True,
        "max_selection_attempt": int(attempts.max()),
        "mean_selection_attempt": float(attempts.mean()),
        "seeker_truth_path_steps_min": float(min(path_steps)),
        "seeker_truth_path_steps_max": float(max(path_steps)),
        "observer_truth_path_steps_min": float(min(observer_steps)),
        "observer_truth_path_steps_max": float(max(observer_steps)),
        "communication_window_steps_min": float(min(windows)),
        "communication_window_steps_max": float(max(windows)),
        "serialized_instances_rehashed": expected_maps,
        "raw_bitmaps_bit_exactly_reproduced": expected_maps,
        "results_cross_checked": len(rows),
        "accepted_manifest_sha256": sha256(
            (directory / "accepted_layout_manifest.json").read_bytes()
        ).hexdigest(),
    }


def _analyze_groups(
    rows: list[dict[str, str]], *, condition_fields: tuple[str, ...],
    expected_policies: tuple[str, ...], output: Path, seed_offset: int,
) -> None:
    groups: dict[tuple[str, ...], dict[tuple[str, str], dict[str, str]]] = defaultdict(dict)
    for row in rows:
        condition = tuple(row[field] for field in condition_fields) + (row["policy"],)
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate natural episode: {condition}, {key}")
        groups[condition][key] = row
    expected_keys = {(str(seed), str(seed)) for seed in range(100)}
    if any(set(trials) != expected_keys for trials in groups.values()):
        raise ValueError("natural conditions do not contain 100 matched maps")
    summaries = []
    for condition_index, (condition, trials) in enumerate(sorted(groups.items())):
        fields = dict(zip(condition_fields + ("policy",), condition))
        for metric_index, metric in enumerate(METRICS):
            values = np.asarray([float(trials[key][metric]) for key in sorted(expected_keys)])
            low, high = _bootstrap(values, seed_offset + condition_index * 100 + metric_index)
            summaries.append({
                **fields, "metric": metric, "independent_maps": 100,
                "mean": float(values.mean()), "std": float(values.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
            })
    _write(output / "summary_mean_std_ci.csv", summaries)

    paired = []
    base_conditions = sorted({condition[:-1] for condition in groups})
    for condition_index, condition in enumerate(base_conditions):
        left = groups[condition + ("certificate_repair",)]
        for comparator in expected_policies:
            if comparator == "certificate_repair":
                continue
            right = groups[condition + (comparator,)]
            for metric_index, metric in enumerate(METRICS):
                differences = np.asarray([
                    float(left[key][metric]) - float(right[key][metric])
                    for key in sorted(expected_keys)
                ])
                low, high = _bootstrap(
                    differences, seed_offset + 1_000_000 + condition_index * 1000 + metric_index,
                )
                std = float(differences.std(ddof=1))
                paired.append({
                    **dict(zip(condition_fields, condition)), "left": "certificate_repair",
                    "right": comparator, "metric": metric, "paired_maps": 100,
                    "mean_difference": float(differences.mean()),
                    "std_difference": std,
                    "paired_effect_dz": float(differences.mean()/std) if std else 0.0,
                    "ci95_low": low, "ci95_high": high,
                })
    _write(output / "paired_comparisons.csv", paired)


def analyze(primary: Path, scale: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    primary_rows = _rows(primary)
    expected_primary = 100 * 2 * len(PRIMARY_POLICIES)
    if len(primary_rows) != expected_primary:
        raise ValueError(f"expected {expected_primary} natural primary rows")
    primary_audit = _audit_manifest(
        primary, 100, primary_rows, expected_agents=8, expected_map_size=48,
        expected_policies=PRIMARY_POLICIES,
    )
    tracked_manifests = output / "accepted_manifests"
    tracked_manifests.mkdir()
    shutil.copyfile(
        primary / "accepted_layout_manifest.json",
        tracked_manifests / "natural_primary_accepted_layouts.json",
    )
    primary_output = output / "primary"
    primary_output.mkdir()
    _analyze_groups(
        primary_rows, condition_fields=("planner",),
        expected_policies=PRIMARY_POLICIES, output=primary_output, seed_offset=10_000,
    )

    scale_rows: list[dict[str, str]] = []
    scale_audits = {}
    for agents in (4, 8, 16, 32):
        directory = scale / f"agents-{agents}"
        rows = _rows(directory)
        if len(rows) != 100 * 2 * 2:
            raise ValueError(f"scale {agents} lacks 400 episodes")
        scale_rows.extend(rows)
        expected_sizes = {4: 24, 8: 32, 16: 48, 32: 64}
        scale_audits[str(agents)] = _audit_manifest(
            directory, 100, rows, expected_agents=agents,
            expected_map_size=expected_sizes[agents],
            expected_policies=("one_shot_delta", "certificate_repair"),
        )
        shutil.copyfile(
            directory / "accepted_layout_manifest.json",
            tracked_manifests / f"natural_scale_{agents}_accepted_layouts.json",
        )
    scale_output = output / "scale"
    scale_output.mkdir()
    _analyze_groups(
        scale_rows, condition_fields=("num_agents", "map_size", "planner"),
        expected_policies=("one_shot_delta", "certificate_repair"),
        output=scale_output, seed_offset=20_000,
    )
    manifest = {
        "complete": True,
        "primary_episodes": expected_primary,
        "scale_episodes": len(scale_rows),
        "primary_audit": primary_audit,
        "scale_audits": scale_audits,
        "primary_endpoint": "seeker_success_rate",
        "confidence_interval": f"{BOOTSTRAP_DRAWS}-draw paired map-cluster bootstrap",
        "population": (
            "i.i.d. Bernoulli maps conditioned on a predeclared action-conflict, "
            "visibility, path-length, communication-window, and disjointness predicate bundle"
        ),
    }
    (output / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary-directory", type=Path, required=True)
    parser.add_argument("--scale-directory", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.primary_directory, args.scale_directory, args.output_directory)
    print("natural external-validity analysis complete")


if __name__ == "__main__":
    main()
