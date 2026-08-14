#!/usr/bin/env python3
"""Create CARE cross-planner tables and paired delay-effect artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt


LABELS = {
    "one_shot_delta": "One-shot",
    "utility_triggered_repair": "PSR-UT",
    "deadline_aware_repair": "CARE-Lite",
    "certificate_repair": "CARE",
}
COLORS = {
    "one_shot_delta": "#777777",
    "utility_triggered_repair": "#D55E00",
    "deadline_aware_repair": "#0072B2",
    "certificate_repair": "#009E73",
}
PLANNERS = ("astar", "dstar_lite")
PLANNER_LABELS = {"astar": "A*", "dstar_lite": "D* Lite"}
DELAYS = (0, 1, 2, 4)
COMPARATORS = (
    "one_shot_delta", "utility_triggered_repair", "deadline_aware_repair",
)
STYLES = {
    "one_shot_delta": "-",
    "utility_triggered_repair": ":",
    "deadline_aware_repair": "--",
}


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, default=Path("paper/tables"))
    parser.add_argument("--figure-directory", type=Path, default=Path("paper/figures"))
    args = parser.parse_args()
    args.table_directory.mkdir(parents=True, exist_ok=True)
    args.figure_directory.mkdir(parents=True, exist_ok=True)
    (args.table_directory / "care_delay_gate.json").write_text(
        (args.analysis_directory / "gate_decision.json").read_text()
    )
    gate = json.loads((args.analysis_directory / "gate_decision.json").read_text())
    role_label = (
        "Direct seeker CSR" if gate["role_metric_provenance"].startswith("Direct")
        else "Derived seeker CSR"
    )
    role_delta_label = (
        "direct seeker CSR" if role_label.startswith("Direct")
        else "derived seeker CSR"
    )

    rows = list(csv.DictReader((args.analysis_directory / "summary_mean_std_ci.csv").open()))
    paired = list(csv.DictReader((args.analysis_directory / "paired_comparisons.csv").open()))
    lookup = {
        (row["planner"], int(row["delay_steps"]), row["policy"], row["metric"]): row
        for row in rows
    }
    paired_lookup = {
        (row["planner"], int(row["delay_steps"]), row["right"], row["metric"]): row
        for row in paired
    }
    output = []
    for planner in PLANNERS:
        for policy in LABELS:
            csr = lookup[(planner, 0, policy, "seeker_success_rate")]
            overall = lookup[(planner, 0, policy, "completion_success_rate")]
            episode_length = lookup[(planner, 0, policy, "episode_length")]
            traffic = lookup[(planner, 0, policy, "attempted_bytes")]
            cpu = lookup[(planner, 0, policy, "planning_cpu_ms")]
            output.append({
                "planner": planner, "method": LABELS[policy],
                "seeker_csr_mean": csr["mean"], "seeker_csr_std": csr["std"],
                "seeker_csr_ci95_low": csr["ci95_low"],
                "seeker_csr_ci95_high": csr["ci95_high"],
                "overall_completion_mean": overall["mean"],
                "overall_completion_ci95_low": overall["ci95_low"],
                "overall_completion_ci95_high": overall["ci95_high"],
                "el_mean": episode_length["mean"], "el_std": episode_length["std"],
                "el_ci95_low": episode_length["ci95_low"],
                "el_ci95_high": episode_length["ci95_high"],
                "attempted_kb_mean": float(traffic["mean"]) / 1_000,
                "attempted_kb_std": float(traffic["std"]) / 1_000,
                "planning_cpu_ms_mean": cpu["mean"],
            })
    csv_path = args.table_directory / "care_cross_planner_primary.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader(); writer.writerows(output)

    lines = [
        "# CARE cross-planner primary result", "",
        f"100 matched structured maps; 30% loss; zero link delay. {role_label} is primary; overall completion is diagnostic only. CIs bootstrap independent maps.", "",
        f"| Planner | Method | {role_label} mean ± SD [95% CI] | Overall completion diagnostic [95% CI] | EL mean ± SD [95% CI] | Attempted KB mean ± SD | Planning CPU ms |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in output:
        lines.append(
            f"| {row['planner']} | {row['method']} | "
            f"{float(row['seeker_csr_mean']):.4f} ± {float(row['seeker_csr_std']):.4f} "
            f"[{float(row['seeker_csr_ci95_low']):.4f}, {float(row['seeker_csr_ci95_high']):.4f}] | "
            f"{float(row['overall_completion_mean']):.4f} "
            f"[{float(row['overall_completion_ci95_low']):.4f}, "
            f"{float(row['overall_completion_ci95_high']):.4f}] | "
            f"{float(row['el_mean']):.2f} ± {float(row['el_std']):.2f} "
            f"[{float(row['el_ci95_low']):.2f}, {float(row['el_ci95_high']):.2f}] | "
            f"{float(row['attempted_kb_mean']):.2f} ± {float(row['attempted_kb_std']):.2f} | "
            f"{float(row['planning_cpu_ms_mean']):.2f} |"
        )
    (args.table_directory / "care_cross_planner_primary.md").write_text("\n".join(lines) + "\n")

    paired_output = []
    for planner in PLANNERS:
        for delay in DELAYS:
            for comparator in COMPARATORS:
                csr = paired_lookup[(planner, delay, comparator, "seeker_success_rate")]
                episode_length = paired_lookup[(planner, delay, comparator, "episode_length")]
                traffic = paired_lookup[(planner, delay, comparator, "attempted_bytes")]
                paired_output.append({
                    "planner": PLANNER_LABELS[planner],
                    "delay_steps": delay,
                    "comparison": f'CARE - {LABELS[comparator]}',
                    "paired_maps": csr["paired_maps"],
                    "seeker_csr_difference": f'{float(csr["mean_difference"]):+.4f}',
                    "seeker_csr_std_difference": f'{float(csr["std_difference"]):.4f}',
                    "seeker_csr_ci95": (
                        f'[{float(csr["ci95_low"]):+.4f}, '
                        f'{float(csr["ci95_high"]):+.4f}]'
                    ),
                    "seeker_csr_effect_dz": f'{float(csr["paired_effect_dz"]):+.3f}',
                    "el_difference": f'{float(episode_length["mean_difference"]):+.2f}',
                    "el_ci95": (
                        f'[{float(episode_length["ci95_low"]):+.2f}, '
                        f'{float(episode_length["ci95_high"]):+.2f}]'
                    ),
                    "traffic_kb_difference": (
                        f'{float(traffic["mean_difference"]) / 1000:+.2f}'
                    ),
                    "traffic_kb_ci95": (
                        f'[{float(traffic["ci95_low"]) / 1000:+.2f}, '
                        f'{float(traffic["ci95_high"]) / 1000:+.2f}]'
                    ),
                })
    _write_csv(args.table_directory / "care_delay_paired.csv", paired_output)
    paired_lines = [
        "# Paired CARE effects across one-way link delays", "",
        (
            "Every difference is CARE minus the matched comparator on the same "
            "100 maps and deterministic loss traces. Brackets are 20,000-draw "
            "paired map-cluster bootstrap 95% CIs."
        ), "",
        (
            f"| Planner | Delay | Comparison | Δ {role_delta_label} [95% CI] | paired d_z | "
            "ΔEL [95% CI] | ΔKB [95% CI] |"
        ),
        "| --- | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in paired_output:
        paired_lines.append(
            f'| {row["planner"]} | {row["delay_steps"]} | '
            f'{row["comparison"]} | {row["seeker_csr_difference"]} '
            f'{row["seeker_csr_ci95"]} | {row["seeker_csr_effect_dz"]} | '
            f'{row["el_difference"]} {row["el_ci95"]} | '
            f'{row["traffic_kb_difference"]} {row["traffic_kb_ci95"]} |'
        )
    (args.table_directory / "care_delay_paired.md").write_text(
        "\n".join(paired_lines) + "\n"
    )

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
    for axis, planner in zip(axes, PLANNERS):
        for comparator in COMPARATORS:
            points = [
                paired_lookup[(planner, delay, comparator, "seeker_success_rate")]
                for delay in DELAYS
            ]
            means = [float(point["mean_difference"]) for point in points]
            low = [float(point["ci95_low"]) for point in points]
            high = [float(point["ci95_high"]) for point in points]
            label = f'CARE − {LABELS[comparator]}'
            axis.plot(
                DELAYS, means, STYLES[comparator], marker="o", linewidth=1.8,
                label=label, color=COLORS[comparator],
            )
            axis.fill_between(
                DELAYS, low, high, alpha=.14, color=COLORS[comparator],
            )
        axis.axhline(0.0, color="#333333", linewidth=.9, alpha=.75)
        axis.set_title(PLANNER_LABELS[planner])
        axis.set_xlabel("One-way link delay (steps)")
        axis.set_xticks(DELAYS)
        axis.grid(alpha=.25)
    axes[0].set_ylabel(f"Δ {role_delta_label}")
    axes[1].legend(frameon=False, fontsize=7.5)
    fig.text(
        .5, .99, "Shading: paired map-cluster bootstrap 95% CI",
        ha="center", va="top", fontsize=8,
    )
    fig.tight_layout(rect=(0, 0, 1, .94))
    fig.savefig(args.figure_directory / "care_cross_planner_delay.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()
