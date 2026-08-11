#!/usr/bin/env python3
"""Create compact paper tables for CARE ablations and extensions."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


LABELS = {
    "trigger_to_action": "Certificate trigger -> immediate-action trigger",
    "scope_to_full_replica": "Certificate scope -> full-replica scope",
    "utility_heuristic": "Exact certificate -> PSR-UT heuristic",
    "deadline_heuristic": "Exact certificate -> CARE-Lite heuristic",
    "certificate_cadence_k4": "Cadence K=1 -> K=4",
    "certificate_q1_cap8": "Uncertainty order q=2 -> q=1",
    "certificate_q2_cap4": "Candidate cap 8 -> 4",
    "certificate_q2_cap12": "Candidate cap 8 -> 12",
}
PLANNERS = {"astar": "A*", "dstar_lite": "D* Lite"}


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def make(analysis_directory: Path, table_directory: Path, figure_directory: Path) -> None:
    table_directory.mkdir(parents=True, exist_ok=True)
    figure_directory.mkdir(parents=True, exist_ok=True)
    (table_directory / "care_extensions_manifest.json").write_text(
        (analysis_directory / "analysis_manifest.json").read_text()
    )
    summary = list(csv.DictReader((analysis_directory / "summary_mean_std_ci.csv").open()))
    ablations = list(csv.DictReader((analysis_directory / "paired_full_method_ablations.csv").open()))
    paired = list(csv.DictReader((analysis_directory / "paired_extension_comparisons.csv").open()))

    ablation_lookup = {(row["planner"], row["ablation"], row["metric"]): row for row in ablations}
    ablation_rows = []
    for planner in PLANNERS:
        for ablation, label in LABELS.items():
            csr = ablation_lookup[(planner, ablation, "completion_success_rate")]
            episode_length = ablation_lookup[(planner, ablation, "episode_length")]
            traffic = ablation_lookup[(planner, ablation, "attempted_bytes")]
            cpu = ablation_lookup[(planner, ablation, "episode_cpu_ms")]
            ablation_rows.append({
                "planner": PLANNERS[planner], "ablation": label,
                "delta_csr": float(csr["mean_difference"]),
                "delta_csr_ci95_low": float(csr["ci95_low"]),
                "delta_csr_ci95_high": float(csr["ci95_high"]),
                "delta_el": float(episode_length["mean_difference"]),
                "delta_el_ci95_low": float(episode_length["ci95_low"]),
                "delta_el_ci95_high": float(episode_length["ci95_high"]),
                "delta_attempted_kb": float(traffic["mean_difference"]) / 1000,
                "delta_attempted_kb_ci95_low": float(traffic["ci95_low"]) / 1000,
                "delta_attempted_kb_ci95_high": float(traffic["ci95_high"]) / 1000,
                "delta_episode_cpu_ms": float(cpu["mean_difference"]),
                "delta_episode_cpu_ms_ci95_low": float(cpu["ci95_low"]),
                "delta_episode_cpu_ms_ci95_high": float(cpu["ci95_high"]),
            })
    write_csv(table_directory / "care_full_method_ablations.csv", ablation_rows)
    lines = [
        "# CARE paired full-method ablations", "",
        "Every difference is full CARE (q=2, cap=8, K=1) minus the named matched ablation on the same 100 maps and loss traces.", "",
        "| Planner | Ablation | ΔCSR [95% CI] | ΔEL [95% CI] | Δ attempted KB [95% CI] | Δ episode CPU ms [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in ablation_rows:
        lines.append(
            f"| {row['planner']} | {row['ablation']} | {row['delta_csr']:+.4f} "
            f"[{row['delta_csr_ci95_low']:+.4f}, {row['delta_csr_ci95_high']:+.4f}] | "
            f"{row['delta_el']:+.2f} [{row['delta_el_ci95_low']:+.2f}, "
            f"{row['delta_el_ci95_high']:+.2f}] | "
            f"{row['delta_attempted_kb']:+.2f} [{row['delta_attempted_kb_ci95_low']:+.2f}, "
            f"{row['delta_attempted_kb_ci95_high']:+.2f}] | {row['delta_episode_cpu_ms']:+.2f} "
            f"[{row['delta_episode_cpu_ms_ci95_low']:+.2f}, {row['delta_episode_cpu_ms_ci95_high']:+.2f}] |"
        )
    (table_directory / "care_full_method_ablations.md").write_text("\n".join(lines) + "\n")

    summary_lookup = {(row["study"], row["planner"], row["policy"], row["metric"]): row for row in summary}
    paired_lookup = {(row["study"], row["planner"], row["right"], row["metric"]): row for row in paired}
    extension_rows = []
    ordered_studies = (
        *(f"density_{value:02d}" for value in (10, 20, 30, 40)),
        "topology_t_junction", "topology_asymmetric_fork", "topology_narrow_bypass",
        *(f"scale_agents_{agents}_map_{size}" for agents, size in ((4, 24), (8, 32), (16, 48), (32, 64))),
        *(f"random_negative_density_{value:02d}" for value in (10, 20, 30, 40)),
    )
    for study in ordered_studies:
        planners = ("astar", "dstar_lite") if (study.startswith("density_") or study.startswith("topology_")) else ("astar",)
        for planner in planners:
            csr = summary_lookup[(study, planner, "certificate_repair", "completion_success_rate")]
            episode_length = summary_lookup[(study, planner, "certificate_repair", "episode_length")]
            traffic = summary_lookup[(study, planner, "certificate_repair", "attempted_bytes")]
            one_shot = paired_lookup[(study, planner, "one_shot_delta", "completion_success_rate")]
            one_shot_el = paired_lookup[(study, planner, "one_shot_delta", "episode_length")]
            extension_rows.append({
                "study": study, "planner": PLANNERS[planner],
                "care_csr_mean": float(csr["mean"]), "care_csr_std": float(csr["std"]),
                "care_csr_ci95_low": float(csr["ci95_low"]), "care_csr_ci95_high": float(csr["ci95_high"]),
                "care_el_mean": float(episode_length["mean"]),
                "care_el_std": float(episode_length["std"]),
                "care_el_ci95_low": float(episode_length["ci95_low"]),
                "care_el_ci95_high": float(episode_length["ci95_high"]),
                "care_attempted_kb_mean": float(traffic["mean"]) / 1000,
                "delta_csr_vs_one_shot": float(one_shot["mean_difference"]),
                "delta_csr_ci95_low": float(one_shot["ci95_low"]),
                "delta_csr_ci95_high": float(one_shot["ci95_high"]),
                "delta_el_vs_one_shot": float(one_shot_el["mean_difference"]),
                "delta_el_ci95_low": float(one_shot_el["ci95_low"]),
                "delta_el_ci95_high": float(one_shot_el["ci95_high"]),
            })
    write_csv(table_directory / "care_extensions.csv", extension_rows)
    extension_lines = [
        "# CARE density, topology, scale, and random-map extensions", "",
        "All cells use 100 physically distinct maps. ΔCSR is paired CARE minus One-shot.", "",
        "| Study | Planner | CARE CSR mean ± SD [95% CI] | CARE EL mean ± SD [95% CI] | Attempted KB | ΔCSR vs One-shot [95% CI] | ΔEL vs One-shot [95% CI] |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in extension_rows:
        extension_lines.append(
            f"| {row['study']} | {row['planner']} | {row['care_csr_mean']:.4f} ± {row['care_csr_std']:.4f} "
            f"[{row['care_csr_ci95_low']:.4f}, {row['care_csr_ci95_high']:.4f}] | "
            f"{row['care_el_mean']:.2f} ± {row['care_el_std']:.2f} "
            f"[{row['care_el_ci95_low']:.2f}, {row['care_el_ci95_high']:.2f}] | "
            f"{row['care_attempted_kb_mean']:.2f} | {row['delta_csr_vs_one_shot']:+.4f} "
            f"[{row['delta_csr_ci95_low']:+.4f}, {row['delta_csr_ci95_high']:+.4f}] | "
            f"{row['delta_el_vs_one_shot']:+.2f} [{row['delta_el_ci95_low']:+.2f}, "
            f"{row['delta_el_ci95_high']:+.2f}] |"
        )
    (table_directory / "care_extensions.md").write_text("\n".join(extension_lines) + "\n")

    fig, axes = plt.subplots(1, 3, figsize=(10.2, 3.0))
    for planner, color in (("astar", "#0072B2"), ("dstar_lite", "#D55E00")):
        points = [summary_lookup[(f"density_{value:02d}", planner, "certificate_repair", "completion_success_rate")] for value in (10, 20, 30, 40)]
        axes[0].plot((.1, .2, .3, .4), [float(point["mean"]) for point in points], marker="o", label=PLANNERS[planner], color=color)
    topo = ("t_junction", "asymmetric_fork", "narrow_bypass")
    axes[1].bar(range(3), [float(summary_lookup[(f"topology_{name}", "astar", "certificate_repair", "completion_success_rate")]["mean"]) for name in topo], color="#009E73")
    axes[1].set_xticks(range(3), ("T", "Asym.", "Bypass"))
    scale = ((4, 24), (8, 32), (16, 48), (32, 64))
    axes[2].plot([agents for agents, _ in scale], [float(summary_lookup[(f"scale_agents_{agents}_map_{size}", "astar", "certificate_repair", "completion_success_rate")]["mean"]) for agents, size in scale], marker="o", color="#CC79A7")
    axes[0].set_xlabel("Obstacle density"); axes[1].set_xlabel("Decision topology"); axes[2].set_xlabel("Agents")
    for axis in axes:
        axis.set_ylabel("CARE completion success rate"); axis.grid(alpha=.2)
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(figure_directory / "care_extensions.png", dpi=220)
    fig.savefig(figure_directory / "care_extensions.pdf")
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
