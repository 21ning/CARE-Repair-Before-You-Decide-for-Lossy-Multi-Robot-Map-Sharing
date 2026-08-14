#!/usr/bin/env python3
"""Build tables and figures for non-tiled natural-critical validation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import shutil

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


LABELS = {
    "no_communication": "No Communication", "one_shot_delta": "One-shot",
    "retry_all_arq": "Retry-All", "periodic_full_sync": "Periodic Full",
    "path_aware_top_k_repair": "Path-Aware Top-K",
    "single_cell_sensitivity_repair": "Single-Cell",
    "deadline_aware_repair": "CARE-Lite", "certificate_repair": "CARE",
}


def _read(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open()))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def artifacts(analysis: Path, tables: Path, figures: Path) -> None:
    tables.mkdir(parents=True, exist_ok=True); figures.mkdir(parents=True, exist_ok=True)
    manifests = tables.parent / "manifests"
    manifests.mkdir(parents=True, exist_ok=True)
    primary = _read(analysis / "primary" / "summary_mean_std_ci.csv")
    primary_paired = _read(analysis / "primary" / "paired_comparisons.csv")
    scale = _read(analysis / "scale" / "summary_mean_std_ci.csv")
    scale_paired = _read(analysis / "scale" / "paired_comparisons.csv")
    p = {(r["planner"], r["policy"], r["metric"]): r for r in primary}
    pp = {(r["planner"], r["right"], r["metric"]): r for r in primary_paired}
    s = {(int(r["num_agents"]), r["planner"], r["policy"], r["metric"]): r for r in scale}
    sp = {(int(r["num_agents"]), r["planner"], r["right"], r["metric"]): r for r in scale_paired}

    rows = []
    for planner in ("astar", "dstar_lite"):
        for policy in LABELS:
            seeker, el, traffic = (p[(planner, policy, metric)] for metric in (
                "seeker_success_rate", "episode_length", "attempted_bytes",
            ))
            rows.append({
                "planner": "A*" if planner == "astar" else "D* Lite",
                "method": LABELS[policy],
                "seeker_csr": f'{float(seeker["mean"]):.4f} ± {float(seeker["std"]):.4f}',
                "seeker_ci95": f'[{float(seeker["ci95_low"]):.4f}, {float(seeker["ci95_high"]):.4f}]',
                "el": f'{float(el["mean"]):.2f} ± {float(el["std"]):.2f}',
                "traffic_kb": f'{float(traffic["mean"])/1000:.2f}',
            })
    _write(tables / "care_natural_primary.csv", rows)
    lines = [
        "# Natural non-tiled external validity", "",
        "100 untouched Bernoulli maps conditioned on a predeclared action-conflict, visibility, path-length, communication-window, and disjointness predicate bundle.", "",
        "| Planner | Method | Seeker CSR mean ± SD [95% CI] | EL mean ± SD | Attempted KB |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(f'| {row["planner"]} | {row["method"]} | {row["seeker_csr"]} {row["seeker_ci95"]} | {row["el"]} | {row["traffic_kb"]} |')
    (tables / "care_natural_primary.md").write_text("\n".join(lines) + "\n")

    effects = []
    for planner in ("astar", "dstar_lite"):
        for comparator in tuple(LABELS)[:-1]:
            seeker = pp[(planner, comparator, "seeker_success_rate")]
            traffic = pp[(planner, comparator, "attempted_bytes")]
            effects.append({
                "planner": "A*" if planner == "astar" else "D* Lite",
                "comparison": f'CARE - {LABELS[comparator]}',
                "delta_seeker_csr": f'{float(seeker["mean_difference"]):+.4f}',
                "seeker_ci95": f'[{float(seeker["ci95_low"]):+.4f}, {float(seeker["ci95_high"]):+.4f}]',
                "paired_dz": f'{float(seeker["paired_effect_dz"]):+.3f}',
                "delta_kb": f'{float(traffic["mean_difference"])/1000:+.2f}',
                "kb_ci95": f'[{float(traffic["ci95_low"])/1000:+.2f}, {float(traffic["ci95_high"])/1000:+.2f}]',
            })
    _write(tables / "care_natural_paired.csv", effects)
    lines = ["# CARE paired effects on natural maps", "", "| Planner | Comparison | Δ seeker CSR [95% CI] | d_z | ΔKB [95% CI] |", "| --- | --- | ---: | ---: | ---: |"]
    for row in effects:
        lines.append(f'| {row["planner"]} | {row["comparison"]} | {row["delta_seeker_csr"]} {row["seeker_ci95"]} | {row["paired_dz"]} | {row["delta_kb"]} {row["kb_ci95"]} |')
    (tables / "care_natural_paired.md").write_text("\n".join(lines) + "\n")

    scale_rows = []
    for agents in (4, 8, 16, 32):
        for planner in ("astar", "dstar_lite"):
            for policy in ("one_shot_delta", "certificate_repair"):
                seeker = s[(agents, planner, policy, "seeker_success_rate")]
                traffic = s[(agents, planner, policy, "attempted_bytes")]
                scale_rows.append({
                    "agents": str(agents), "planner": "A*" if planner == "astar" else "D* Lite",
                    "method": LABELS[policy], "seeker_csr": f'{float(seeker["mean"]):.4f}',
                    "seeker_ci95": f'[{float(seeker["ci95_low"]):.4f}, {float(seeker["ci95_high"]):.4f}]',
                    "attempted_kb": f'{float(traffic["mean"])/1000:.2f}',
                })
    _write(tables / "care_natural_scale.csv", scale_rows)
    lines = ["# Non-tiled natural scale validation", "", "| Agents | Planner | Method | Seeker CSR [95% CI] | Attempted KB |", "| ---: | --- | --- | ---: | ---: |"]
    for row in scale_rows:
        lines.append(f'| {row["agents"]} | {row["planner"]} | {row["method"]} | {row["seeker_csr"]} {row["seeker_ci95"]} | {row["attempted_kb"]} |')
    (tables / "care_natural_scale.md").write_text("\n".join(lines) + "\n")

    scale_effects = []
    for agents in (4, 8, 16, 32):
        for planner in ("astar", "dstar_lite"):
            seeker = sp[(agents, planner, "one_shot_delta", "seeker_success_rate")]
            traffic = sp[(agents, planner, "one_shot_delta", "attempted_bytes")]
            scale_effects.append({
                "agents": str(agents),
                "planner": "A*" if planner == "astar" else "D* Lite",
                "comparison": "CARE - One-shot",
                "delta_seeker_csr": f'{float(seeker["mean_difference"]):+.4f}',
                "seeker_ci95": f'[{float(seeker["ci95_low"]):+.4f}, {float(seeker["ci95_high"]):+.4f}]',
                "paired_dz": f'{float(seeker["paired_effect_dz"]):+.3f}',
                "delta_kb": f'{float(traffic["mean_difference"])/1000:+.2f}',
                "kb_ci95": f'[{float(traffic["ci95_low"])/1000:+.2f}, {float(traffic["ci95_high"])/1000:+.2f}]',
            })
    _write(tables / "care_natural_scale_paired.csv", scale_effects)
    lines = [
        "# Paired CARE effects on non-tiled natural scale maps", "",
        "Every difference matches CARE and One-shot on the same accepted map and link trace.", "",
        "| Agents | Planner | Comparison | Δ seeker CSR [95% CI] | d_z | ΔKB [95% CI] |",
        "| ---: | --- | --- | ---: | ---: | ---: |",
    ]
    for row in scale_effects:
        lines.append(
            f'| {row["agents"]} | {row["planner"]} | {row["comparison"]} | '
            f'{row["delta_seeker_csr"]} {row["seeker_ci95"]} | '
            f'{row["paired_dz"]} | {row["delta_kb"]} {row["kb_ci95"]} |'
        )
    (tables / "care_natural_scale_paired.md").write_text("\n".join(lines) + "\n")

    figure, axes = plt.subplots(1, 2, figsize=(10, 4.1))
    for planner, style in (("astar", "-o"), ("dstar_lite", "--s")):
        effects_by_scale = [sp[(agents, planner, "one_shot_delta", "seeker_success_rate")] for agents in (4, 8, 16, 32)]
        means = np.asarray([float(row["mean_difference"]) for row in effects_by_scale])
        low = np.asarray([float(row["ci95_low"]) for row in effects_by_scale])
        high = np.asarray([float(row["ci95_high"]) for row in effects_by_scale])
        label = "A*" if planner == "astar" else "D* Lite"
        axes[0].plot((4,8,16,32), means, style, label=label)
        axes[0].fill_between((4,8,16,32), low, high, alpha=.14)
        bytes_by_scale = [sp[(agents, planner, "one_shot_delta", "attempted_bytes")] for agents in (4, 8, 16, 32)]
        bmeans = np.asarray([float(row["mean_difference"])/1000 for row in bytes_by_scale])
        blow = np.asarray([float(row["ci95_low"])/1000 for row in bytes_by_scale])
        bhigh = np.asarray([float(row["ci95_high"])/1000 for row in bytes_by_scale])
        axes[1].plot((4,8,16,32), bmeans, style, label=label)
        axes[1].fill_between((4,8,16,32), blow, bhigh, alpha=.14)
    axes[0].axhline(0, color="black", lw=.8); axes[1].axhline(0, color="black", lw=.8)
    axes[0].set_ylabel("CARE − One-shot seeker CSR")
    axes[1].set_ylabel("CARE − One-shot traffic (KB)")
    for axis in axes:
        axis.set_xlabel("Agents (non-tiled random map)"); axis.set_xticks((4,8,16,32)); axis.grid(alpha=.2)
    axes[0].legend(frameon=False)
    figure.suptitle("Natural decision-conflict scale study (paired 95% map CIs)")
    figure.tight_layout()
    figure.savefig(figures / "care_natural_scale.png", dpi=220, bbox_inches="tight")
    figure.savefig(
        figures / "care_natural_scale.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(figure)

    (tables / "care_natural_manifest.json").write_text((analysis / "analysis_manifest.json").read_text())
    for source in sorted((analysis / "accepted_manifests").glob("*.json")):
        shutil.copyfile(source, manifests / source.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, required=True)
    parser.add_argument("--figure-directory", type=Path, required=True)
    args = parser.parse_args(); artifacts(args.analysis_directory, args.table_directory, args.figure_directory)


if __name__ == "__main__":
    main()
