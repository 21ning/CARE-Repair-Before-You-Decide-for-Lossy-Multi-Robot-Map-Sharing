#!/usr/bin/env python3
"""Render PSR-UT paper assets from final 100-map result matrices."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


DISPLAY = {
    "one_shot_delta": "One-shot",
    "retry_all_arq": "Retry-All ARQ",
    "path_weighted_arq": "Path-Weighted ARQ",
    "periodic_full_sync": "Periodic Full (K=4)",
    "mismatch_triggered_full_repair": "Mismatch Full Repair",
    "utility_triggered_repair": "PSR-UT",
}
POLICIES = tuple(DISPLAY)
COLORS = {
    "one_shot_delta": "#6c757d", "retry_all_arq": "#009E73",
    "path_weighted_arq": "#56B4E9", "mismatch_triggered_full_repair": "#D55E00",
    "periodic_full_sync": "#CC79A7",
    "utility_triggered_repair": "#0072B2",
}


def number(row: dict[str, str], field: str) -> float:
    return float(row[field])


def select_primary(
    rows: list[dict[str, str]], periodic_rows: list[dict[str, str]] | None = None,
) -> list[dict[str, str]]:
    selected = [
        row for row in rows
        if row["study"] == "loss_sweep" and row["loss_probability"] == "0.3"
        and row["delay_steps"] == "0" and row["policy"] in POLICIES
    ]
    by_policy = {row["policy"]: row for row in selected}
    if periodic_rows is not None:
        periodic = [row for row in periodic_rows if row["policy"] == "periodic_full_sync"]
        if len(periodic) != 1:
            raise ValueError("periodic baseline summary must contain exactly one K=4 row")
        by_policy["periodic_full_sync"] = periodic[0]
    required_policies = POLICIES if periodic_rows is not None else tuple(
        policy for policy in POLICIES if policy != "periodic_full_sync"
    )
    if set(by_policy) != set(required_policies) or len(selected) != len(required_policies) - (periodic_rows is not None):
        raise ValueError("primary comparison is missing one or more required policies")
    return [by_policy[policy] for policy in required_policies]


def render_primary_table(rows: list[dict[str, str]], directory: Path) -> None:
    lines = [
        "# PSR-UT primary comparison (100 independent matched maps)", "",
        "95% CIs use a deterministic 20,000-draw bootstrap over independent maps.", "",
        "| Method | CSR (95% CI) | Attempted bytes / episode (95% CI) |",
        "| --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {DISPLAY[row['policy']]} | {number(row, 'mean_completion_success_rate'):.4f} "
            f"[{number(row, 'ci95_low_completion_success_rate'):.4f}, {number(row, 'ci95_high_completion_success_rate'):.4f}] | "
            f"{number(row, 'mean_attempted_bytes'):,.0f} "
            f"[{number(row, 'ci95_low_attempted_bytes'):,.0f}, {number(row, 'ci95_high_attempted_bytes'):,.0f}] |"
        )
    (directory / "psr_ut_primary_comparison.md").write_text("\n".join(lines) + "\n")
    with (directory / "psr_ut_primary_comparison.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def render_pareto(rows: list[dict[str, str]], directory: Path) -> None:
    plt.figure(figsize=(6.2, 3.7))
    offsets = {
        "one_shot_delta": (4, -10), "utility_triggered_repair": (4, 6),
        "retry_all_arq": (4, -12), "path_weighted_arq": (4, 6),
        "periodic_full_sync": (4, 8),
        "mismatch_triggered_full_repair": (-86, 5),
    }
    for row in rows:
        policy = row["policy"]
        csr = number(row, "mean_completion_success_rate")
        low, high = number(row, "ci95_low_completion_success_rate"), number(row, "ci95_high_completion_success_rate")
        traffic = number(row, "mean_attempted_bytes") / 1000
        plt.errorbar(traffic, csr, yerr=[[csr - low], [high - csr]], fmt="o", ms=6, capsize=3, color=COLORS[policy])
        plt.annotate(DISPLAY[policy], (traffic, csr), xytext=offsets[policy], textcoords="offset points", fontsize=8)
    plt.xlabel("Attempted communication (KB / episode)")
    plt.ylabel("Completion success rate")
    plt.xlim(35, 625); plt.ylim(.74, 1.02); plt.grid(alpha=.25); plt.tight_layout()
    plt.savefig(directory / "psr_ut_primary_pareto.png", dpi=240); plt.close()


def render_loss_curve(rows: list[dict[str, str]], directory: Path) -> None:
    plt.figure(figsize=(6.2, 3.7))
    for policy in ("one_shot_delta", "retry_all_arq", "utility_triggered_repair"):
        points = sorted(
            (row for row in rows if row["study"] == "loss_sweep" and row["delay_steps"] == "0" and row["policy"] == policy),
            key=lambda row: number(row, "loss_probability"),
        )
        x = [number(row, "loss_probability") for row in points]
        y = [number(row, "mean_completion_success_rate") for row in points]
        low = [number(row, "ci95_low_completion_success_rate") for row in points]
        high = [number(row, "ci95_high_completion_success_rate") for row in points]
        plt.errorbar(x, y, yerr=[[a - b for a, b in zip(y, low)], [b - a for a, b in zip(y, high)]],
                     marker="o", capsize=3, label=DISPLAY[policy], color=COLORS[policy])
    plt.xlabel("Independent packet-loss probability")
    plt.ylabel("Completion success rate")
    plt.ylim(.65, 1.03); plt.xlim(-.02, .52); plt.grid(alpha=.25); plt.legend(fontsize=8); plt.tight_layout()
    plt.savefig(directory / "psr_ut_csr_vs_loss.png", dpi=240); plt.close()


def render_gate_schematic(directory: Path) -> None:
    def box(ax, xy: tuple[float, float], text: str, color: str, width: float, height: float = .14) -> None:
        ax.add_patch(FancyBboxPatch(xy, width, height, boxstyle="round,pad=0.018", fc=color, ec="#333333", lw=.8))
        ax.text(xy[0] + width / 2, xy[1] + height / 2, text, ha="center", va="center", fontsize=8, wrap=True)
    fig, ax = plt.subplots(figsize=(6.4, 3.25)); ax.set_axis_off(); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    box(ax, (.03, .43), "Receiver-local\nreplica", "#E6F0F8", .22)
    box(ax, (.32, .43), "Where: imminent\npath corridor", "#DDEEDB", .23)
    box(ax, (.62, .41), "When: do optimistic and\npessimistic actions differ?", "#FCE5CD", .26, .18)
    box(ax, (.72, .75), "Different\nquery + stamped repair", "#DCEAF7", .23)
    box(ax, (.72, .08), "Same\nsuppress query", "#ECECEC", .23)
    for end, start, color in [((.32, .50), (.25, .50), "#333333"), ((.62, .50), (.56, .50), "#333333"), ((.80, .75), (.75, .60), "#0072B2"), ((.80, .22), (.75, .40), "#6c757d")]:
        ax.annotate("", end, start, arrowprops={"arrowstyle": "->", "lw": 1.1, "color": color})
    fig.tight_layout(pad=.2); fig.savefig(directory / "psr_ut_two_gate_schematic.png", dpi=240); plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-summary", type=Path, default=Path("results/psr_ut_formal_100map_matrix/analysis/summary_mean_std_ci.csv"))
    parser.add_argument("--periodic-summary", type=Path,
                        help="Optional 100-map Periodic Full (K=4) summary.csv.")
    parser.add_argument("--table-directory", type=Path, default=Path("paper/tables"))
    parser.add_argument("--figure-directory", type=Path, default=Path("paper/figures"))
    args = parser.parse_args(); args.table_directory.mkdir(parents=True, exist_ok=True); args.figure_directory.mkdir(parents=True, exist_ok=True)
    summary = list(csv.DictReader(args.formal_summary.open()))
    periodic_summary = list(csv.DictReader(args.periodic_summary.open())) if args.periodic_summary else None
    primary = select_primary(summary, periodic_summary)
    render_primary_table(primary, args.table_directory)
    render_pareto(primary, args.figure_directory)
    render_loss_curve(summary, args.figure_directory)
    render_gate_schematic(args.figure_directory)
    print({"primary_rows": len(primary), "tables": 1, "figures": 3})


if __name__ == "__main__":
    main()
