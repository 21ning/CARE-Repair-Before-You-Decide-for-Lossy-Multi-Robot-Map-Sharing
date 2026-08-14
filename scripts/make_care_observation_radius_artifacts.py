#!/usr/bin/env python3
"""Create paper-ready CARE observation-radius tables and figure."""

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
    "action_triggered_repair", "full_replica_repair",
    "utility_triggered_repair", "deadline_aware_repair", "certificate_repair",
)
PLOT_POLICIES = (
    "one_shot_delta", "retry_all_arq", "periodic_full_sync",
    "utility_triggered_repair", "deadline_aware_repair", "certificate_repair",
)
LABELS = {
    "one_shot_delta": "One-shot", "retry_all_arq": "Retry-All ARQ",
    "path_weighted_arq": "Path-weighted ARQ", "periodic_full_sync": "Periodic Full",
    "mismatch_triggered_full_repair": "Mismatch Full",
    "action_triggered_repair": "Action-triggered",
    "full_replica_repair": "Full-replica scope", "utility_triggered_repair": "PSR-UT",
    "deadline_aware_repair": "CARE-Lite", "certificate_repair": "CARE",
}
PLANNER_LABELS = {"astar": "A*", "dstar_lite": "D* Lite"}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def make(analysis_directory: Path, table_directory: Path, figure_directory: Path) -> None:
    table_directory.mkdir(parents=True, exist_ok=True)
    figure_directory.mkdir(parents=True, exist_ok=True)
    (table_directory / "care_fov_manifest.json").write_text(
        (analysis_directory / "analysis_manifest.json").read_text()
    )
    summary = list(csv.DictReader((analysis_directory / "summary_mean_std_ci.csv").open()))
    paired = list(csv.DictReader((analysis_directory / "paired_comparisons.csv").open()))
    timing = list(csv.DictReader((analysis_directory / "causal_timing_and_cap.csv").open()))
    lookup = {
        (row["fov"], row["planner"], row["policy"], row["metric"]): row for row in summary
    }

    primary = []
    for planner in ("astar", "dstar_lite"):
        for policy in POLICIES:
            csr = lookup[("5x5", planner, policy, "seeker_success_rate")]
            overall = lookup[("5x5", planner, policy, "completion_success_rate")]
            episode_length = lookup[("5x5", planner, policy, "episode_length")]
            traffic = lookup[("5x5", planner, policy, "attempted_bytes")]
            primary.append({
                "planner": PLANNER_LABELS[planner], "method": LABELS[policy],
                "seeker_csr_mean": float(csr["mean"]),
                "seeker_csr_std": float(csr["std"]),
                "seeker_csr_ci95_low": float(csr["ci95_low"]),
                "seeker_csr_ci95_high": float(csr["ci95_high"]),
                "overall_completion_mean": float(overall["mean"]),
                "overall_completion_ci95_low": float(overall["ci95_low"]),
                "overall_completion_ci95_high": float(overall["ci95_high"]),
                "el_mean": float(episode_length["mean"]),
                "el_std": float(episode_length["std"]),
                "el_ci95_low": float(episode_length["ci95_low"]),
                "el_ci95_high": float(episode_length["ci95_high"]),
                "attempted_kb_mean": float(traffic["mean"]) / 1000,
                "attempted_kb_std": float(traffic["std"]) / 1000,
                "attempted_kb_ci95_low": float(traffic["ci95_low"]) / 1000,
                "attempted_kb_ci95_high": float(traffic["ci95_high"]) / 1000,
            })
    write_csv(table_directory / "care_fov_primary_5x5.csv", primary)
    lines = [
        "# CARE primary 5x5 observation results", "",
        "100 matched structured layouts; mean ± sample SD and map-cluster bootstrap 95% CI. Seeker CSR is exactly derived from the audited observer/seeker pairing; overall completion is diagnostic only.", "",
        "| Planner | Method | Derived seeker CSR mean ± SD [95% CI] | Overall completion diagnostic [95% CI] | EL mean ± SD [95% CI] | Attempted KB mean ± SD [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in primary:
        lines.append(
            f"| {row['planner']} | {row['method']} | {row['seeker_csr_mean']:.4f} ± {row['seeker_csr_std']:.4f} "
            f"[{row['seeker_csr_ci95_low']:.4f}, {row['seeker_csr_ci95_high']:.4f}] | "
            f"{row['overall_completion_mean']:.4f} "
            f"[{row['overall_completion_ci95_low']:.4f}, "
            f"{row['overall_completion_ci95_high']:.4f}] | "
            f"{row['el_mean']:.2f} ± {row['el_std']:.2f} "
            f"[{row['el_ci95_low']:.2f}, {row['el_ci95_high']:.2f}] | "
            f"{row['attempted_kb_mean']:.2f} ± {row['attempted_kb_std']:.2f} "
            f"[{row['attempted_kb_ci95_low']:.2f}, {row['attempted_kb_ci95_high']:.2f}] |"
        )
    (table_directory / "care_fov_primary_5x5.md").write_text("\n".join(lines) + "\n")

    range_rows = []
    for planner in ("astar", "dstar_lite"):
        for fov in ("3x3", "5x5", "7x7"):
            for policy in PLOT_POLICIES:
                csr = lookup[(fov, planner, policy, "seeker_success_rate")]
                episode_length = lookup[(fov, planner, policy, "episode_length")]
                traffic = lookup[(fov, planner, policy, "attempted_bytes")]
                range_rows.append({
                    "planner": PLANNER_LABELS[planner], "fov": fov, "method": LABELS[policy],
                    "seeker_csr_mean": float(csr["mean"]),
                    "seeker_csr_std": float(csr["std"]),
                    "seeker_csr_ci95_low": float(csr["ci95_low"]),
                    "seeker_csr_ci95_high": float(csr["ci95_high"]),
                    "el_mean": float(episode_length["mean"]),
                    "el_std": float(episode_length["std"]),
                    "el_ci95_low": float(episode_length["ci95_low"]),
                    "el_ci95_high": float(episode_length["ci95_high"]),
                    "attempted_kb_mean": float(traffic["mean"]) / 1000,
                    "attempted_kb_std": float(traffic["std"]) / 1000,
                    "attempted_kb_ci95_low": float(traffic["ci95_low"]) / 1000,
                    "attempted_kb_ci95_high": float(traffic["ci95_high"]) / 1000,
                })
    write_csv(table_directory / "care_fov_extension.csv", range_rows)
    range_lines = [
        "# Observation-range extension", "",
        "All conditions use 100 matched structured layouts and 30% loss. Reliability is derived seeker CSR; brackets are map-cluster bootstrap 95% CIs.", "",
        "| FOV | Planner | Method | Derived seeker CSR mean ± SD [95% CI] | EL mean ± SD [95% CI] | Attempted KB mean ± SD [95% CI] |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for row in range_rows:
        range_lines.append(
            f"| {row['fov']} | {row['planner']} | {row['method']} | "
            f"{row['seeker_csr_mean']:.4f} ± {row['seeker_csr_std']:.4f} "
            f"[{row['seeker_csr_ci95_low']:.4f}, {row['seeker_csr_ci95_high']:.4f}] | "
            f"{row['el_mean']:.2f} ± {row['el_std']:.2f} "
            f"[{row['el_ci95_low']:.2f}, {row['el_ci95_high']:.2f}] | "
            f"{row['attempted_kb_mean']:.2f} ± {row['attempted_kb_std']:.2f} "
            f"[{row['attempted_kb_ci95_low']:.2f}, {row['attempted_kb_ci95_high']:.2f}] |"
        )
    (table_directory / "care_fov_extension.md").write_text(
        "\n".join(range_lines) + "\n"
    )

    paired_rows = [row for row in paired if row["fov"] == "5x5" and row["metric"] in {
        "seeker_success_rate", "episode_length", "attempted_bytes",
    }]
    write_csv(table_directory / "care_fov_primary_paired.csv", paired_rows)
    paired_lines = [
        "# Paired 5x5 CARE comparisons", "",
        "Differences are CARE minus the matched method on the same map and loss trace; reliability rows use derived seeker CSR.", "",
        "| Planner | Comparator | Metric | Difference [95% CI] | paired d_z |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in paired_rows:
        scale = 1000.0 if row["metric"] == "attempted_bytes" else 1.0
        metric_label = {
            "seeker_success_rate": "Derived seeker CSR",
            "episode_length": "EL",
            "attempted_bytes": "Attempted KB",
        }[row["metric"]]
        paired_lines.append(
            f"| {PLANNER_LABELS[row['planner']]} | {LABELS[row['right']]} | "
            f"{metric_label} | {float(row['mean_difference']) / scale:+.4f} "
            f"[{float(row['ci95_low']) / scale:+.4f}, "
            f"{float(row['ci95_high']) / scale:+.4f}] | "
            f"{float(row['paired_effect_dz']):+.3f} |"
        )
    (table_directory / "care_fov_primary_paired.md").write_text(
        "\n".join(paired_lines) + "\n"
    )

    timing_rows = [row for row in timing if row["planner"] == "astar" and row["policy"] == "certificate_repair"]
    write_csv(table_directory / "care_fov_causal_timing.csv", timing_rows)
    timing_lines = [
        "# CARE causal timing and certificate diagnostics", "",
        "Event means are weighted by observed critical pairs; coverage prevents conditional timing from hiding missing events.", "",
        "| FOV | Diagnostic | Mean [95% CI] | Coverage |", "| --- | --- | ---: | ---: |",
    ]
    for row in timing_rows:
        timing_lines.append(
            f"| {row['fov']} | {row['metric']} | {float(row['event_weighted_mean']):.4f} "
            f"[{float(row['ci95_low']):.4f}, {float(row['ci95_high']):.4f}] | {float(row['coverage']):.3f} |"
        )
    (table_directory / "care_fov_causal_timing.md").write_text("\n".join(timing_lines) + "\n")

    colors = plt.cm.tab10.colors
    fig, axes = plt.subplots(2, 2, figsize=(9.2, 6.2), sharex=True)
    x = (3, 5, 7)
    for column, planner in enumerate(("astar", "dstar_lite")):
        for policy_index, policy in enumerate(PLOT_POLICIES):
            csr = [float(lookup[(f"{size}x{size}", planner, policy, "seeker_success_rate")]["mean"]) for size in x]
            traffic = [float(lookup[(f"{size}x{size}", planner, policy, "attempted_bytes")]["mean"]) / 1000 for size in x]
            width = 2.8 if policy == "certificate_repair" else 1.4
            axes[0, column].plot(x, csr, marker="o", linewidth=width, color=colors[policy_index], label=LABELS[policy])
            axes[1, column].plot(x, traffic, marker="o", linewidth=width, color=colors[policy_index], label=LABELS[policy])
        axes[0, column].set_title(PLANNER_LABELS[planner]); axes[0, column].set_ylabel("Derived seeker CSR")
        axes[1, column].set_ylabel("Attempted traffic (KB)"); axes[1, column].set_xlabel("Observation width")
        axes[1, column].set_yscale("log")
        for axis in axes[:, column]:
            axis.set_xticks(x); axis.grid(alpha=.2)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0, 1, .89))
    fig.savefig(figure_directory / "care_observation_radius.png", dpi=220)
    fig.savefig(
        figure_directory / "care_observation_radius.pdf",
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
