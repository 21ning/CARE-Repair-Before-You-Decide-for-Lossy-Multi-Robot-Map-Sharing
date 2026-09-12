#!/usr/bin/env python3
"""Audit frozen CARE timings and build the computation-overhead artifacts.

This script is deliberately analysis-only: it reads a completed result matrix,
checks the paired design, and writes derived paper tables.  It never imports or
invokes the experiment runner.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Callable

import numpy as np
import yaml

try:
    from bootstrap_ci import (
        BOOTSTRAP_DRAWS,
        BOOTSTRAP_SEED,
        bootstrap_mean_ci,
        bootstrap_ratio_ci,
    )
except ModuleNotFoundError:  # Imported as ``scripts.analyze_*`` in tests.
    from scripts.bootstrap_ci import (
        BOOTSTRAP_DRAWS,
        BOOTSTRAP_SEED,
        bootstrap_mean_ci,
        bootstrap_ratio_ci,
    )


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = Path("outputs/care_closest_work_baselines_fov_100map")
SOURCE_CONFIG = Path("configs/care_closest_work_baselines_fov_100map.yaml")
TABLE_DIRECTORY = Path("paper/tables")

PLANNERS = ("astar", "dstar_lite")
POLICIES = (
    "one_shot_delta",
    "path_aware_top_k_repair",
    "single_cell_sensitivity_repair",
    "deadline_aware_repair",
    "certificate_repair",
)
LABELS = {
    "one_shot_delta": "One-shot",
    "path_aware_top_k_repair": "Path Top-K",
    "single_cell_sensitivity_repair": "Single-Cell",
    "deadline_aware_repair": "CARE-Lite",
    "certificate_repair": "CARE",
}
PLANNER_LABELS = {"astar": "A*", "dstar_lite": "D* Lite"}
PAIR_KEYS = tuple((str(seed), str(seed)) for seed in range(100))
PAIR_KEY_SET = set(PAIR_KEYS)

ROLE_FIELDS = {
    "observer_success_rate",
    "seeker_success_rate",
    "critical_pair_success_rate",
    "all_seekers_success",
    "completed_mask",
}
REQUIRED_FIELDS = ROLE_FIELDS | {
    "topology_family",
    "map_size",
    "num_agents",
    "observation_radius",
    "layout_seed",
    "network_seed",
    "instance_fingerprint",
    "layout_fingerprint",
    "density",
    "loss_probability",
    "delay_steps",
    "planner",
    "policy",
    "episode_cpu_ms",
    "planning_cpu_ms",
    "certificate_cpu_ms",
    "optimistic_planning_calls",
    "pessimistic_planning_calls",
    "certificate_scenario_planning_calls",
    "certificate_candidate_cells",
    "certificate_query_cells",
    "task_aware_candidate_cells",
    "task_aware_query_cells",
    "single_cell_planning_calls",
    "deadline_query_cells",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_relative(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _link_seed(
    seed: int, density: float, loss: float, delay: int, config_seed: int,
) -> int:
    material = (
        f"{config_seed}|{seed}|{density:.6f}|{loss:.6f}|{delay}"
    ).encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def _canonical_rows_digest(rows: list[dict[str, str]]) -> str:
    payload = "\n".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"))
        for row in sorted(
            rows,
            key=lambda row: (
                row["planner"], row["policy"], int(row["layout_seed"]),
                int(row["network_seed"]),
            ),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _float(row: dict[str, str], field: str) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric field {field!r}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite numeric field {field!r}")
    return value


def _candidate_cells(row: dict[str, str]) -> float | None:
    policy = row["policy"]
    if policy in {"path_aware_top_k_repair", "single_cell_sensitivity_repair"}:
        return _float(row, "task_aware_candidate_cells")
    if policy == "certificate_repair":
        return _float(row, "certificate_candidate_cells")
    # One-shot has no repair selector. CARE-Lite logs its selected influence
    # cells but not a separate pre-selection candidate-pool count.
    return None


def _query_cells(row: dict[str, str]) -> float:
    policy = row["policy"]
    if policy in {"path_aware_top_k_repair", "single_cell_sensitivity_repair"}:
        return _float(row, "task_aware_query_cells")
    if policy == "deadline_aware_repair":
        return _float(row, "deadline_query_cells")
    if policy == "certificate_repair":
        return _float(row, "certificate_query_cells")
    return 0.0


def _extra_planning_calls(row: dict[str, str]) -> float:
    """Return method-specific plans beyond the shared optimistic replans."""
    policy = row["policy"]
    if policy == "single_cell_sensitivity_repair":
        return _float(row, "single_cell_planning_calls")
    if policy == "deadline_aware_repair":
        return _float(row, "pessimistic_planning_calls")
    if policy == "certificate_repair":
        return _float(row, "certificate_scenario_planning_calls")
    return 0.0


def _certificate_scenario_calls(row: dict[str, str]) -> float:
    return _float(row, "certificate_scenario_planning_calls")


METRICS: tuple[tuple[str, str, Callable[[dict[str, str]], float | None]], ...] = (
    ("episode_cpu_ms", "ms/episode", lambda row: _float(row, "episode_cpu_ms")),
    ("planning_cpu_ms", "ms/episode", lambda row: _float(row, "planning_cpu_ms")),
    (
        "certificate_cpu_ms", "ms/episode",
        lambda row: _float(row, "certificate_cpu_ms"),
    ),
    (
        "method_extra_planning_calls", "calls/episode", _extra_planning_calls,
    ),
    (
        "certificate_scenario_planning_calls", "calls/episode",
        _certificate_scenario_calls,
    ),
    ("candidate_cells", "cells/episode", _candidate_cells),
    ("query_cells", "cells/episode", _query_cells),
)


def _audit_source(
    source_directory: Path, config_path: Path,
) -> tuple[
    list[dict[str, str]],
    dict,
    dict[tuple[str, str], dict[tuple[str, str], dict[str, str]]],
    dict,
]:
    results_path = source_directory / "results.csv"
    summary_path = source_directory / "summary.json"
    if not results_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("completed results.csv and summary.json are required")
    if not config_path.is_file():
        raise FileNotFoundError(f"frozen config not found: {config_path}")

    with results_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        missing = sorted(REQUIRED_FIELDS - fieldnames)
        if missing:
            raise ValueError(f"source schema lacks required fields: {missing}")
        rows = list(reader)
    summary = json.loads(summary_path.read_text())
    frozen_config = yaml.safe_load(config_path.read_text())
    run_config = summary.get("config")
    if run_config != frozen_config:
        raise ValueError("summary config does not exactly match the frozen YAML")

    expected_source_rows = (
        100 * 3 * 2 * len(frozen_config["policies"])
    )
    if len(rows) != expected_source_rows or summary.get("rows") != expected_source_rows:
        raise ValueError(
            f"expected {expected_source_rows} source rows, found {len(rows)}"
        )
    if summary.get("workers") != 32 or frozen_config.get("workers") != 32:
        raise ValueError("the frozen source must use exactly 32 workers")
    expected_config = {
        "instance_family": "multifork_cluttered",
        "seed_count": 100,
        "map_size": 32,
        "num_agents": 8,
        "observation_radii": [1, 2, 3],
        "loss_probabilities": [.3],
        "delay_steps": [0],
        "planners": ["astar", "dstar_lite"],
        "certificate_max_cells": 8,
    }
    for field, expected in expected_config.items():
        if frozen_config.get(field) != expected:
            raise ValueError(
                f"unexpected frozen config value {field}: "
                f"{frozen_config.get(field)!r} != {expected!r}"
            )
    if not set(POLICIES).issubset(frozen_config["policies"]):
        raise ValueError("the frozen config lacks a required overhead comparator")
    care_task_aware_query_cap_cells = int(frozen_config["certificate_max_cells"])
    care_task_aware_query_cap_bytes = (
        int(frozen_config["digest_base_bytes"])
        + care_task_aware_query_cap_cells
        * int(frozen_config["digest_entry_bytes"])
    )
    if care_task_aware_query_cap_bytes != 64:
        raise ValueError(
            "expected the CARE/Path/Single 64-byte query cap, got "
            f"{care_task_aware_query_cap_bytes}"
        )
    control_cap_bytes = int(frozen_config["control_bytes_per_agent_per_step"])
    care_lite_query_cap_cells = (
        control_cap_bytes - int(frozen_config["digest_base_bytes"])
    ) // int(frozen_config["digest_entry_bytes"])
    care_lite_query_cap_bytes = (
        int(frozen_config["digest_base_bytes"])
        + care_lite_query_cap_cells * int(frozen_config["digest_entry_bytes"])
    )

    source_conditions = {
        (
            int(row["observation_radius"]), float(row["density"]),
            float(row["loss_probability"]), int(row["delay_steps"]),
        )
        for row in rows
    }
    if source_conditions != {
        (radius, .2, .3, 0) for radius in (1, 2, 3)
    }:
        raise ValueError(f"unexpected source conditions: {source_conditions}")
    source_groups: dict[
        tuple[int, str, str], set[tuple[str, str]]
    ] = defaultdict(set)
    for row in rows:
        condition = int(row["observation_radius"]), row["planner"], row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in source_groups[condition]:
            raise ValueError(f"duplicate full-matrix trial: {condition}, {key}")
        source_groups[condition].add(key)
    expected_source_groups = {
        (radius, planner, policy)
        for radius in (1, 2, 3)
        for planner in PLANNERS
        for policy in frozen_config["policies"]
    }
    if set(source_groups) != expected_source_groups:
        raise ValueError("the full frozen source has incomplete condition cells")
    if any(keys != PAIR_KEY_SET for keys in source_groups.values()):
        raise ValueError("a full-matrix condition is not paired on exactly 100 maps")

    selected = [
        row for row in rows
        if int(row["observation_radius"]) == 2 and row["policy"] in POLICIES
    ]
    if len(selected) != 100 * len(PLANNERS) * len(POLICIES):
        raise ValueError(f"expected 1,000 selected rows, found {len(selected)}")
    if {
        (row["topology_family"], int(row["map_size"]), int(row["num_agents"]))
        for row in selected
    } != {("multifork_cluttered", 32, 8)}:
        raise ValueError("selected rows do not share the frozen task condition")
    if any(len(row["completed_mask"]) != 8 for row in selected):
        raise ValueError("role-aware completion masks must encode all eight agents")
    if any(_float(row, "observer_success_rate") != 1.0 for row in selected):
        raise ValueError("the controlled role-aware observer invariant is broken")

    groups: dict[
        tuple[str, str], dict[tuple[str, str], dict[str, str]]
    ] = defaultdict(dict)
    for row in selected:
        condition = row["planner"], row["policy"]
        key = row["layout_seed"], row["network_seed"]
        if key in groups[condition]:
            raise ValueError(f"duplicate paired trial: {condition}, {key}")
        groups[condition][key] = row
        for field in (
            "episode_cpu_ms", "planning_cpu_ms", "certificate_cpu_ms",
            "optimistic_planning_calls", "pessimistic_planning_calls",
            "certificate_scenario_planning_calls", "certificate_candidate_cells",
            "certificate_query_cells", "task_aware_candidate_cells",
            "task_aware_query_cells", "single_cell_planning_calls",
            "deadline_query_cells",
        ):
            if _float(row, field) < 0:
                raise ValueError(f"negative overhead field {field}")
        if _float(row, "certificate_cpu_ms") > _float(row, "planning_cpu_ms") + 1e-9:
            raise ValueError("certificate CPU must be a subset of planning CPU")
        if _float(row, "planning_cpu_ms") > _float(row, "episode_cpu_ms") + 1e-9:
            raise ValueError("planning CPU must be a subset of episode CPU")

    expected_conditions = {
        (planner, policy) for planner in PLANNERS for policy in POLICIES
    }
    if set(groups) != expected_conditions:
        raise ValueError("selected policy/planner cells are incomplete")
    for condition in expected_conditions:
        if set(groups[condition]) != PAIR_KEY_SET:
            raise ValueError(f"condition is not paired on exactly 100 maps: {condition}")

    instance_fingerprints: dict[tuple[str, str], set[str]] = defaultdict(set)
    layout_fingerprints: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in selected:
        key = row["layout_seed"], row["network_seed"]
        instance_fingerprints[key].add(row["instance_fingerprint"])
        layout_fingerprints[key].add(row["layout_fingerprint"])
    if any(len(values) != 1 for values in instance_fingerprints.values()):
        raise ValueError("a paired key maps to multiple frozen instances")
    if any(len(values) != 1 for values in layout_fingerprints.values()):
        raise ValueError("a paired key maps to multiple physical layouts")
    unique_instances = {next(iter(values)) for values in instance_fingerprints.values()}
    unique_layouts = {next(iter(values)) for values in layout_fingerprints.values()}
    if len(unique_instances) != 100 or len(unique_layouts) != 100:
        raise ValueError("the selected matrix must contain 100 unique frozen maps")

    # The link model hashes the common config seed, network seed and condition;
    # this is the exact seed schedule used by the runner. Common link keys then
    # receive identical packet-loss draws across policies.
    link_seeds = [
        _link_seed(seed, .2, .3, 0, int(frozen_config["link_seed"]))
        for seed in range(100)
    ]
    link_seed_digest = hashlib.sha256(
        json.dumps(link_seeds, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    audit = {
        "source_rows": len(rows),
        "source_groups": len(source_groups),
        "source_groups_all_have_100_paired_keys": True,
        "selected_rows": len(selected),
        "selected_groups": len(groups),
        "workers": 32,
        "worker_semantics": (
            "32 workers parallelized independent episodes; each method episode "
            "and CARE certificate ran in one worker process"
        ),
        "role_aware_fields_present": sorted(ROLE_FIELDS),
        "observer_success_invariant": 1.0,
        "paired_key_fields": ["layout_seed", "network_seed"],
        "paired_keys_per_condition": 100,
        "paired_keys_exactly_0_through_99": True,
        "unique_instance_fingerprints": len(unique_instances),
        "unique_layout_fingerprints": len(unique_layouts),
        "same_instance_per_paired_key_across_planners_and_methods": True,
        "same_network_seed_per_paired_key_across_planners_and_methods": True,
        "keyed_loss_seed_schedule_sha256": link_seed_digest,
        "common_packet_loss_contract": (
            "same derived link seed; the transport hashes link seed and stable "
            "packet link_key so common packets have identical loss draws"
        ),
        "summary_config_exactly_matches_yaml": True,
        "common_control_cap_bytes": control_cap_bytes,
        "care_path_single_query_cap_cells": care_task_aware_query_cap_cells,
        "care_path_single_query_cap_bytes": care_task_aware_query_cap_bytes,
        "care_lite_query_cap_cells": care_lite_query_cap_cells,
        "care_lite_query_cap_bytes": care_lite_query_cap_bytes,
        "query_cap_scope": (
            "CARE, Path Top-K and Single-Cell use the additional 8-cell/64-byte "
            "algorithmic cap; CARE-Lite uses the codec maximum under the common "
            "512-byte control cap and is not a query-cap-matched comparator"
        ),
        "selected_input_sha256": _canonical_rows_digest(selected),
    }
    return selected, summary, groups, audit


def _summary(values: np.ndarray) -> dict[str, float]:
    low, high = bootstrap_mean_ci(values, draws=BOOTSTRAP_DRAWS)
    return {
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)),
        "ci95_low": low,
        "ci95_high": high,
    }


def _number(value: float) -> str:
    return f"{value:.6f}"


def _formatted(summary: dict[str, float], digits: int = 1) -> str:
    return (
        f'{summary["mean"]:.{digits}f} ± {summary["std"]:.{digits}f} '
        f'[{summary["ci95_low"]:.{digits}f}, {summary["ci95_high"]:.{digits}f}]'
    )


def analyze(
    source_directory: Path = SOURCE_DIRECTORY,
    config_path: Path = SOURCE_CONFIG,
    table_directory: Path = TABLE_DIRECTORY,
) -> dict:
    source_directory = (ROOT / source_directory).resolve() if not source_directory.is_absolute() else source_directory
    config_path = (ROOT / config_path).resolve() if not config_path.is_absolute() else config_path
    table_directory = (ROOT / table_directory).resolve() if not table_directory.is_absolute() else table_directory
    selected, run_summary, groups, source_audit = _audit_source(
        source_directory, config_path,
    )
    del selected  # All derived values below come through the audited groups.

    output_rows: list[dict[str, str]] = []
    for planner in PLANNERS:
        care_rows = groups[(planner, "certificate_repair")]
        care_episode = np.asarray([
            _float(care_rows[key], "episode_cpu_ms") for key in PAIR_KEYS
        ])
        for policy in POLICIES:
            trials = groups[(planner, policy)]
            metric_summaries: dict[str, dict[str, float] | None] = {}
            for metric, _unit, projection in METRICS:
                projected = [projection(trials[key]) for key in PAIR_KEYS]
                if all(value is None for value in projected):
                    metric_summaries[metric] = None
                    continue
                if any(value is None for value in projected):
                    raise ValueError(f"partially missing projected metric: {metric}")
                values = np.asarray(projected, dtype=float)
                metric_summaries[metric] = _summary(values)

            method_episode = np.asarray([
                _float(trials[key], "episode_cpu_ms") for key in PAIR_KEYS
            ])
            differences = care_episode - method_episode
            delta = _summary(differences)
            ratio = float(care_episode.sum() / method_episode.sum())
            ratio_low, ratio_high = bootstrap_ratio_ci(
                care_episode, method_episode, draws=BOOTSTRAP_DRAWS,
            )
            output: dict[str, str] = {
                "planner": PLANNER_LABELS[planner],
                "method": LABELS[policy],
                "policy": policy,
                "paired_maps": "100",
            }
            for metric, _unit, _projection in METRICS:
                summary = metric_summaries[metric]
                output[f"{metric}_available"] = "yes" if summary else "no"
                for statistic in ("mean", "std", "ci95_low", "ci95_high"):
                    output[f"{metric}_{statistic}"] = (
                        _number(summary[statistic]) if summary else ""
                    )
            output.update({
                "care_minus_method_episode_cpu_ms_mean": _number(delta["mean"]),
                "care_minus_method_episode_cpu_ms_std": _number(delta["std"]),
                "care_minus_method_episode_cpu_ms_ci95_low": _number(delta["ci95_low"]),
                "care_minus_method_episode_cpu_ms_ci95_high": _number(delta["ci95_high"]),
                "care_to_method_episode_cpu_ratio": _number(ratio),
                "care_to_method_episode_cpu_ratio_ci95_low": _number(ratio_low),
                "care_to_method_episode_cpu_ratio_ci95_high": _number(ratio_high),
            })
            output_rows.append(output)

    table_directory.mkdir(parents=True, exist_ok=True)
    csv_path = table_directory / "care_computation_overhead.csv"
    md_path = table_directory / "care_computation_overhead.md"
    manifest_path = table_directory / "care_computation_overhead_manifest.json"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(output_rows[0]), lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(output_rows)

    lines = [
        "# CARE computation overhead (frozen 5x5 anchor)",
        "",
        (
            "All values are per-episode process CPU or episode-total mechanism "
            "counts over 100 paired maps at 30% loss and zero delay. Brackets are "
            "95% CIs from the shared 20,000-draw map-cluster bootstrap."
        ),
        "",
        (
            "`CARE / method` is the ratio of paired-map CPU sums (equivalently, "
            "the ratio of means here), not the mean of per-map ratios. Its paired "
            "bootstrap preserves each map's numerator/denominator pair. This avoids "
            "inflation from small individual denominators."
        ),
        "",
    ]
    for planner in PLANNERS:
        lines.extend([
            f"## {PLANNER_LABELS[planner]}",
            "",
            (
                "| Method | Episode CPU ms, mean ± SD [95% CI] | Instrumented planning-block CPU ms, "
                "mean ± SD [95% CI] | Certificate CPU ms, mean ± SD [95% CI] | "
                "Extra plans / cert. scenario plans | Candidate / query cells | "
                "CARE−method episode CPU ms [95% CI] | CARE / method [95% CI] |"
            ),
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ])
        for output in (
            row for row in output_rows
            if row["planner"] == PLANNER_LABELS[planner]
        ):
            policy = output["policy"]
            def metric_summary(metric: str) -> dict[str, float] | None:
                if output[f"{metric}_available"] == "no":
                    return None
                return {
                    statistic: float(output[f"{metric}_{statistic}"])
                    for statistic in ("mean", "std", "ci95_low", "ci95_high")
                }

            episode = metric_summary("episode_cpu_ms")
            planning = metric_summary("planning_cpu_ms")
            certificate = metric_summary("certificate_cpu_ms")
            extra = metric_summary("method_extra_planning_calls")
            scenarios = metric_summary("certificate_scenario_planning_calls")
            candidates = metric_summary("candidate_cells")
            queries = metric_summary("query_cells")
            assert all(value is not None for value in (episode, planning, certificate, extra, scenarios, queries))
            candidate_text = _formatted(candidates, 1) if candidates else "n/r"
            delta_text = (
                f'{float(output["care_minus_method_episode_cpu_ms_mean"]):+.1f} '
                f'[{float(output["care_minus_method_episode_cpu_ms_ci95_low"]):+.1f}, '
                f'{float(output["care_minus_method_episode_cpu_ms_ci95_high"]):+.1f}]'
            )
            ratio_text = (
                f'{float(output["care_to_method_episode_cpu_ratio"]):.2f} '
                f'[{float(output["care_to_method_episode_cpu_ratio_ci95_low"]):.2f}, '
                f'{float(output["care_to_method_episode_cpu_ratio_ci95_high"]):.2f}]'
            )
            lines.append(
                f'| {LABELS[policy]} | {_formatted(episode, 1)} | '
                f'{_formatted(planning, 1)} | {_formatted(certificate, 1)} | '
                f'{_formatted(extra, 1)} / {_formatted(scenarios, 1)} | '
                f'{candidate_text} / {_formatted(queries, 1)} | {delta_text} | '
                f'{ratio_text} |'
            )
        lines.append("")
    lines.extend([
        (
            "`n/r` means not recorded as a distinct pool: One-shot has no repair "
            "selector, while CARE-Lite records only its selected influence/query "
            "cells. Extra plans exclude the 400 optimistic operational replans "
            "shared by all five methods; they are Single-Cell blocked replans, "
            "CARE-Lite pessimistic replans, or CARE scenario replans as applicable."
        ),
        "",
        (
            "The planning-block timer is instrumentation-specific and is not the "
            "cross-method primary runtime: it surrounds the full selector for CARE "
            "and Single-Cell, only the pessimistic plan for CARE-Lite, and excludes "
            "the Path Top-K selector. Use total episode CPU for method comparisons. "
            "Candidate totals are also differently scoped: Path/Single report their "
            "uncapped proposal pools, whereas CARE reports post-cap scenario "
            "candidates; they are mechanism diagnostics, not like-for-like sizes."
        ),
        "",
        (
            "Timing uses `time.process_time()` in the frozen 32-worker batch. The "
            "workers parallelized independent episodes; CARE itself was not a 32-core "
            "algorithm within an episode. The intervals quantify between-map variation "
            "in that run, not machine-to-machine or repeated-run timing uncertainty; "
            "process CPU is not parallel wall-clock latency. Accordingly, these results "
            "support a material exact-certificate compute-cost claim, not a real-time "
            "latency guarantee."
        ),
        "",
        (
            "CARE, Path Top-K and Single-Cell use the additional 8-cell/64-byte "
            "algorithmic query cap. CARE-Lite uses the same codec and 512-byte "
            "control channel but may query up to 82 cells (508 encoded bytes); "
            "its CPU ratio is therefore an implementation comparison, not a "
            "query-cap-matched one."
        ),
    ])
    md_path.write_text("\n".join(lines) + "\n")

    results_path = source_directory / "results.csv"
    summary_path = source_directory / "summary.json"
    manifest = {
        "complete": True,
        "analysis_only": True,
        "new_experiments_run": False,
        "source": {
            "directory": _repo_relative(source_directory),
            "results": _repo_relative(results_path),
            "summary": _repo_relative(summary_path),
            "config": _repo_relative(config_path),
            "results_sha256": _sha256(results_path),
            "summary_sha256": _sha256(summary_path),
            "config_sha256": _sha256(config_path),
        },
        "condition": {
            "instance_family": "multifork_cluttered",
            "map_size": 32,
            "num_agents": 8,
            "observation_radius": 2,
            "fov": "5x5",
            "density": .2,
            "loss_probability": .3,
            "delay_steps": 0,
            "planners": list(PLANNERS),
            "policies": list(POLICIES),
            "independent_maps_per_condition": 100,
            "workers": int(run_summary["workers"]),
        },
        "source_audit": source_audit,
        "metric_semantics": {
            "episode_cpu_ms": (
                "per-episode process CPU measured by time.process_time; not wall clock"
            ),
            "planning_cpu_ms": (
                "instrumentation-specific planning block; includes the full CARE and "
                "Single-Cell selector, only the pessimistic plan for CARE-Lite, and "
                "excludes Path Top-K selection; not a cross-method primary runtime"
            ),
            "certificate_cpu_ms": (
                "subset of planning CPU spent inside exact CARE certificate construction"
            ),
            "method_extra_planning_calls": (
                "plans beyond shared optimistic replans: Single-Cell blocked, "
                "CARE-Lite pessimistic, or CARE scenario calls"
            ),
            "certificate_scenario_planning_calls": (
                "exact sparse-scenario replans; zero outside CARE"
            ),
            "candidate_cells": (
                "episode-total task-aware proposal cells for Path/Single or capped "
                "scenario candidates for CARE; not separately recorded for One-shot/CARE-Lite"
            ),
            "query_cells": "episode-total cells submitted to the common query-patch codec",
            "care_minus_method_episode_cpu_ms": (
                "paired map-level CARE minus method process CPU"
            ),
            "care_to_method_episode_cpu_ratio": (
                "ratio of paired-map episode CPU sums; not mean of per-map ratios"
            ),
        },
        "confidence_interval": {
            "draws": BOOTSTRAP_DRAWS,
            "public_base_seed": BOOTSTRAP_SEED,
            "cluster": "whole paired map/network-seed key",
            "index_matrix": (
                "shared deterministic matrix from scripts/bootstrap_ci.py for map_count=100"
            ),
            "marginal": "percentile interval for map-level mean",
            "difference": "paired percentile interval for CARE-minus-method mean",
            "ratio": "paired percentile interval for ratio of sums",
        },
        "timing_limit": (
            "32 workers parallelized independent single-process episodes; CIs measure "
            "between-map variation within that frozen run, not repeated-machine timing "
            "uncertainty or online wall latency"
        ),
        "comparison_limit": (
            "CARE-Lite shares the codec and 512-byte control channel but not the "
            "additional 8-cell/64-byte algorithmic cap used by CARE, Path Top-K "
            "and Single-Cell"
        ),
        "provenance_limit": (
            "the frozen run summary did not record generation git SHA, CPU model, "
            "frequency controls, CPU pinning, or isolated wall-clock timing"
        ),
        "output_rows": len(output_rows),
        "artifacts": {
            "csv": _repo_relative(csv_path),
            "csv_sha256": _sha256(csv_path),
            "markdown": _repo_relative(md_path),
            "markdown_sha256": _sha256(md_path),
        },
        "implementation": {
            "script": _repo_relative(Path(__file__)),
            "script_sha256": _sha256(Path(__file__)),
            "bootstrap_module": "scripts/bootstrap_ci.py",
            "bootstrap_module_sha256": _sha256(ROOT / "scripts/bootstrap_ci.py"),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, default=SOURCE_DIRECTORY)
    parser.add_argument("--config", type=Path, default=SOURCE_CONFIG)
    parser.add_argument("--table-directory", type=Path, default=TABLE_DIRECTORY)
    args = parser.parse_args()
    manifest = analyze(args.input_directory, args.config, args.table_directory)
    print(
        "CARE computation-overhead audit complete: "
        f'{manifest["output_rows"]} rows, no experiments run'
    )


if __name__ == "__main__":
    main()
