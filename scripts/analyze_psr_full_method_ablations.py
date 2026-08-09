#!/usr/bin/env python3
"""Paired full-method ablations for PSR-UT on 100 independent maps."""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_psr_100map_matrix import bootstrap


@dataclass(frozen=True)
class Ablation:
    name: str
    full_file: Path
    full_policy: str
    ablated_file: Path
    ablated_policy: str
    loss_probability: str | None = None


def build_ablations(formal_directory: Path, action_directory: Path) -> tuple[Ablation, ...]:
    """Build the three paired ablations from explicit result roots."""
    return (
        Ablation(
            "utility_trigger",
            formal_directory / "loss_sweep" / "results.csv",
            "utility_triggered_repair",
            action_directory / "results.csv",
            "action_triggered_repair",
            "0.3",
        ),
        Ablation(
            "repair_cadence",
            formal_directory / "timing_k1" / "results.csv",
            "utility_triggered_repair",
            formal_directory / "timing_k4" / "results.csv",
            "utility_triggered_repair",
        ),
        Ablation(
            "repair_scope",
            formal_directory / "repair_scope" / "results.csv",
            "utility_triggered_repair",
            formal_directory / "repair_scope" / "results.csv",
            "full_replica_repair",
        ),
    )
METRICS = ("completion_success_rate", "attempted_bytes")


def select(path: Path, policy: str, loss_probability: str | None) -> dict[tuple[str, str], dict[str, str]]:
    rows = [
        row for row in csv.DictReader(path.open())
        if row["policy"] == policy and (loss_probability is None or row["loss_probability"] == loss_probability)
    ]
    selected = {(row["layout_seed"], row["network_seed"]): row for row in rows}
    if len(selected) != 100 or len({row["instance_fingerprint"] for row in selected.values()}) != 100:
        raise ValueError(f"{path}: {policy} does not contain 100 independent maps")
    if any(layout != network for layout, network in selected):
        raise ValueError(f"{path}: each map must have its own independent loss trace")
    return selected


def analyze(ablation: Ablation, *, seed: int) -> dict[str, float | int | str]:
    full = select(ablation.full_file, ablation.full_policy, ablation.loss_probability)
    ablated = select(ablation.ablated_file, ablation.ablated_policy, ablation.loss_probability)
    if set(full) != set(ablated):
        raise ValueError(f"{ablation.name}: full and ablated trials are not exactly paired")
    if any(full[key]["instance_fingerprint"] != ablated[key]["instance_fingerprint"] for key in full):
        raise ValueError(f"{ablation.name}: full and ablated trials have different maps")
    keys = sorted(full, key=lambda key: int(key[0]))
    row: dict[str, float | int | str] = {
        "ablation": ablation.name,
        "full_method": ablation.full_policy,
        "ablated_method": ablation.ablated_policy,
        "paired_maps": len(keys),
    }
    for metric_index, metric in enumerate(METRICS):
        full_values = np.asarray([float(full[key][metric]) for key in keys])
        ablated_values = np.asarray([float(ablated[key][metric]) for key in keys])
        delta = full_values - ablated_values
        low, high = bootstrap(delta, seed=seed + metric_index)
        row.update({
            f"full_mean_{metric}": float(full_values.mean()),
            f"full_std_{metric}": float(full_values.std(ddof=1)),
            f"ablated_mean_{metric}": float(ablated_values.mean()),
            f"ablated_std_{metric}": float(ablated_values.std(ddof=1)),
            f"mean_difference_{metric}": float(delta.mean()),
            f"std_difference_{metric}": float(delta.std(ddof=1)),
            f"ci95_low_difference_{metric}": low,
            f"ci95_high_difference_{metric}": high,
        })
    return row


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--formal-directory", type=Path, default=Path("results/psr_ut_formal_100map_matrix"))
    parser.add_argument("--action-directory", type=Path, default=Path("results/psr_ut_action_ablation_100map"))
    parser.add_argument("--output-directory", type=Path, default=Path("results/psr_ut_ablation_100map/analysis"))
    args = parser.parse_args(); args.output_directory.mkdir(parents=True, exist_ok=True)
    rows = [analyze(ablation, seed=10_000 + 100 * index) for index, ablation in enumerate(build_ablations(args.formal_directory, args.action_directory))]
    write_csv(args.output_directory / "full_method_paired_ablation.csv", rows)
    print({"ablations": len(rows), "paired_maps": 100})


if __name__ == "__main__":
    main()
