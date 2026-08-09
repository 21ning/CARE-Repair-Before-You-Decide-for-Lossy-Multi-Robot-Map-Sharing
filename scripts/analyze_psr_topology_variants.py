#!/usr/bin/env python3
"""Summarize the three preregistered decision-critical topology matrices."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_psr_external_baselines import NON_PERIODIC_POLICIES, analyze, write_csv


TOPOLOGIES = {
    "t_junction": "multifork_t_junction",
    "asymmetric_fork": "multifork_asymmetric_fork",
    "narrow_bypass": "multifork_narrow_bypass",
}


def analyze_directories(directories: dict[str, Path]) -> tuple[list[dict], list[dict]]:
    """Validate all frozen matrices and return topology-labelled summaries."""
    if set(directories) != set(TOPOLOGIES):
        raise ValueError("exactly the three preregistered topology directories are required")
    summaries: list[dict] = []
    comparisons: list[dict] = []
    for topology, family in TOPOLOGIES.items():
        directory = directories[topology]
        run_config = json.loads((directory / "summary.json").read_text())["config"]
        if run_config["instance_family"] != family:
            raise ValueError(f"{topology} directory has the wrong instance family")
        summary, pairs = analyze(
            list(csv.DictReader((directory / "results.csv").open())),
            policies=NON_PERIODIC_POLICIES,
        )
        summaries.extend({"topology": topology, **row} for row in summary)
        comparisons.extend({"topology": topology, **row} for row in pairs)
    return summaries, comparisons


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--t-junction", type=Path, required=True)
    parser.add_argument("--asymmetric-fork", type=Path, required=True)
    parser.add_argument("--narrow-bypass", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_directory
    output.mkdir(parents=True, exist_ok=True)
    summaries, comparisons = analyze_directories({
        "t_junction": args.t_junction,
        "asymmetric_fork": args.asymmetric_fork,
        "narrow_bypass": args.narrow_bypass,
    })
    write_csv(output / "summary.csv", summaries)
    write_csv(output / "paired_comparisons.csv", comparisons)
    lines = [
        "# PSR decision-critical topology variants", "",
        "| Topology | Method | CSR | Episode length | Attempted bytes |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in summaries:
        lines.append(
            f"| {row['topology']} | {row['policy']} | "
            f"{float(row['mean_completion_success_rate']):.3f} | "
            f"{float(row['mean_episode_length']):.2f} | "
            f"{float(row['mean_attempted_bytes']):.0f} |"
        )
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print({"summary_rows": len(summaries), "paired_rows": len(comparisons)})


if __name__ == "__main__":
    main()
