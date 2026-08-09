#!/usr/bin/env python3
"""Require independent CARE reruns to agree on every non-timing field."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


TIMING_FIELDS = {
    "planning_cpu_ms", "utility_trigger_cpu_ms", "certificate_cpu_ms",
    "episode_cpu_ms",
}


def load(path: Path, *, radius: int = 2, loss: float = .3, delay: int = 0) -> dict[tuple, dict]:
    selected = {}
    for row in csv.DictReader((path / "results.csv").open()):
        if (
            int(row["observation_radius"]) != radius
            or float(row["loss_probability"]) != loss
            or int(row["delay_steps"]) != delay
        ):
            continue
        key = row["layout_seed"], row["network_seed"], row["planner"], row["policy"]
        selected[key] = {field: value for field, value in row.items() if field not in TIMING_FIELDS}
    return selected


def compare(anchor: dict, candidate: dict, *, label: str) -> dict:
    common = set(anchor) & set(candidate)
    if not common:
        raise ValueError(f"{label}: no matched rows")
    differences = [key for key in common if anchor[key] != candidate[key]]
    if differences:
        raise ValueError(f"{label}: {len(differences)} non-timing rows differ; first={differences[0]}")
    return {"study": label, "matched_rows": len(common), "non_timing_differences": 0}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--main", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--delay", type=Path, required=True)
    parser.add_argument("--extensions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    anchor = load(args.main)
    records = [
        compare(anchor, load(args.observation), label="observation_radius_r2"),
        compare(anchor, load(args.delay), label="delay_zero"),
        compare(anchor, load(args.extensions / "density_20"), label="density_20"),
    ]
    result = {"complete": True, "timing_fields_excluded": sorted(TIMING_FIELDS), "comparisons": records}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
