#!/usr/bin/env python3
"""Expand and run the frozen non-tiled natural-critical scale matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_psr_suite import run_suite


def run(config: dict, output: Path) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    shared = {key: value for key, value in config.items() if key not in {"scales", "output_directory"}}
    for scale in config["scales"]:
        agents = int(scale["num_agents"])
        scale_config = {
            **shared,
            "num_agents": agents,
            "map_size": int(scale["map_size"]),
            "max_episode_steps": int(scale["max_episode_steps"]),
        }
        target = output / f"agents-{agents}"
        summaries.append(run_suite(scale_config, target))
    manifest = {
        "complete": True,
        "family": "natural_critical_random",
        "scales": summaries,
        "non_tiled": True,
        "independent_maps_per_condition": int(config["seed_count"]),
    }
    (output / "scale_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path)
    parser.add_argument("--workers", type=int)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    if args.workers is not None:
        config["workers"] = args.workers
    output = args.output_directory or Path(config["output_directory"])
    print(json.dumps(run(config, output), indent=2))


if __name__ == "__main__":
    main()
