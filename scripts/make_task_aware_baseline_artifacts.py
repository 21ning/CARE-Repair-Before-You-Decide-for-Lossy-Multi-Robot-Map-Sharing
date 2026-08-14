#!/usr/bin/env python3
"""Generate compact manuscript tables for the task-aware baseline ladder."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LABELS = {
    "one_shot_delta": "One-shot",
    "retry_all_arq": "Retry-All ARQ",
    "path_weighted_arq": "Path-Weighted ARQ",
    "utility_triggered_repair": "PSR-UT",
    "deadline_aware_repair": "CARE-Lite",
    "path_aware_top_k_repair": "Path-Aware Top-K",
    "single_cell_sensitivity_repair": "Single-Cell Sensitivity",
    "certificate_repair": "CARE",
}
ORDER = tuple(LABELS)
NEAREST = (
    "path_aware_top_k_repair", "single_cell_sensitivity_repair",
    "deadline_aware_repair", "utility_triggered_repair",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open()))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def artifacts(analysis_directory: Path, table_directory: Path) -> None:
    table_directory.mkdir(parents=True, exist_ok=True)
    summary = read_csv(analysis_directory / "summary_mean_std_ci.csv")
    paired = read_csv(analysis_directory / "paired_comparisons.csv")
    diagnostics = read_csv(analysis_directory / "mechanism_diagnostics.csv")
    lookup = {
        (
            int(row["observation_radius"]), row["planner"],
            row["policy"], row["metric"],
        ): row for row in summary
    }
    paired_lookup = {
        (
            int(row["observation_radius"]), row["planner"], row["left"],
            row["right"], row["metric"],
        ): row for row in paired
    }

    primary = []
    for planner in ("astar", "dstar_lite"):
        for policy in ORDER:
            csr = lookup[(2, planner, policy, "seeker_success_rate")]
            overall = lookup[(2, planner, policy, "completion_success_rate")]
            episode_length = lookup[(2, planner, policy, "episode_length")]
            traffic = lookup[(2, planner, policy, "attempted_bytes")]
            cpu = lookup[(2, planner, policy, "episode_cpu_ms")]
            primary.append({
                "planner": "A*" if planner == "astar" else "D* Lite",
                "method": LABELS[policy],
                "seeker_csr_mean": f'{float(csr["mean"]):.4f}',
                "seeker_csr_std": f'{float(csr["std"]):.4f}',
                "seeker_csr_ci95": (
                    f'[{float(csr["ci95_low"]):.4f}, '
                    f'{float(csr["ci95_high"]):.4f}]'
                ),
                "overall_completion_mean": f'{float(overall["mean"]):.4f}',
                "overall_completion_ci95": (
                    f'[{float(overall["ci95_low"]):.4f}, '
                    f'{float(overall["ci95_high"]):.4f}]'
                ),
                "el_mean": f'{float(episode_length["mean"]):.2f}',
                "el_std": f'{float(episode_length["std"]):.2f}',
                "el_ci95": (
                    f'[{float(episode_length["ci95_low"]):.2f}, '
                    f'{float(episode_length["ci95_high"]):.2f}]'
                ),
                "attempted_kb": f'{float(traffic["mean"]) / 1000:.2f}',
                "episode_cpu_ms": f'{float(cpu["mean"]):.1f}',
            })
    write_csv(table_directory / "care_task_aware_primary.csv", primary)
    lines = [
        "# Task-aware baseline ladder at 5x5 sensing and 30% packet loss", "",
        "100 matched structured maps; mean ± sample SD and map-cluster 95% CI. Seeker CSR is exactly derived from the audited observer/seeker pairing; overall completion is diagnostic only.", "",
        "| Planner | Method | Derived seeker CSR mean ± SD [95% CI] | Overall completion diagnostic [95% CI] | EL mean ± SD [95% CI] | Attempted KB | Episode CPU ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in primary:
        lines.append(
            f'| {row["planner"]} | {row["method"]} | {row["seeker_csr_mean"]} ± '
            f'{row["seeker_csr_std"]} {row["seeker_csr_ci95"]} | '
            f'{row["overall_completion_mean"]} {row["overall_completion_ci95"]} | '
            f'{row["el_mean"]} ± '
            f'{row["el_std"]} {row["el_ci95"]} | {row["attempted_kb"]} | '
            f'{row["episode_cpu_ms"]} |'
        )
    (table_directory / "care_task_aware_primary.md").write_text(
        "\n".join(lines) + "\n"
    )

    fov = []
    for radius in (1, 2, 3):
        for planner in ("astar", "dstar_lite"):
            for policy in ORDER:
                csr = lookup[(radius, planner, policy, "seeker_success_rate")]
                episode_length = lookup[(radius, planner, policy, "episode_length")]
                traffic = lookup[(radius, planner, policy, "attempted_bytes")]
                fov.append({
                    "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "method": LABELS[policy],
                    "seeker_csr_mean": f'{float(csr["mean"]):.4f}',
                    "seeker_csr_ci95": (
                        f'[{float(csr["ci95_low"]):.4f}, '
                        f'{float(csr["ci95_high"]):.4f}]'
                    ),
                    "el_mean": f'{float(episode_length["mean"]):.2f}',
                    "el_ci95": (
                        f'[{float(episode_length["ci95_low"]):.2f}, '
                        f'{float(episode_length["ci95_high"]):.2f}]'
                    ),
                    "attempted_kb": f'{float(traffic["mean"]) / 1000:.2f}',
                })
    write_csv(table_directory / "care_task_aware_fov.csv", fov)
    lines = [
        "# Task-aware baseline ladder across sensing ranges", "",
        "All conditions use 30% packet loss and 100 matched structured maps; reliability is derived seeker CSR.", "",
        "| FOV | Planner | Method | Derived seeker CSR [95% CI] | Mean EL [95% CI] | Attempted KB |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in fov:
        lines.append(
            f'| {row["fov"]} | {row["planner"]} | {row["method"]} | '
            f'{row["seeker_csr_mean"]} {row["seeker_csr_ci95"]} | {row["el_mean"]} '
            f'{row["el_ci95"]} | {row["attempted_kb"]} |'
        )
    (table_directory / "care_task_aware_fov.md").write_text(
        "\n".join(lines) + "\n"
    )

    effects = []
    for radius in (1, 2, 3):
        for planner in ("astar", "dstar_lite"):
            for comparator in NEAREST:
                csr = paired_lookup[(
                    radius, planner, "certificate_repair", comparator,
                    "seeker_success_rate",
                )]
                traffic = paired_lookup[(
                    radius, planner, "certificate_repair", comparator,
                    "attempted_bytes",
                )]
                episode_length = paired_lookup[(
                    radius, planner, "certificate_repair", comparator,
                    "episode_length",
                )]
                effects.append({
                    "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "comparison": f'CARE - {LABELS[comparator]}',
                    "seeker_csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                    "seeker_csr_ci95": (
                        f'[{float(csr["ci95_low"]):+.4f}, '
                        f'{float(csr["ci95_high"]):+.4f}]'
                    ),
                    "paired_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
                    "el_difference": f'{float(episode_length["mean_difference"]):+.2f}',
                    "el_ci95": (
                        f'[{float(episode_length["ci95_low"]):+.2f}, '
                        f'{float(episode_length["ci95_high"]):+.2f}]'
                    ),
                    "traffic_difference_kb": (
                        f'{float(traffic["mean_difference"]) / 1000:+.2f}'
                    ),
                    "traffic_ci95_kb": (
                        f'[{float(traffic["ci95_low"]) / 1000:+.2f}, '
                        f'{float(traffic["ci95_high"]) / 1000:+.2f}]'
                    ),
                })
    write_csv(table_directory / "care_task_aware_paired.csv", effects)
    lines = [
        "# CARE paired against the closest task-aware baselines", "",
        "Positive Δ derived seeker CSR favors CARE; negative ΔKB means CARE sends less.", "",
        "| FOV | Planner | Comparison | Δ derived seeker CSR [95% CI] | paired d_z | ΔEL [95% CI] | ΔKB [95% CI] |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in effects:
        lines.append(
            f'| {row["fov"]} | {row["planner"]} | {row["comparison"]} | '
            f'{row["seeker_csr_difference"]} {row["seeker_csr_ci95"]} | {row["paired_dz"]} | '
            f'{row["el_difference"]} {row["el_ci95"]} | '
            f'{row["traffic_difference_kb"]} {row["traffic_ci95_kb"]} |'
        )
    (table_directory / "care_task_aware_paired.md").write_text(
        "\n".join(lines) + "\n"
    )

    mechanism = []
    for row in diagnostics:
        mechanism.append({
            "fov": row["fov"],
            "planner": "A*" if row["planner"] == "astar" else "D* Lite",
            "method": LABELS[row["policy"]],
            "queries_per_check": f'{float(row["mean_query_cells_per_check"]):.3f}',
            "query_cells_per_episode": f'{float(row["mean_query_cells_per_episode"]):.2f}',
            "counterfactual_plans_per_episode": (
                f'{float(row["mean_counterfactual_plans_per_episode"]):.2f}'
            ),
            "method_cpu_ms": f'{float(row["mean_method_cpu_ms"]):.1f}',
        })
    write_csv(table_directory / "care_task_aware_mechanism.csv", mechanism)
    lines = [
        "# Task-aware mechanism diagnostics", "",
        "| FOV | Planner | Method | Query cells/check | Query cells/episode | Counterfactual plans/episode | Method CPU ms |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in mechanism:
        lines.append(
            f'| {row["fov"]} | {row["planner"]} | {row["method"]} | '
            f'{row["queries_per_check"]} | {row["query_cells_per_episode"]} | '
            f'{row["counterfactual_plans_per_episode"]} | {row["method_cpu_ms"]} |'
        )
    (table_directory / "care_task_aware_mechanism.md").write_text(
        "\n".join(lines) + "\n"
    )

    manifest = json.loads(
        (analysis_directory / "analysis_manifest.json").read_text()
    )
    (table_directory / "care_task_aware_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, required=True)
    args = parser.parse_args()
    artifacts(args.analysis_directory, args.table_directory)


if __name__ == "__main__":
    main()
