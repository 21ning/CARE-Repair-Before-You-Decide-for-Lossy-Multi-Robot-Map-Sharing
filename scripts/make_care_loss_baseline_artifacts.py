#!/usr/bin/env python3
"""Build final loss-sweep tables and figures from audited CARE analysis."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter


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
            csr = lookup[(planner, .3, policy, "completion_success_rate")]
            traffic = lookup[(planner, .3, policy, "attempted_bytes")]
            primary_rows.append({
                "planner": PLANNER_LABELS[planner], "method": LABELS[policy],
                "csr_mean": f'{float(csr["mean"]):.4f}',
                "csr_std": f'{float(csr["std"]):.4f}',
                "csr_ci95": f'[{float(csr["ci95_low"]):.4f}, {float(csr["ci95_high"]):.4f}]',
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
        "| Planner | Method | CSR | Attempted traffic (KB) |", "| --- | --- | ---: | ---: |",
    ]
    for row in primary_rows:
        markdown.append(
            f'| {row["planner"]} | {row["method"]} | '
            f'{row["csr_mean"]} ± {row["csr_std"]} {row["csr_ci95"]} | '
            f'{row["attempted_kb_mean"]} ± {row["attempted_kb_std"]} '
            f'{row["attempted_kb_ci95"]} |'
        )
    (table_directory / "care_loss_baselines_primary.md").write_text("\n".join(markdown) + "\n")

    paired_rows = []
    for planner in PLANNERS:
        for comparator in POLICIES[:-1]:
            csr = paired_lookup[(planner, .3, comparator, "completion_success_rate")]
            traffic = paired_lookup[(planner, .3, comparator, "attempted_bytes")]
            paired_rows.append({
                "planner": PLANNER_LABELS[planner], "comparison": f'CARE - {LABELS[comparator]}',
                "csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                "csr_ci95": f'[{float(csr["ci95_low"]):+.4f}, {float(csr["ci95_high"]):+.4f}]',
                "csr_effect_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
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
        "| Planner | Comparison | CSR difference [95% CI] | Effect dz | Traffic difference KB [95% CI] |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in paired_rows:
        paired_markdown.append(
            f'| {row["planner"]} | {row["comparison"]} | '
            f'{row["csr_difference"]} {row["csr_ci95"]} | '
            f'{row["csr_effect_dz"]} | {row["traffic_kb_difference"]} '
            f'{row["traffic_kb_ci95"]} |'
        )
    (table_directory / "care_loss_baselines_paired.md").write_text(
        "\n".join(paired_markdown) + "\n"
    )

    colors = plt.cm.tab10.colors
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 7.2), sharex="col")
    for column, planner in enumerate(PLANNERS):
        for policy_index, policy in enumerate(POLICIES):
            losses = [0, .1, .2, .3, .4, .5]
            csr = [float(lookup[(planner, loss, policy, "completion_success_rate")]["mean"]) for loss in losses]
            traffic = [float(lookup[(planner, loss, policy, "attempted_bytes")]["mean"]) / 1000 for loss in losses]
            style = "-" if policy == "certificate_repair" else "--" if policy == "deadline_aware_repair" else ":"
            width = 2.8 if policy == "certificate_repair" else 1.5
            axes[0, column].plot(losses, csr, style, linewidth=width, marker="o", markersize=3,
                                 color=colors[policy_index], label=LABELS[policy])
            axes[1, column].plot(losses, traffic, style, linewidth=width, marker="o", markersize=3,
                                 color=colors[policy_index], label=LABELS[policy])
        axes[0, column].set_title(PLANNER_LABELS[planner])
        axes[0, column].set_ylabel("Completion success rate")
        axes[1, column].set_ylabel("Attempted traffic (KB)")
        axes[1, column].set_yscale("log")
        axes[1, column].set_ylim(50, 720)
        axes[1, column].set_yticks((50, 75, 100, 200, 400, 700))
        axes[1, column].yaxis.set_major_formatter(ScalarFormatter())
        axes[1, column].set_xlabel("Packet-loss probability")
        axes[0, column].grid(alpha=.2)
        axes[1, column].grid(alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, .91))
    fig.savefig(figure_directory / "care_loss_baseline_sweep.png", dpi=220)
    fig.savefig(figure_directory / "care_loss_baseline_sweep.pdf")
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
