#!/usr/bin/env python3
"""Create the CARE cross-planner paper table and delay figure."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


LABELS = {
    "one_shot_delta": "One-shot",
    "utility_triggered_repair": "PSR-UT",
    "deadline_aware_repair": "CARE",
}
COLORS = {
    "one_shot_delta": "#777777",
    "utility_triggered_repair": "#D55E00",
    "deadline_aware_repair": "#0072B2",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, default=Path("paper/tables"))
    parser.add_argument("--figure-directory", type=Path, default=Path("paper/figures"))
    args = parser.parse_args()
    args.table_directory.mkdir(parents=True, exist_ok=True)
    args.figure_directory.mkdir(parents=True, exist_ok=True)

    rows = list(csv.DictReader((args.analysis_directory / "summary_mean_std_ci.csv").open()))
    lookup = {
        (row["planner"], int(row["delay_steps"]), row["policy"], row["metric"]): row
        for row in rows
    }
    output = []
    for planner in ("astar", "dstar_lite"):
        for policy in LABELS:
            csr = lookup[(planner, 0, policy, "completion_success_rate")]
            traffic = lookup[(planner, 0, policy, "attempted_bytes")]
            cpu = lookup[(planner, 0, policy, "planning_cpu_ms")]
            output.append({
                "planner": planner, "method": LABELS[policy],
                "csr_mean": csr["mean"], "csr_std": csr["std"],
                "csr_ci95_low": csr["ci95_low"], "csr_ci95_high": csr["ci95_high"],
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
        "100 independent maps; 30% loss; zero link delay. CIs bootstrap independent maps.", "",
        "| Planner | Method | CSR mean ± SD [95% CI] | Attempted KB mean ± SD | Planning CPU ms |",
        "|---|---|---:|---:|---:|",
    ]
    for row in output:
        lines.append(
            f"| {row['planner']} | {row['method']} | "
            f"{float(row['csr_mean']):.4f} ± {float(row['csr_std']):.4f} "
            f"[{float(row['csr_ci95_low']):.4f}, {float(row['csr_ci95_high']):.4f}] | "
            f"{float(row['attempted_kb_mean']):.2f} ± {float(row['attempted_kb_std']):.2f} | "
            f"{float(row['planning_cpu_ms_mean']):.2f} |"
        )
    (args.table_directory / "care_cross_planner_primary.md").write_text("\n".join(lines) + "\n")

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), sharey=True)
    for axis, planner in zip(axes, ("astar", "dstar_lite")):
        for policy in LABELS:
            points = [lookup[(planner, delay, policy, "completion_success_rate")] for delay in (0, 1, 2, 4)]
            means = [float(point["mean"]) for point in points]
            low = [float(point["ci95_low"]) for point in points]
            high = [float(point["ci95_high"]) for point in points]
            axis.plot((0, 1, 2, 4), means, marker="o", linewidth=1.8, label=LABELS[policy], color=COLORS[policy])
            axis.fill_between((0, 1, 2, 4), low, high, alpha=.12, color=COLORS[policy])
        axis.set_title("A*" if planner == "astar" else "D* Lite")
        axis.set_xlabel("One-way link delay (steps)")
        axis.set_xticks((0, 1, 2, 4))
        axis.grid(alpha=.25)
    axes[0].set_ylabel("Completion success rate")
    axes[1].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(args.figure_directory / "care_cross_planner_delay.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()
