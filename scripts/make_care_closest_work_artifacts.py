#!/usr/bin/env python3
"""Generate paper artifacts for CARE's codec-matched closest-work study."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


LABELS = {
    "one_shot_delta": "One-shot",
    "retry_all_arq": "Retry-All",
    "path_aware_top_k_repair": "Path-Aware Top-K",
    "single_cell_sensitivity_repair": "Single-Cell",
    "deadline_aware_repair": "CARE-Lite",
    "ocbc_forward_simulation": "OCBC-FS (adapt.)",
    "path_guided_compression": "PGSC (adapt.)",
    "rate_distortion_compression": "Bernoulli R-D (adapt.)",
    "voi_repair": "VoI/byte (adapt.)",
    "certificate_repair": "CARE",
}
ORDER = tuple(LABELS)
CLOSEST = (
    "ocbc_forward_simulation", "path_guided_compression",
    "rate_distortion_compression", "voi_repair",
    "path_aware_top_k_repair", "single_cell_sensitivity_repair",
    "deadline_aware_repair",
)


def _read(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open()))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def artifacts(analysis: Path, tables: Path, figures: Path) -> None:
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    summary = _read(analysis / "summary_mean_std_ci.csv")
    paired = _read(analysis / "paired_comparisons.csv")
    lookup = {
        (int(row["observation_radius"]), row["planner"], row["policy"], row["metric"]): row
        for row in summary
    }
    paired_lookup = {
        (int(row["observation_radius"]), row["planner"], row["left"], row["right"], row["metric"]): row
        for row in paired
    }

    primary: list[dict[str, str]] = []
    for planner in ("astar", "dstar_lite"):
        for policy in ORDER:
            seeker = lookup[(2, planner, policy, "seeker_success_rate")]
            overall = lookup[(2, planner, policy, "completion_success_rate")]
            el = lookup[(2, planner, policy, "episode_length")]
            traffic = lookup[(2, planner, policy, "attempted_bytes")]
            cpu = lookup[(2, planner, policy, "episode_cpu_ms")]
            primary.append({
                "planner": "A*" if planner == "astar" else "D* Lite",
                "method": LABELS[policy],
                "seeker_csr_mean": f'{float(seeker["mean"]):.4f}',
                "seeker_csr_std": f'{float(seeker["std"]):.4f}',
                "seeker_csr_ci95": f'[{float(seeker["ci95_low"]):.4f}, {float(seeker["ci95_high"]):.4f}]',
                "overall_csr": f'{float(overall["mean"]):.4f}',
                "el_mean_std": f'{float(el["mean"]):.2f} ± {float(el["std"]):.2f}',
                "attempted_kb": f'{float(traffic["mean"])/1000:.2f}',
                "episode_cpu_ms": f'{float(cpu["mean"]):.1f}',
            })
    _write(tables / "care_closest_work_primary.csv", primary)
    lines = [
        "# Codec-matched closest-work comparison (5x5, 30% loss)", "",
        "The four literature-derived controls are declared adaptations because their original representations differ from CARE's binary exact-cell contract. All rows use 100 paired maps.", "",
        "| Planner | Method | Seeker CSR mean ± SD [95% CI] | Overall CSR | EL mean ± SD | Attempted KB | CPU ms |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in primary:
        lines.append(
            f'| {row["planner"]} | {row["method"]} | {row["seeker_csr_mean"]} ± '
            f'{row["seeker_csr_std"]} {row["seeker_csr_ci95"]} | {row["overall_csr"]} | '
            f'{row["el_mean_std"]} | {row["attempted_kb"]} | {row["episode_cpu_ms"]} |'
        )
    (tables / "care_closest_work_primary.md").write_text("\n".join(lines) + "\n")

    effects: list[dict[str, str]] = []
    for radius in (1, 2, 3):
        for planner in ("astar", "dstar_lite"):
            for comparator in CLOSEST:
                seeker = paired_lookup[(radius, planner, "certificate_repair", comparator, "seeker_success_rate")]
                traffic = paired_lookup[(radius, planner, "certificate_repair", comparator, "attempted_bytes")]
                el = paired_lookup[(radius, planner, "certificate_repair", comparator, "episode_length")]
                effects.append({
                    "fov": f"{2*radius+1}x{2*radius+1}",
                    "planner": "A*" if planner == "astar" else "D* Lite",
                    "comparison": f'CARE - {LABELS[comparator]}',
                    "delta_seeker_csr": f'{float(seeker["mean_difference"]):+.4f}',
                    "seeker_ci95": f'[{float(seeker["ci95_low"]):+.4f}, {float(seeker["ci95_high"]):+.4f}]',
                    "paired_dz": f'{float(seeker["paired_effect_dz"]):+.3f}',
                    "delta_el": f'{float(el["mean_difference"]):+.2f}',
                    "el_ci95": f'[{float(el["ci95_low"]):+.2f}, {float(el["ci95_high"]):+.2f}]',
                    "delta_kb": f'{float(traffic["mean_difference"])/1000:+.2f}',
                    "kb_ci95": f'[{float(traffic["ci95_low"])/1000:+.2f}, {float(traffic["ci95_high"])/1000:+.2f}]',
                })
    _write(tables / "care_closest_work_paired.csv", effects)
    lines = [
        "# CARE paired against closest-work controls", "",
        "Positive Δ seeker CSR favors CARE; negative ΔKB means CARE sends less. CIs resample whole maps.", "",
        "| FOV | Planner | Comparison | Δ seeker CSR [95% CI] | d_z | ΔEL [95% CI] | ΔKB [95% CI] |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in effects:
        lines.append(
            f'| {row["fov"]} | {row["planner"]} | {row["comparison"]} | '
            f'{row["delta_seeker_csr"]} {row["seeker_ci95"]} | {row["paired_dz"]} | '
            f'{row["delta_el"]} {row["el_ci95"]} | {row["delta_kb"]} {row["kb_ci95"]} |'
        )
    (tables / "care_closest_work_paired.md").write_text("\n".join(lines) + "\n")

    # Primary-point overview: marginal CIs establish absolute performance;
    # the companion table supplies the paired inferential comparisons.
    figure, axes = plt.subplots(1, 2, figsize=(12.2, 4.8))
    x = np.arange(len(ORDER))
    width = .38
    for offset, planner in ((-.5, "astar"), (.5, "dstar_lite")):
        seeker_rows = [lookup[(2, planner, policy, "seeker_success_rate")] for policy in ORDER]
        byte_rows = [lookup[(2, planner, policy, "attempted_bytes")] for policy in ORDER]
        means = np.asarray([float(row["mean"]) for row in seeker_rows])
        errors = np.asarray([[means[i]-float(row["ci95_low"]) for i, row in enumerate(seeker_rows)],
                             [float(row["ci95_high"])-means[i] for i, row in enumerate(seeker_rows)]])
        axes[0].bar(x + offset*width, means, width, label="A*" if planner == "astar" else "D* Lite", yerr=errors, capsize=2)
        kb = np.asarray([float(row["mean"])/1000 for row in byte_rows])
        kb_errors = np.asarray([[kb[i]-float(row["ci95_low"])/1000 for i, row in enumerate(byte_rows)],
                                [float(row["ci95_high"])/1000-kb[i] for i, row in enumerate(byte_rows)]])
        axes[1].bar(x + offset*width, kb, width, yerr=kb_errors, capsize=2)
    axes[0].set_ylabel("Seeker completion rate")
    axes[1].set_ylabel("Attempted traffic (KB/episode)")
    for axis in axes:
        axis.set_xticks(x, [LABELS[p] for p in ORDER], rotation=45, ha="right")
        axis.grid(axis="y", alpha=.25)
    axes[0].legend(frameon=False)
    figure.suptitle("Closest-work controls under one explicit-map communication contract (95% map CIs)")
    figure.tight_layout()
    figure.savefig(figures / "care_closest_work.png", dpi=220, bbox_inches="tight")
    figure.savefig(
        figures / "care_closest_work.pdf",
        bbox_inches="tight",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(figure)

    manifest = json.loads((analysis / "analysis_manifest.json").read_text())
    (tables / "care_closest_work_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, required=True)
    parser.add_argument("--figure-directory", type=Path, required=True)
    args = parser.parse_args()
    artifacts(args.analysis_directory, args.table_directory, args.figure_directory)


if __name__ == "__main__":
    main()
