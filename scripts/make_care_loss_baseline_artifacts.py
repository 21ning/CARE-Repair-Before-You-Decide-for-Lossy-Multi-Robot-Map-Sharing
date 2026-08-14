#!/usr/bin/env python3
"""Build final loss-sweep tables and figures from audited CARE analysis."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


POLICIES = (
    "one_shot_delta", "retry_all_arq", "path_weighted_arq",
    "periodic_full_sync", "mismatch_triggered_full_repair",
    "utility_triggered_repair", "deadline_aware_repair", "certificate_repair",
)
LABELS = {
    "one_shot_delta": "One-shot",
    "retry_all_arq": "Retry-All ARQ",
    "path_weighted_arq": "Path-weighted ARQ",
    "periodic_full_sync": "Periodic Full",
    "mismatch_triggered_full_repair": "Mismatch Full",
    "utility_triggered_repair": "PSR-UT",
    "deadline_aware_repair": "CARE-Lite",
    "certificate_repair": "CARE",
}
PLANNERS = ("astar", "dstar_lite")
PLANNER_LABELS = {"astar": "A*", "dstar_lite": "D* Lite"}
LOSSES = (0.0, .1, .2, .3, .4, .5)
FIGURE_COMPARATORS = (
    "one_shot_delta", "deadline_aware_repair", "retry_all_arq",
)
FIGURE_COLORS = {
    "one_shot_delta": "#0072B2",
    "deadline_aware_repair": "#D55E00",
    "retry_all_arq": "#6F4C9B",
}
FIGURE_STYLES = {
    "one_shot_delta": "-",
    "deadline_aware_repair": "--",
    "retry_all_arq": ":",
}


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make(analysis_directory: Path, table_directory: Path, figure_directory: Path) -> None:
    summary = list(csv.DictReader((analysis_directory / "summary_mean_std_ci.csv").open()))
    paired = list(csv.DictReader((analysis_directory / "paired_comparisons.csv").open()))
    lookup = {
        (row["planner"], float(row["loss_probability"]), row["policy"], row["metric"]): row
        for row in summary
    }
    paired_lookup = {
        (row["planner"], float(row["loss_probability"]), row["right"], row["metric"]): row
        for row in paired
    }
    table_directory.mkdir(parents=True, exist_ok=True)
    figure_directory.mkdir(parents=True, exist_ok=True)
    (table_directory / "care_loss_baselines_manifest.json").write_text(
        (analysis_directory / "analysis_manifest.json").read_text()
    )

    primary_rows = []
    for planner in PLANNERS:
        for policy in POLICIES:
            csr = lookup[(planner, .3, policy, "seeker_success_rate")]
            overall = lookup[(planner, .3, policy, "completion_success_rate")]
            episode_length = lookup[(planner, .3, policy, "episode_length")]
            traffic = lookup[(planner, .3, policy, "attempted_bytes")]
            primary_rows.append({
                "planner": PLANNER_LABELS[planner], "method": LABELS[policy],
                "csr_mean": f'{float(csr["mean"]):.4f}',
                "csr_std": f'{float(csr["std"]):.4f}',
                "csr_ci95": f'[{float(csr["ci95_low"]):.4f}, {float(csr["ci95_high"]):.4f}]',
                "overall_csr": f'{float(overall["mean"]):.4f}',
                "el_mean": f'{float(episode_length["mean"]):.2f}',
                "el_std": f'{float(episode_length["std"]):.2f}',
                "el_ci95": (
                    f'[{float(episode_length["ci95_low"]):.2f}, '
                    f'{float(episode_length["ci95_high"]):.2f}]'
                ),
                "attempted_kb_mean": f'{float(traffic["mean"]) / 1000:.2f}',
                "attempted_kb_std": f'{float(traffic["std"]) / 1000:.2f}',
                "attempted_kb_ci95": (
                    f'[{float(traffic["ci95_low"]) / 1000:.2f}, '
                    f'{float(traffic["ci95_high"]) / 1000:.2f}]'
                ),
            })
    _write_csv(table_directory / "care_loss_baselines_primary.csv", primary_rows)
    markdown = [
        "# CARE baseline comparison at 30% packet loss", "",
        "Each condition uses 100 independent maps. Values are mean ± sample SD; ",
        "brackets give a 20,000-draw map-cluster bootstrap 95% CI.", "",
        "Primary endpoint is seeker-only CSR; overall CSR is retained only as a diagnostic.", "",
        "| Planner | Method | Seeker CSR | Overall CSR | Mean EL | Attempted traffic (KB) |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in primary_rows:
        markdown.append(
            f'| {row["planner"]} | {row["method"]} | '
            f'{row["csr_mean"]} ± {row["csr_std"]} {row["csr_ci95"]} | {row["overall_csr"]} | '
            f'{row["el_mean"]} ± {row["el_std"]} {row["el_ci95"]} | '
            f'{row["attempted_kb_mean"]} ± {row["attempted_kb_std"]} '
            f'{row["attempted_kb_ci95"]} |'
        )
    (table_directory / "care_loss_baselines_primary.md").write_text("\n".join(markdown) + "\n")

    paired_rows = []
    for planner in PLANNERS:
        for comparator in POLICIES[:-1]:
            csr = paired_lookup[(planner, .3, comparator, "seeker_success_rate")]
            episode_length = paired_lookup[(planner, .3, comparator, "episode_length")]
            traffic = paired_lookup[(planner, .3, comparator, "attempted_bytes")]
            paired_rows.append({
                "planner": PLANNER_LABELS[planner], "comparison": f'CARE - {LABELS[comparator]}',
                "csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                "csr_ci95": f'[{float(csr["ci95_low"]):+.4f}, {float(csr["ci95_high"]):+.4f}]',
                "csr_effect_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
                "el_difference": f'{float(episode_length["mean_difference"]):+.2f}',
                "el_ci95": (
                    f'[{float(episode_length["ci95_low"]):+.2f}, '
                    f'{float(episode_length["ci95_high"]):+.2f}]'
                ),
                "traffic_kb_difference": f'{float(traffic["mean_difference"]) / 1000:+.2f}',
                "traffic_kb_ci95": (
                    f'[{float(traffic["ci95_low"]) / 1000:+.2f}, '
                    f'{float(traffic["ci95_high"]) / 1000:+.2f}]'
                ),
            })
    _write_csv(table_directory / "care_loss_baselines_paired.csv", paired_rows)
    paired_markdown = [
        "# Paired CARE comparisons at 30% packet loss", "",
        "Differences are CARE minus the matched comparator on each of 100 maps.", "",
        "| Planner | Comparison | Seeker-CSR difference [95% CI] | Effect dz | EL difference [95% CI] | Traffic difference KB [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in paired_rows:
        paired_markdown.append(
            f'| {row["planner"]} | {row["comparison"]} | '
            f'{row["csr_difference"]} {row["csr_ci95"]} | '
            f'{row["csr_effect_dz"]} | {row["el_difference"]} {row["el_ci95"]} | '
            f'{row["traffic_kb_difference"]} '
            f'{row["traffic_kb_ci95"]} |'
        )
    (table_directory / "care_loss_baselines_paired.md").write_text(
        "\n".join(paired_markdown) + "\n"
    )

    sweep_rows = []
    for planner in PLANNERS:
        for loss in LOSSES:
            for comparator in POLICIES[:-1]:
                csr = paired_lookup[(planner, loss, comparator, "seeker_success_rate")]
                episode_length = paired_lookup[(planner, loss, comparator, "episode_length")]
                traffic = paired_lookup[(planner, loss, comparator, "attempted_bytes")]
                sweep_rows.append({
                    "planner": PLANNER_LABELS[planner],
                    "loss_probability": f"{loss:.1f}",
                    "comparison": f'CARE - {LABELS[comparator]}',
                    "paired_maps": csr["paired_maps"],
                    "csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                    "csr_std_difference": f'{float(csr["std_difference"]):.4f}',
                    "csr_ci95": (
                        f'[{float(csr["ci95_low"]):+.4f}, '
                        f'{float(csr["ci95_high"]):+.4f}]'
                    ),
                    "csr_effect_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
                    "el_difference": f'{float(episode_length["mean_difference"]):+.2f}',
                    "el_ci95": (
                        f'[{float(episode_length["ci95_low"]):+.2f}, '
                        f'{float(episode_length["ci95_high"]):+.2f}]'
                    ),
                    "traffic_kb_difference": (
                        f'{float(traffic["mean_difference"]) / 1000:+.2f}'
                    ),
                    "traffic_kb_std_difference": (
                        f'{float(traffic["std_difference"]) / 1000:.2f}'
                    ),
                    "traffic_kb_ci95": (
                        f'[{float(traffic["ci95_low"]) / 1000:+.2f}, '
                        f'{float(traffic["ci95_high"]) / 1000:+.2f}]'
                    ),
                })
    _write_csv(table_directory / "care_loss_paired_sweep.csv", sweep_rows)
    sweep_markdown = [
        "# Paired CARE effects across packet-loss rates", "",
        (
            "Every difference is CARE minus the matched comparator on the same "
            "100 maps and deterministic loss traces. Brackets are 20,000-draw "
            "paired map-cluster bootstrap 95% CIs."
        ), "",
        (
            "| Planner | Loss | Comparison | Δ seeker CSR [95% CI] | paired d_z | "
            "ΔEL [95% CI] | ΔKB [95% CI] |"
        ),
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in sweep_rows:
        sweep_markdown.append(
            f'| {row["planner"]} | {row["loss_probability"]} | '
            f'{row["comparison"]} | {row["csr_difference"]} '
            f'{row["csr_ci95"]} | {row["csr_effect_dz"]} | '
            f'{row["el_difference"]} {row["el_ci95"]} | '
            f'{row["traffic_kb_difference"]} {row["traffic_kb_ci95"]} |'
        )
    (table_directory / "care_loss_paired_sweep.md").write_text(
        "\n".join(sweep_markdown) + "\n"
    )

    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), sharex="col")
    for column, planner in enumerate(PLANNERS):
        for comparator in FIGURE_COMPARATORS:
            csr_points = [
                paired_lookup[(planner, loss, comparator, "seeker_success_rate")]
                for loss in LOSSES
            ]
            traffic_points = [
                paired_lookup[(planner, loss, comparator, "attempted_bytes")]
                for loss in LOSSES
            ]
            csr = [float(point["mean_difference"]) for point in csr_points]
            csr_low = [float(point["ci95_low"]) for point in csr_points]
            csr_high = [float(point["ci95_high"]) for point in csr_points]
            traffic = [float(point["mean_difference"]) / 1000 for point in traffic_points]
            traffic_low = [float(point["ci95_low"]) / 1000 for point in traffic_points]
            traffic_high = [float(point["ci95_high"]) / 1000 for point in traffic_points]
            label = f'CARE − {LABELS[comparator]}'
            color = FIGURE_COLORS[comparator]
            style = FIGURE_STYLES[comparator]
            axes[0, column].plot(
                LOSSES, csr, style, linewidth=2.0, marker="o", markersize=3.5,
                color=color, label=label,
            )
            axes[0, column].fill_between(
                LOSSES, csr_low, csr_high, alpha=.14, color=color,
            )
            axes[1, column].plot(
                LOSSES, traffic, style, linewidth=2.0, marker="o", markersize=3.5,
                color=color, label=label,
            )
            axes[1, column].fill_between(
                LOSSES, traffic_low, traffic_high, alpha=.14, color=color,
            )
        axes[0, column].set_title(PLANNER_LABELS[planner])
        axes[0, column].set_ylabel("Δ seeker completion rate")
        axes[1, column].set_ylabel("Δ attempted traffic (KB)")
        axes[1, column].set_xlabel("Packet-loss probability")
        axes[0, column].axhline(0.0, color="#333333", linewidth=.9, alpha=.75)
        axes[1, column].axhline(0.0, color="#333333", linewidth=.9, alpha=.75)
        axes[0, column].grid(alpha=.2)
        axes[1, column].grid(alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.text(
        .5, .925, "Shading: paired map-cluster bootstrap 95% CI",
        ha="center", va="center", fontsize=9,
    )
    fig.tight_layout(rect=(0, 0, 1, .89))
    fig.savefig(figure_directory / "care_loss_baseline_sweep.png", dpi=220)
    fig.savefig(
        figure_directory / "care_loss_baseline_sweep.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, required=True)
    parser.add_argument("--figure-directory", type=Path, required=True)
    args = parser.parse_args()
    make(args.analysis_directory, args.table_directory, args.figure_directory)


if __name__ == "__main__":
    main()
