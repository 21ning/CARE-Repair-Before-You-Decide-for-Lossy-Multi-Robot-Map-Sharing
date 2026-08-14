#!/usr/bin/env python3
"""Create compact paper tables for the published reconciliation baselines."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


LABELS = {
    "one_shot_delta": "One-shot",
    "retry_all_arq": "Retry-All ARQ",
    "scuttlebutt_depth": "Scuttlebutt-Depth",
    "merkle_anti_entropy": "Dynamo-style Merkle AE",
    "iblt_reconciliation": "Partitioned IBLT",
    "certificate_repair": "CARE",
}
ORDER = tuple(LABELS)


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
    diagnostics = read_csv(analysis_directory / "protocol_diagnostics.csv")
    lookup = {
        (
            int(row["observation_radius"]), row["planner"],
            float(row["loss_probability"]), row["policy"], row["metric"],
        ): row
        for row in summary
    }

    primary = []
    for planner in ("astar", "dstar_lite"):
        for policy in ORDER:
            csr = lookup[(2, planner, .3, policy, "seeker_success_rate")]
            overall = lookup[(2, planner, .3, policy, "completion_success_rate")]
            episode_length = lookup[(2, planner, .3, policy, "episode_length")]
            traffic = lookup[(2, planner, .3, policy, "attempted_bytes")]
            error = lookup[(2, planner, .3, policy, "mean_path_truth_error")]
            primary.append({
                "planner": "A*" if planner == "astar" else "D* Lite",
                "method": LABELS[policy],
                "seeker_csr_mean": f'{float(csr["mean"]):.4f}',
                "seeker_csr_std": f'{float(csr["std"]):.4f}',
                "seeker_csr_ci95": f'[{float(csr["ci95_low"]):.4f}, {float(csr["ci95_high"]):.4f}]',
                "overall_completion_mean": f'{float(overall["mean"]):.4f}',
                "overall_completion_ci95": f'[{float(overall["ci95_low"]):.4f}, {float(overall["ci95_high"]):.4f}]',
                "el_mean": f'{float(episode_length["mean"]):.2f}',
                "el_std": f'{float(episode_length["std"]):.2f}',
                "el_ci95": f'[{float(episode_length["ci95_low"]):.2f}, {float(episode_length["ci95_high"]):.2f}]',
                "attempted_kb_mean": f'{float(traffic["mean"]) / 1000:.2f}',
                "attempted_kb_std": f'{float(traffic["std"]) / 1000:.2f}',
                "path_truth_error_mean": f'{float(error["mean"]):.4f}',
            })
    write_csv(table_directory / "care_external_baselines_primary.csv", primary)
    lines = [
        "# Published reconciliation baselines at 30% packet loss", "",
        "100 matched structured maps; mean ± sample SD and 20,000-draw map-cluster 95% CI. Seeker CSR is exactly derived from the audited observer/seeker pairing; overall completion is diagnostic only.", "",
        "| Planner | Method | Derived seeker CSR mean ± SD [95% CI] | Overall completion diagnostic [95% CI] | EL mean ± SD [95% CI] | Attempted KB mean ± SD | Path-truth error |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in primary:
        lines.append(
            f'| {row["planner"]} | {row["method"]} | '
            f'{row["seeker_csr_mean"]} ± {row["seeker_csr_std"]} {row["seeker_csr_ci95"]} | '
            f'{row["overall_completion_mean"]} {row["overall_completion_ci95"]} | '
            f'{row["el_mean"]} ± {row["el_std"]} {row["el_ci95"]} | '
            f'{row["attempted_kb_mean"]} ± {row["attempted_kb_std"]} | '
            f'{row["path_truth_error_mean"]} |'
        )
    (table_directory / "care_external_baselines_primary.md").write_text(
        "\n".join(lines) + "\n"
    )

    paired_lookup = {
        (
            int(row["observation_radius"]), row["planner"],
            float(row["loss_probability"]), row["left"],
            row["right"], row["metric"],
        ): row for row in paired
    }
    paired_rows = []
    for planner in ("astar", "dstar_lite"):
        for comparator in (
            "scuttlebutt_depth", "merkle_anti_entropy", "iblt_reconciliation",
        ):
            csr = paired_lookup[(
                2, planner, .3, "certificate_repair", comparator,
                "seeker_success_rate",
            )]
            traffic = paired_lookup[(
                2, planner, .3, "certificate_repair", comparator, "attempted_bytes",
            )]
            episode_length = paired_lookup[(
                2, planner, .3, "certificate_repair", comparator, "episode_length",
            )]
            paired_rows.append({
                "planner": "A*" if planner == "astar" else "D* Lite",
                "comparison": f'CARE - {LABELS[comparator]}',
                "seeker_csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                "seeker_csr_ci95": f'[{float(csr["ci95_low"]):+.4f}, {float(csr["ci95_high"]):+.4f}]',
                "seeker_csr_effect_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
                "el_difference": f'{float(episode_length["mean_difference"]):+.2f}',
                "el_ci95": f'[{float(episode_length["ci95_low"]):+.2f}, {float(episode_length["ci95_high"]):+.2f}]',
                "traffic_difference_kb": f'{float(traffic["mean_difference"]) / 1000:+.2f}',
                "traffic_ci95_kb": (
                    f'[{float(traffic["ci95_low"]) / 1000:+.2f}, '
                    f'{float(traffic["ci95_high"]) / 1000:+.2f}]'
                ),
            })
    write_csv(table_directory / "care_external_baselines_paired.csv", paired_rows)
    lines = [
        "# CARE paired against published reconciliation baselines at 30% loss", "",
        "Positive Δ derived seeker CSR favors CARE; negative ΔKB means CARE sends less traffic.", "",
        "| Planner | Comparison | Δ derived seeker CSR [95% CI] | paired d_z | ΔEL [95% CI] | ΔKB [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in paired_rows:
        lines.append(
            f'| {row["planner"]} | {row["comparison"]} | '
            f'{row["seeker_csr_difference"]} {row["seeker_csr_ci95"]} | '
            f'{row["seeker_csr_effect_dz"]} | {row["el_difference"]} {row["el_ci95"]} | '
            f'{row["traffic_difference_kb"]} '
            f'{row["traffic_ci95_kb"]} |'
        )
    (table_directory / "care_external_baselines_paired.md").write_text(
        "\n".join(lines) + "\n"
    )

    diagnostic_rows = [{
        "observation_radius": row["observation_radius"],
        "planner": "A*" if row["planner"] == "astar" else "D* Lite",
        "loss_probability": f'{float(row["loss_probability"]):.1f}',
        "iblt_decode_success_rate": f'{float(row["ratio"]):.4f}',
        "ci95": f'[{float(row["ci95_low"]):.4f}, {float(row["ci95_high"]):.4f}]',
        "successful_decodes": str(int(float(row["numerator"]))),
        "decode_attempts": str(int(float(row["denominator"]))),
    } for row in diagnostics]
    write_csv(table_directory / "care_external_protocol_diagnostics.csv", diagnostic_rows)

    fov_rows = []
    for radius in sorted({key[0] for key in lookup}):
        for planner in ("astar", "dstar_lite"):
            for policy in ORDER:
                csr = lookup[(radius, planner, .3, policy, "seeker_success_rate")]
                episode_length = lookup[(radius, planner, .3, policy, "episode_length")]
                traffic = lookup[(radius, planner, .3, policy, "attempted_bytes")]
                fov_rows.append({
                    "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "method": LABELS[policy],
                    "seeker_csr_mean": f'{float(csr["mean"]):.4f}',
                    "seeker_csr_std": f'{float(csr["std"]):.4f}',
                    "seeker_csr_ci95": f'[{float(csr["ci95_low"]):.4f}, {float(csr["ci95_high"]):.4f}]',
                    "el_mean": f'{float(episode_length["mean"]):.2f}',
                    "el_ci95": f'[{float(episode_length["ci95_low"]):.2f}, {float(episode_length["ci95_high"]):.2f}]',
                    "attempted_kb_mean": f'{float(traffic["mean"]) / 1000:.2f}',
                })
    write_csv(table_directory / "care_external_baselines_fov.csv", fov_rows)
    lines = [
        "# Published reconciliation baselines across sensing ranges at 30% loss", "",
        "Each cell uses 100 matched structured maps; reliability is derived seeker CSR.", "",
        "| FOV | Planner | Method | Derived seeker CSR mean ± SD [95% CI] | Mean EL [95% CI] | Attempted KB |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in fov_rows:
        lines.append(
            f'| {row["fov"]} | {row["planner"]} | {row["method"]} | '
            f'{row["seeker_csr_mean"]} ± {row["seeker_csr_std"]} {row["seeker_csr_ci95"]} | '
            f'{row["el_mean"]} {row["el_ci95"]} | '
            f'{row["attempted_kb_mean"]} |'
        )
    (table_directory / "care_external_baselines_fov.md").write_text(
        "\n".join(lines) + "\n"
    )

    fov_paired_rows = []
    for radius in sorted({key[0] for key in lookup}):
        for planner in ("astar", "dstar_lite"):
            for comparator in (
                "scuttlebutt_depth", "merkle_anti_entropy", "iblt_reconciliation",
            ):
                csr = paired_lookup[(
                    radius, planner, .3, "certificate_repair", comparator,
                    "seeker_success_rate",
                )]
                traffic = paired_lookup[(
                    radius, planner, .3, "certificate_repair", comparator,
                    "attempted_bytes",
                )]
                episode_length = paired_lookup[(
                    radius, planner, .3, "certificate_repair", comparator,
                    "episode_length",
                )]
                fov_paired_rows.append({
                    "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "comparison": f'CARE - {LABELS[comparator]}',
                    "seeker_csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                    "seeker_csr_ci95": (
                        f'[{float(csr["ci95_low"]):+.4f}, '
                        f'{float(csr["ci95_high"]):+.4f}]'
                    ),
                    "seeker_csr_effect_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
                    "el_difference": f'{float(episode_length["mean_difference"]):+.2f}',
                    "el_ci95": f'[{float(episode_length["ci95_low"]):+.2f}, {float(episode_length["ci95_high"]):+.2f}]',
                    "traffic_difference_kb": (
                        f'{float(traffic["mean_difference"]) / 1000:+.2f}'
                    ),
                    "traffic_ci95_kb": (
                        f'[{float(traffic["ci95_low"]) / 1000:+.2f}, '
                        f'{float(traffic["ci95_high"]) / 1000:+.2f}]'
                    ),
                })
    stem = "care_external_baselines_fov_paired"
    write_csv(table_directory / f"{stem}.csv", fov_paired_rows)
    markdown = [
        "# CARE paired against published reconciliation baselines across sensing ranges",
        "", "All comparisons use 30% loss and 100 matched maps. Positive Δ derived seeker CSR "
        "favors CARE; negative ΔKB means CARE sends less traffic.", "",
        "| FOV | Planner | Comparison | Δ derived seeker CSR [95% CI] | paired d_z | ΔEL [95% CI] | ΔKB [95% CI] |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in fov_paired_rows:
        markdown.append(
            f'| {row["fov"]} | {row["planner"]} | {row["comparison"]} | '
            f'{row["seeker_csr_difference"]} {row["seeker_csr_ci95"]} | '
            f'{row["seeker_csr_effect_dz"]} | {row["el_difference"]} {row["el_ci95"]} | '
            f'{row["traffic_difference_kb"]} '
            f'{row["traffic_ci95_kb"]} |'
        )
    (table_directory / f"{stem}.md").write_text("\n".join(markdown) + "\n")

    external_rows = []
    for radius in sorted({key[0] for key in lookup}):
        for planner in ("astar", "dstar_lite"):
            for external_policy in (
                "scuttlebutt_depth", "merkle_anti_entropy", "iblt_reconciliation",
            ):
                csr = paired_lookup[(
                    radius, planner, .3, external_policy, "one_shot_delta",
                    "seeker_success_rate",
                )]
                traffic = paired_lookup[(
                    radius, planner, .3, external_policy, "one_shot_delta",
                    "attempted_bytes",
                )]
                episode_length = paired_lookup[(
                    radius, planner, .3, external_policy, "one_shot_delta",
                    "episode_length",
                )]
                external_rows.append({
                    "fov": f"{2 * radius + 1}x{2 * radius + 1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "comparison": f'{LABELS[external_policy]} - One-shot',
                    "seeker_csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                    "seeker_csr_ci95": (
                        f'[{float(csr["ci95_low"]):+.4f}, '
                        f'{float(csr["ci95_high"]):+.4f}]'
                    ),
                    "seeker_csr_effect_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
                    "el_difference": f'{float(episode_length["mean_difference"]):+.2f}',
                    "el_ci95": f'[{float(episode_length["ci95_low"]):+.2f}, {float(episode_length["ci95_high"]):+.2f}]',
                    "traffic_difference_kb": (
                        f'{float(traffic["mean_difference"]) / 1000:+.2f}'
                    ),
                    "traffic_ci95_kb": (
                        f'[{float(traffic["ci95_low"]) / 1000:+.2f}, '
                        f'{float(traffic["ci95_high"]) / 1000:+.2f}]'
                    ),
                })
    stem = "care_external_baselines_vs_oneshot"
    write_csv(table_directory / f"{stem}.csv", external_rows)
    markdown = [
        "# Published reconciliation baselines paired against One-shot", "",
        "All comparisons use 30% loss and 100 matched maps. Positive Δ derived seeker CSR favors "
        "the external method; positive ΔKB means extra traffic.", "",
        "| FOV | Planner | Comparison | Δ derived seeker CSR [95% CI] | paired d_z | ΔEL [95% CI] | ΔKB [95% CI] |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in external_rows:
        markdown.append(
            f'| {row["fov"]} | {row["planner"]} | {row["comparison"]} | '
            f'{row["seeker_csr_difference"]} {row["seeker_csr_ci95"]} | '
            f'{row["seeker_csr_effect_dz"]} | {row["el_difference"]} {row["el_ci95"]} | '
            f'{row["traffic_difference_kb"]} '
            f'{row["traffic_ci95_kb"]} |'
        )
    (table_directory / f"{stem}.md").write_text("\n".join(markdown) + "\n")

    (table_directory / "care_external_baselines_manifest.json").write_text(
        json.dumps(json.loads(
            (analysis_directory / "analysis_manifest.json").read_text()
        ), indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, required=True)
    args = parser.parse_args()
    artifacts(args.analysis_directory, args.table_directory)


if __name__ == "__main__":
    main()
