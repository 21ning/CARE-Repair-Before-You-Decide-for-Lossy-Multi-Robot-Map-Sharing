#!/usr/bin/env python3
"""Generate manuscript artifacts for CARE's matched commitment-gate ablation."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


PLANNERS = ("astar", "dstar_lite")
PLANNER_LABELS = {"astar": "A*", "dstar_lite": "D* Lite"}
DELAYS = (0, 1, 2, 4)
POLICIES = (
    "certificate_repair_route_gate",
    "certificate_repair_no_commitment_gate",
)
LABELS = {
    "certificate_repair_route_gate": "RouteWitness-Gated",
    "certificate_repair_no_commitment_gate": "RouteWitness-Ungated",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open()))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write an empty artifact: {path}")
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def interval(row: dict[str, str], digits: int, scale: float = 1.0) -> str:
    return (
        f'[{float(row["ci95_low"]) / scale:.{digits}f}, '
        f'{float(row["ci95_high"]) / scale:.{digits}f}]'
    )


def signed_interval(row: dict[str, str], digits: int, scale: float = 1.0) -> str:
    return (
        f'[{float(row["ci95_low"]) / scale:+.{digits}f}, '
        f'{float(row["ci95_high"]) / scale:+.{digits}f}]'
    )


def artifacts(analysis: Path, tables: Path, figures: Path) -> None:
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    summary = read_csv(analysis / "summary_mean_std_ci.csv")
    paired = read_csv(analysis / "paired_comparisons.csv")
    audit = json.loads((analysis / "gate_audit.json").read_text())
    lookup = {
        (
            row["planner"], int(row["delay_steps"]), row["policy"],
            row["metric"],
        ): row
        for row in summary
    }
    paired_lookup = {
        (row["planner"], int(row["delay_steps"]), row["metric"]): row
        for row in paired
    }

    absolute_rows: list[dict[str, str]] = []
    for planner in PLANNERS:
        for delay in DELAYS:
            for policy in POLICIES:
                metric = lambda name: lookup[(planner, delay, policy, name)]
                seeker = metric("seeker_success_rate")
                pair = metric("critical_pair_success_rate")
                overall = metric("completion_success_rate")
                episode_length = metric("episode_length")
                attempted = metric("attempted_bytes")
                delivered = metric("delivered_bytes")
                attempted_control = metric("attempted_control_bytes")
                delivered_control = metric("delivered_control_bytes")
                attempted_repair = metric("attempted_repair_bytes")
                delivered_repair = metric("delivered_repair_bytes")
                checks = metric("commitment_gate_checks")
                closed = metric("commitment_gate_closed")
                raw = metric("commitment_raw_query_cells")
                suppressed = metric("commitment_suppressed_query_cells")
                planning_cpu = metric("planning_cpu_ms")
                certificate_cpu = metric("certificate_cpu_ms")
                episode_cpu = metric("episode_cpu_ms")
                checks_mean = float(checks["mean"])
                absolute_rows.append({
                    "planner": PLANNER_LABELS[planner], "delay_steps": str(delay),
                    "method": LABELS[policy],
                    "seeker_success_mean": f'{float(seeker["mean"]):.4f}',
                    "seeker_success_std": f'{float(seeker["std"]):.4f}',
                    "seeker_success_ci95": interval(seeker, 4),
                    "pair_success_mean": f'{float(pair["mean"]):.4f}',
                    "pair_success_std": f'{float(pair["std"]):.4f}',
                    "pair_success_ci95": interval(pair, 4),
                    "overall_csr_mean": f'{float(overall["mean"]):.4f}',
                    "overall_csr_std": f'{float(overall["std"]):.4f}',
                    "overall_csr_ci95": interval(overall, 4),
                    "el_mean": f'{float(episode_length["mean"]):.2f}',
                    "el_std": f'{float(episode_length["std"]):.2f}',
                    "el_ci95": interval(episode_length, 2),
                    "attempted_kb_mean": f'{float(attempted["mean"]) / 1000:.2f}',
                    "attempted_kb_ci95": interval(attempted, 2, 1000),
                    "delivered_kb_mean": f'{float(delivered["mean"]) / 1000:.2f}',
                    "delivered_kb_ci95": interval(delivered, 2, 1000),
                    "attempted_control_kb_mean": (
                        f'{float(attempted_control["mean"]) / 1000:.2f}'
                    ),
                    "attempted_control_kb_ci95": interval(
                        attempted_control, 2, 1000,
                    ),
                    "delivered_control_kb_mean": (
                        f'{float(delivered_control["mean"]) / 1000:.2f}'
                    ),
                    "delivered_control_kb_ci95": interval(
                        delivered_control, 2, 1000,
                    ),
                    "attempted_repair_kb_mean": (
                        f'{float(attempted_repair["mean"]) / 1000:.2f}'
                    ),
                    "attempted_repair_kb_ci95": interval(
                        attempted_repair, 2, 1000,
                    ),
                    "delivered_repair_kb_mean": (
                        f'{float(delivered_repair["mean"]) / 1000:.2f}'
                    ),
                    "delivered_repair_kb_ci95": interval(
                        delivered_repair, 2, 1000,
                    ),
                    "gate_checks_mean": f'{checks_mean:.2f}',
                    "gate_checks_ci95": interval(checks, 2),
                    "gate_closed_mean": f'{float(closed["mean"]):.2f}',
                    "gate_closed_ci95": interval(closed, 2),
                    "gate_closed_fraction": (
                        f'{float(closed["mean"]) / checks_mean:.4f}'
                        if checks_mean else "0.0000"
                    ),
                    "commitment_raw_cells_mean": f'{float(raw["mean"]):.2f}',
                    "commitment_raw_cells_ci95": interval(raw, 2),
                    "commitment_suppressed_cells_mean": (
                        f'{float(suppressed["mean"]):.2f}'
                    ),
                    "commitment_suppressed_cells_ci95": interval(suppressed, 2),
                    "planning_cpu_ms_mean": f'{float(planning_cpu["mean"]):.1f}',
                    "planning_cpu_ms_ci95": interval(planning_cpu, 1),
                    "certificate_cpu_ms_mean": f'{float(certificate_cpu["mean"]):.1f}',
                    "certificate_cpu_ms_ci95": interval(certificate_cpu, 1),
                    "episode_cpu_ms_mean": f'{float(episode_cpu["mean"]):.1f}',
                    "episode_cpu_ms_ci95": interval(episode_cpu, 1),
                })
    write_csv(tables / "care_commitment_gate.csv", absolute_rows)

    lines = [
        "# CARE commitment-gate ablation", "",
        (
            "The two ablation-only variants use the identical scenario "
            "certificate and raw route witness; RouteWitness-Gated suppresses "
            "that auxiliary witness after its local proxy deadline. Neither "
            "variant is final CARE. All cells use 100 paired maps."
        ), "",
        "## Outcomes and communication", "",
        (
            "| Planner | Delay | Method | Seeker success [95% CI] | Pair success "
            "[95% CI] | Overall CSR [95% CI] | EL [95% CI] | Attempted/Delivered KB |"
        ),
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in absolute_rows:
        lines.append(
            f'| {row["planner"]} | {row["delay_steps"]} | {row["method"]} | '
            f'{row["seeker_success_mean"]} {row["seeker_success_ci95"]} | '
            f'{row["pair_success_mean"]} {row["pair_success_ci95"]} | '
            f'{row["overall_csr_mean"]} {row["overall_csr_ci95"]} | '
            f'{row["el_mean"]} {row["el_ci95"]} | '
            f'{row["attempted_kb_mean"]}/{row["delivered_kb_mean"]} |'
        )
    lines.extend([
        "", "## Gate, byte-class, and compute diagnostics", "",
        (
            "| Planner | Delay | Method | Closed/Checks | Raw/Suppressed cells | "
            "Attempted control/repair KB | Delivered control/repair KB | "
            "Planning/Certificate/Episode CPU ms |"
        ),
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in absolute_rows:
        lines.append(
            f'| {row["planner"]} | {row["delay_steps"]} | {row["method"]} | '
            f'{row["gate_closed_mean"]}/{row["gate_checks_mean"]} | '
            f'{row["commitment_raw_cells_mean"]}/'
            f'{row["commitment_suppressed_cells_mean"]} | '
            f'{row["attempted_control_kb_mean"]}/'
            f'{row["attempted_repair_kb_mean"]} | '
            f'{row["delivered_control_kb_mean"]}/'
            f'{row["delivered_repair_kb_mean"]} | '
            f'{row["planning_cpu_ms_mean"]}/{row["certificate_cpu_ms_mean"]}/'
            f'{row["episode_cpu_ms_mean"]} |'
        )
    (tables / "care_commitment_gate.md").write_text("\n".join(lines) + "\n")

    paired_rows: list[dict[str, str]] = []
    for planner in PLANNERS:
        for delay in DELAYS:
            metric = lambda name: paired_lookup[(planner, delay, name)]
            seeker = metric("seeker_success_rate")
            pair = metric("critical_pair_success_rate")
            overall = metric("completion_success_rate")
            episode_length = metric("episode_length")
            attempted = metric("attempted_bytes")
            delivered = metric("delivered_bytes")
            attempted_control = metric("attempted_control_bytes")
            delivered_control = metric("delivered_control_bytes")
            attempted_repair = metric("attempted_repair_bytes")
            delivered_repair = metric("delivered_repair_bytes")
            episode_cpu = metric("episode_cpu_ms")
            planning_cpu = metric("planning_cpu_ms")
            certificate_cpu = metric("certificate_cpu_ms")
            gate_checks = metric("commitment_gate_checks")
            gate_closed = metric("commitment_gate_closed")
            raw_cells = metric("commitment_raw_query_cells")
            suppressed_cells = metric("commitment_suppressed_query_cells")
            paired_rows.append({
                "planner": PLANNER_LABELS[planner], "delay_steps": str(delay),
                "comparison": "RouteWitness-Gated - RouteWitness-Ungated", "paired_maps": "100",
                "delta_seeker_success": f'{float(seeker["mean_difference"]):+.4f}',
                "seeker_ci95": signed_interval(seeker, 4),
                "seeker_dz": f'{float(seeker["paired_effect_dz"]):+.3f}',
                "delta_pair_success": f'{float(pair["mean_difference"]):+.4f}',
                "pair_ci95": signed_interval(pair, 4),
                "pair_dz": f'{float(pair["paired_effect_dz"]):+.3f}',
                "delta_overall_csr": f'{float(overall["mean_difference"]):+.4f}',
                "overall_csr_ci95": signed_interval(overall, 4),
                "delta_el": f'{float(episode_length["mean_difference"]):+.2f}',
                "el_ci95": signed_interval(episode_length, 2),
                "delta_attempted_kb": f'{float(attempted["mean_difference"]) / 1000:+.2f}',
                "attempted_kb_ci95": signed_interval(attempted, 2, 1000),
                "delta_delivered_kb": f'{float(delivered["mean_difference"]) / 1000:+.2f}',
                "delivered_kb_ci95": signed_interval(delivered, 2, 1000),
                "delta_attempted_control_kb": (
                    f'{float(attempted_control["mean_difference"]) / 1000:+.2f}'
                ),
                "attempted_control_kb_ci95": signed_interval(
                    attempted_control, 2, 1000,
                ),
                "delta_delivered_control_kb": (
                    f'{float(delivered_control["mean_difference"]) / 1000:+.2f}'
                ),
                "delivered_control_kb_ci95": signed_interval(
                    delivered_control, 2, 1000,
                ),
                "delta_attempted_repair_kb": (
                    f'{float(attempted_repair["mean_difference"]) / 1000:+.2f}'
                ),
                "attempted_repair_kb_ci95": signed_interval(
                    attempted_repair, 2, 1000,
                ),
                "delta_delivered_repair_kb": (
                    f'{float(delivered_repair["mean_difference"]) / 1000:+.2f}'
                ),
                "delivered_repair_kb_ci95": signed_interval(
                    delivered_repair, 2, 1000,
                ),
                "delta_episode_cpu_ms": f'{float(episode_cpu["mean_difference"]):+.1f}',
                "episode_cpu_ms_ci95": signed_interval(episode_cpu, 1),
                "delta_planning_cpu_ms": (
                    f'{float(planning_cpu["mean_difference"]):+.1f}'
                ),
                "planning_cpu_ms_ci95": signed_interval(planning_cpu, 1),
                "delta_certificate_cpu_ms": (
                    f'{float(certificate_cpu["mean_difference"]):+.1f}'
                ),
                "certificate_cpu_ms_ci95": signed_interval(certificate_cpu, 1),
                "delta_gate_checks": f'{float(gate_checks["mean_difference"]):+.2f}',
                "gate_checks_ci95": signed_interval(gate_checks, 2),
                "delta_gate_closed": f'{float(gate_closed["mean_difference"]):+.2f}',
                "gate_closed_ci95": signed_interval(gate_closed, 2),
                "delta_raw_cells": f'{float(raw_cells["mean_difference"]):+.2f}',
                "raw_cells_ci95": signed_interval(raw_cells, 2),
                "delta_suppressed_cells": (
                    f'{float(suppressed_cells["mean_difference"]):+.2f}'
                ),
                "suppressed_cells_ci95": signed_interval(suppressed_cells, 2),
            })
    write_csv(tables / "care_commitment_gate_paired.csv", paired_rows)
    paired_lines = [
        "# Paired commitment-gate effects", "",
        (
            "Differences are RouteWitness-Gated minus RouteWitness-Ungated. Positive success "
            "differences favor the gate; negative byte differences mean that "
            "the gate avoids traffic."
        ), "",
        (
            "| Planner | Delay | Δ seeker success [95% CI] | d_z | Δ pair "
            "success [95% CI] | Δ overall CSR [95% CI] | ΔEL [95% CI] | "
            "Δ attempted/delivered KB [95% CI] |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in paired_rows:
        paired_lines.append(
            f'| {row["planner"]} | {row["delay_steps"]} | '
            f'{row["delta_seeker_success"]} {row["seeker_ci95"]} | '
            f'{row["seeker_dz"]} | {row["delta_pair_success"]} '
            f'{row["pair_ci95"]} | {row["delta_overall_csr"]} '
            f'{row["overall_csr_ci95"]} | {row["delta_el"]} '
            f'{row["el_ci95"]} | {row["delta_attempted_kb"]} '
            f'{row["attempted_kb_ci95"]} / {row["delta_delivered_kb"]} '
            f'{row["delivered_kb_ci95"]} |'
        )
    (tables / "care_commitment_gate_paired.md").write_text(
        "\n".join(paired_lines) + "\n"
    )

    diagnostic_lines = [
        "# Paired commitment-gate mechanism diagnostics", "",
        "All differences are RouteWitness-Gated minus RouteWitness-Ungated on 100 matched maps.",
        "",
        (
            "| Planner | Delay | Δ gate checks [95% CI] | Δ closed [95% CI] | "
            "Δ raw cells [95% CI] | Δ suppressed cells [95% CI] | "
            "Δ attempted control/repair KB [95% CI] | "
            "Δ planning/certificate/episode CPU ms [95% CI] |"
        ),
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in paired_rows:
        diagnostic_lines.append(
            f'| {row["planner"]} | {row["delay_steps"]} | '
            f'{row["delta_gate_checks"]} {row["gate_checks_ci95"]} | '
            f'{row["delta_gate_closed"]} {row["gate_closed_ci95"]} | '
            f'{row["delta_raw_cells"]} {row["raw_cells_ci95"]} | '
            f'{row["delta_suppressed_cells"]} '
            f'{row["suppressed_cells_ci95"]} | '
            f'{row["delta_attempted_control_kb"]} '
            f'{row["attempted_control_kb_ci95"]} / '
            f'{row["delta_attempted_repair_kb"]} '
            f'{row["attempted_repair_kb_ci95"]} | '
            f'{row["delta_planning_cpu_ms"]} '
            f'{row["planning_cpu_ms_ci95"]} / '
            f'{row["delta_certificate_cpu_ms"]} '
            f'{row["certificate_cpu_ms_ci95"]} / '
            f'{row["delta_episode_cpu_ms"]} '
            f'{row["episode_cpu_ms_ci95"]} |'
        )
    (tables / "care_commitment_gate_diagnostics.md").write_text(
        "\n".join(diagnostic_lines) + "\n"
    )

    figure, axes = plt.subplots(2, 2, figsize=(8.4, 6.1), sharex="col")
    for column, planner in enumerate(PLANNERS):
        for metric_name, label, color, style in (
            ("seeker_success_rate", "Seeker success", "#0072B2", "-"),
            ("critical_pair_success_rate", "Pair success", "#D55E00", "--"),
        ):
            points = [paired_lookup[(planner, delay, metric_name)] for delay in DELAYS]
            means = [float(point["mean_difference"]) for point in points]
            low = [float(point["ci95_low"]) for point in points]
            high = [float(point["ci95_high"]) for point in points]
            axes[0, column].plot(
                DELAYS, means, style, color=color, marker="o", linewidth=2,
                label=label,
            )
            axes[0, column].fill_between(
                DELAYS, low, high, color=color, alpha=.14,
            )
        traffic_points = [
            paired_lookup[(planner, delay, "attempted_bytes")] for delay in DELAYS
        ]
        traffic = [float(point["mean_difference"]) / 1000 for point in traffic_points]
        traffic_low = [float(point["ci95_low"]) / 1000 for point in traffic_points]
        traffic_high = [float(point["ci95_high"]) / 1000 for point in traffic_points]
        axes[1, column].plot(
            DELAYS, traffic, color="#6F4C9B", marker="o", linewidth=2,
            label="Attempted traffic",
        )
        axes[1, column].fill_between(
            DELAYS, traffic_low, traffic_high, color="#6F4C9B", alpha=.14,
        )
        axes[0, column].set_title(PLANNER_LABELS[planner])
        axes[1, column].set_xlabel("One-way link delay (steps)")
        axes[1, column].set_xticks(DELAYS)
        for axis in axes[:, column]:
            axis.axhline(0, color="#333333", linewidth=.9, alpha=.75)
            axis.grid(alpha=.25)
    axes[0, 0].set_ylabel("Δ success rate")
    axes[1, 0].set_ylabel("Δ attempted traffic (KB)")
    axes[0, 1].legend(frameon=False, fontsize=8)
    axes[1, 1].legend(frameon=False, fontsize=8)
    figure.suptitle(
        "RouteWitness-Gated − Ungated (paired map-cluster bootstrap 95% CI)",
        fontsize=11,
    )
    figure.tight_layout(rect=(0, 0, 1, .95))
    figure.savefig(figures / "care_commitment_gate.png", dpi=220)
    figure.savefig(
        figures / "care_commitment_gate.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(figure)

    (tables / "care_commitment_gate_audit.json").write_text(
        json.dumps(audit, indent=2) + "\n"
    )
    manifest = json.loads((analysis / "analysis_manifest.json").read_text())
    (tables / "care_commitment_gate_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-directory", type=Path, required=True)
    parser.add_argument("--table-directory", type=Path, required=True)
    parser.add_argument("--figure-directory", type=Path, required=True)
    args = parser.parse_args()
    artifacts(args.analysis_directory, args.table_directory, args.figure_directory)


if __name__ == "__main__":
    main()
