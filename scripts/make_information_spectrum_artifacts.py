#!/usr/bin/env python3
"""Generate manuscript tables for the information-sharing spectrum."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LABELS = {
    "no_communication": "No Communication",
    "certificate_repair": "CARE",
    "periodic_full_sync": "Continuous Full Sync",
}
ORDER = tuple(LABELS)


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open()))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def interval(row: dict[str, str], digits: int, scale: float = 1.0) -> str:
    return (
        f'[{float(row["ci95_low"]) / scale:.{digits}f}, '
        f'{float(row["ci95_high"]) / scale:.{digits}f}]'
    )


def artifacts(analysis_directory: Path, table_directory: Path) -> None:
    table_directory.mkdir(parents=True, exist_ok=True)
    summary = read_csv(analysis_directory / "summary_mean_std_ci.csv")
    paired = read_csv(analysis_directory / "paired_comparisons.csv")
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

    rows = []
    for radius in (1, 2, 3):
        for planner in ("astar", "dstar_lite"):
            for policy in ORDER:
                csr = lookup[(radius, planner, policy, "seeker_success_rate")]
                overall = lookup[(radius, planner, policy, "completion_success_rate")]
                episode_length = lookup[(radius, planner, policy, "episode_length")]
                traffic = lookup[(radius, planner, policy, "attempted_bytes")]
                replica_error = lookup[(radius, planner, policy, "mean_replica_error")]
                rows.append({
                    "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "strategy": LABELS[policy],
                    "seeker_csr_mean": f'{float(csr["mean"]):.4f}',
                    "seeker_csr_std": f'{float(csr["std"]):.4f}',
                    "seeker_csr_ci95": interval(csr, 4),
                    "overall_completion_mean": f'{float(overall["mean"]):.4f}',
                    "overall_completion_ci95": interval(overall, 4),
                    "el_mean": f'{float(episode_length["mean"]):.2f}',
                    "el_std": f'{float(episode_length["std"]):.2f}',
                    "el_ci95": interval(episode_length, 2),
                    "attempted_kb_mean": f'{float(traffic["mean"]) / 1000:.2f}',
                    "attempted_kb_std": f'{float(traffic["std"]) / 1000:.2f}',
                    "attempted_kb_ci95": interval(traffic, 2, 1000),
                    "mean_replica_error": f'{float(replica_error["mean"]):.4f}',
                })
    write_csv(table_directory / "care_information_spectrum.csv", rows)
    lines = [
        "# Information-sharing spectrum", "",
        "Continuous Full Sync performs a budget-bounded full-replica synchronization every step (K=1). All strategies use the same lossy link and 100 matched structured maps. Seeker CSR is exactly derived from the audited observer/seeker pairing; overall completion is diagnostic only.",
        "",
        "| FOV | Planner | Strategy | Derived seeker CSR mean ± SD [95% CI] | Overall completion diagnostic [95% CI] | EL mean ± SD [95% CI] | Attempted KB mean ± SD [95% CI] | Replica error |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f'| {row["fov"]} | {row["planner"]} | {row["strategy"]} | '
            f'{row["seeker_csr_mean"]} ± {row["seeker_csr_std"]} {row["seeker_csr_ci95"]} | '
            f'{row["overall_completion_mean"]} {row["overall_completion_ci95"]} | '
            f'{row["el_mean"]} ± {row["el_std"]} {row["el_ci95"]} | '
            f'{row["attempted_kb_mean"]} ± {row["attempted_kb_std"]} '
            f'{row["attempted_kb_ci95"]} | {row["mean_replica_error"]} |'
        )
    (table_directory / "care_information_spectrum.md").write_text(
        "\n".join(lines) + "\n"
    )

    comparisons = (
        ("certificate_repair", "no_communication"),
        ("periodic_full_sync", "certificate_repair"),
    )
    effects = []
    for radius in (1, 2, 3):
        for planner in ("astar", "dstar_lite"):
            for left, right in comparisons:
                csr = paired_lookup[(
                    radius, planner, left, right, "seeker_success_rate",
                )]
                episode_length = paired_lookup[(
                    radius, planner, left, right, "episode_length",
                )]
                traffic = paired_lookup[(
                    radius, planner, left, right, "attempted_bytes",
                )]
                effects.append({
                    "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "comparison": f"{LABELS[left]} - {LABELS[right]}",
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
    write_csv(table_directory / "care_information_spectrum_paired.csv", effects)
    lines = [
        "# Paired information-spectrum comparisons", "",
        "Positive Δ derived seeker CSR favors the left strategy; negative ΔEL means shorter episodes.",
        "",
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
    (table_directory / "care_information_spectrum_paired.md").write_text(
        "\n".join(lines) + "\n"
    )

    manifest = json.loads(
        (analysis_directory / "analysis_manifest.json").read_text()
    )
    (table_directory / "care_information_spectrum_manifest.json").write_text(
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
