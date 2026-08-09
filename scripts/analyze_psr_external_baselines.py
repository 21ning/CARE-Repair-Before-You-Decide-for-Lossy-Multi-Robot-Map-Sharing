#!/usr/bin/env python3
"""Validate and summarize the matched PSR-UT primary baseline study."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

POLICIES = (
    "one_shot_delta", "retry_all_arq", "path_weighted_arq",
    "periodic_full_sync", "mismatch_triggered_full_repair", "utility_triggered_repair",
)
NON_PERIODIC_POLICIES = tuple(policy for policy in POLICIES if policy != "periodic_full_sync")
METRICS = (
    "completion_success_rate", "episode_length", "attempted_bytes",
    "attempted_data_bytes", "attempted_control_bytes", "attempted_repair_bytes",
    "delivered_bytes", "delivered_data_bytes", "delivered_control_bytes",
    "delivered_repair_bytes", "attempted_retransmission_messages",
    "attempted_retransmission_bytes",
)


def values(rows: dict[tuple[str, str], dict[str, str]], field: str) -> np.ndarray:
    """Return one value per independent matched map."""
    if len(rows) != 100:
        raise ValueError("external-baseline study requires 100 independent maps")
    ordered = sorted(rows, key=lambda key: int(key[0]))
    if any(layout != network for layout, network in ordered):
        raise ValueError("each map must use its own independent matched network trace")
    return np.asarray([float(rows[key][field]) for key in ordered])


def bootstrap(values: np.ndarray, *, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(20_000, len(values)), replace=True).mean(axis=1)
    return tuple(float(item) for item in np.quantile(means, (.025, .975)))


def analyze(
    rows: list[dict[str, str]], *, policies: tuple[str, ...] = POLICIES,
) -> tuple[list[dict[str, float | int | str]], list[dict[str, float | int | str]]]:
    """Summarize a complete matched primary or extension policy matrix."""
    rows = [
        row for row in rows
        if row["loss_probability"] == "0.3" and row["delay_steps"] == "0"
    ]
    expected_rows = 100 * len(policies)
    if len(rows) != expected_rows:
        raise ValueError(f"primary baseline study requires {expected_rows} rows, found {len(rows)}")
    by_policy: dict[str, dict[tuple[str, str], dict[str, str]]] = {policy: {} for policy in policies}
    for row in rows:
        if row["policy"] not in policies:
            raise ValueError("primary baseline study has an unexpected policy")
        key = (row["layout_seed"], row["network_seed"])
        by_policy[row["policy"]][key] = row
    anchor = by_policy["utility_triggered_repair"]
    if len(anchor) != 100 or any(set(group) != set(anchor) for group in by_policy.values()):
        raise ValueError("primary baseline study is not a complete 100-map matched matrix")
    if any(any(group[key]["instance_fingerprint"] != anchor[key]["instance_fingerprint"] for key in anchor) for group in by_policy.values()):
        raise ValueError("primary baseline policies are not instance-paired")

    summaries = []
    comparisons = []
    for policy in policies:
        selected = by_policy[policy]
        summary: dict[str, float | int | str] = {"policy": policy, "trials": len(selected), "independent_maps": 100}
        for metric_index, metric in enumerate(METRICS):
            selected_values = values(selected, metric)
            low, high = bootstrap(selected_values, seed=metric_index)
            summary.update({f"mean_{metric}": float(selected_values.mean()), f"std_{metric}": float(selected_values.std(ddof=1)), f"ci95_low_{metric}": low, f"ci95_high_{metric}": high})
        summaries.append(summary)
    for policy in policies:
        if policy == "utility_triggered_repair":
            continue
        for metric_index, metric in enumerate(METRICS):
            difference = values({key: {metric: str(float(anchor[key][metric]) - float(by_policy[policy][key][metric]))} for key in anchor}, metric)
            low, high = bootstrap(difference, seed=10_000 + metric_index)
            comparisons.append({
                "metric": metric, "left": "utility_triggered_repair", "right": policy,
                "paired_trials": difference.size, "mean_difference": float(difference.mean()), "std_difference": float(difference.std(ddof=1)),
                "ci95_low": low, "ci95_high": high,
            })
    return summaries, comparisons


def write_csv(path: Path, rows: list[dict[str, float | int | str]]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, action="append", required=True,
                        help="Directory containing a matching results.csv; supply one or more directories.")
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    output = args.output_directory or args.input_directory[0] / "analysis"
    output.mkdir(parents=True, exist_ok=True)
    rows = [
        row for directory in args.input_directory
        for row in csv.DictReader((directory / "results.csv").open())
    ]
    summaries, comparisons = analyze(rows)
    write_csv(output / "summary.csv", summaries)
    write_csv(output / "paired_comparisons.csv", comparisons)
    (output / "summary.md").write_text(
        "# PSR-UT Primary Baselines\n\nRaw-derived 100-independent-map tables: `summary.csv` and `paired_comparisons.csv`.\n",
        encoding="utf-8",
    )
    print({"summary_rows": len(summaries), "paired_rows": len(comparisons)})


if __name__ == "__main__":
    main()
