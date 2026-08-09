#!/usr/bin/env python3
"""Summarize the matched Action-Triggered Edge Repair diagnostic."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.analyze_psr_100map_matrix import METRICS, bootstrap, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, default=Path("results/psr_ut_action_ablation_100map"))
    parser.add_argument("--output-directory", type=Path, default=Path("results/psr_ut_action_ablation_100map/analysis"))
    parser.add_argument("--baseline-policy", default="action_triggered_repair")
    args = parser.parse_args(); args.output_directory.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((args.input_directory / "results.csv").open()))
    policies = {row["policy"] for row in rows}
    focal_policy = "utility_triggered_repair"
    required = {args.baseline_policy, focal_policy}
    if policies != required or any(sum(row["policy"] == policy for row in rows) != 100 for policy in required):
        raise ValueError("expected exactly 100 rows for each matched policy")
    by_policy = {policy: { (row["layout_seed"], row["network_seed"]): row for row in rows if row["policy"] == policy} for policy in required}
    if set(by_policy[args.baseline_policy]) != set(by_policy[focal_policy]) or len(by_policy[args.baseline_policy]) != 100:
        raise ValueError("diagnostic is not a complete matched 100-independent-map design")
    summary, paired = [], []
    for policy in sorted(required):
        group = list(by_policy[policy].values())
        if len({r["layout_seed"] for r in group}) != 100:
            raise ValueError("each action-ablation policy must use 100 independent maps")
        item = {"policy": policy, "trials": len(group), "independent_maps": 100}
        for index, metric in enumerate(METRICS):
            values = np.asarray([float(row[metric]) for row in group if row[metric] not in {"", "None"}])
            item[f"mean_{metric}"] = float(values.mean()) if len(values) else None
            item[f"std_{metric}"] = float(values.std(ddof=1)) if len(values) > 1 else None
            low, high = bootstrap(values, seed=index) if len(values) else (None, None)
            item[f"ci95_low_{metric}"], item[f"ci95_high_{metric}"] = low, high
        summary.append(item)
    for index, metric in enumerate(METRICS):
        values = np.asarray([float(by_policy[focal_policy][key][metric]) - float(by_policy[args.baseline_policy][key][metric]) for key in sorted(by_policy[focal_policy])])
        low, high = bootstrap(values, seed=10_000 + index)
        paired.append({"metric": metric, "left": focal_policy, "right": args.baseline_policy, "paired_trials": 100, "mean_difference": float(values.mean()), "std_difference": float(values.std(ddof=1)), "ci95_low": low, "ci95_high": high})
    write_csv(args.output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(args.output_directory / "paired_mean_std_ci.csv", paired)
    print({"summary_rows": len(summary), "paired_rows": len(paired)})


if __name__ == "__main__":
    main()
