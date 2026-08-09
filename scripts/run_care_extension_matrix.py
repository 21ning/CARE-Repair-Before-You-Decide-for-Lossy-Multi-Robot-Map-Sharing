#!/usr/bin/env python3
"""Run 100-map CARE ablations and density/topology/scale extensions."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_psr_suite import run_suite


BASELINE_POLICIES = [
    "one_shot_delta", "retry_all_arq", "periodic_full_sync",
    "utility_triggered_repair", "deadline_aware_repair", "certificate_repair",
]


def base_config(*, workers: int, family: str = "multifork_cluttered") -> dict:
    return {
        "instance_family": family, "seed_count": 100,
        "map_size": 32, "obstacle_densities": [.2], "num_agents": 8,
        "observation_radius": 2, "max_episode_steps": 25,
        "data_bytes_per_agent_per_step": 4459,
        "control_bytes_per_agent_per_step": 512, "max_digest_peers": 1,
        "repair_interval_steps": 1, "sync_interval_steps": 4,
        "corridor_horizon": 8, "corridor_radius": 1,
        "certificate_max_cells": 8, "certificate_uncertainty_order": 2,
        "digest_base_bytes": 16, "digest_entry_bytes": 6,
        "replica_digest_bytes": 16, "path_weighted_sigma": 1.0,
        "ack_bytes": 8, "patch_base_bytes": 4,
        "loss_probabilities": [.3], "delay_steps": [0],
        "planners": ["astar", "dstar_lite"],
        "policies": BASELINE_POLICIES, "link_seed": 20260808,
        "workers": workers,
    }


def studies(workers: int) -> list[tuple[str, dict]]:
    result: list[tuple[str, dict]] = []
    for density in (.10, .20, .30, .40):
        config = base_config(workers=workers)
        config["obstacle_densities"] = [density]
        result.append((f"density_{int(density * 100):02d}", config))
    for density in (.10, .20, .30, .40):
        config = base_config(workers=workers, family="random")
        config["obstacle_densities"] = [density]
        config["policies"] = ["one_shot_delta", "retry_all_arq", "certificate_repair"]
        config["planners"] = ["astar"]
        result.append((f"random_negative_density_{int(density * 100):02d}", config))

    cadence = base_config(workers=workers)
    cadence["repair_interval_steps"] = 4
    cadence["policies"] = ["certificate_repair"]
    result.append(("certificate_cadence_k4", cadence))
    for name, max_cells, order in (
        ("certificate_q1_cap8", 8, 1),
        ("certificate_q2_cap4", 4, 2),
        ("certificate_q2_cap12", 12, 2),
    ):
        config = base_config(workers=workers)
        config["certificate_max_cells"] = max_cells
        config["certificate_uncertainty_order"] = order
        config["policies"] = ["certificate_repair"]
        result.append((name, config))

    for topology in ("t_junction", "asymmetric_fork", "narrow_bypass"):
        config = base_config(workers=workers, family=f"multifork_{topology}")
        config["obstacle_densities"] = [{
            "t_junction": .8359375,
            "asymmetric_fork": .83984375,
            "narrow_bypass": .83984375,
        }[topology]]
        result.append((f"topology_{topology}", config))

    for agents, size, steps in ((4, 24, 18), (8, 32, 32), (16, 48, 32), (32, 64, 32)):
        config = base_config(workers=workers, family="tiled_cluttered_fork")
        config.update({
            "map_size": size, "num_agents": agents, "max_episode_steps": steps,
            "planners": ["astar"],
            "policies": [
                "one_shot_delta", "retry_all_arq",
                "utility_triggered_repair", "certificate_repair",
            ],
        })
        result.append((f"scale_agents_{agents}_map_{size}", config))
    return result


def run_matrix(output_directory: Path, workers: int) -> dict:
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty output: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest = {
        "design": "100 independent matched layouts and loss traces per condition",
        "primary_fov": "5x5", "workers": workers, "studies": [],
    }
    for name, config in studies(workers):
        completed = run_suite(config, output_directory / name)
        record = {
            "study": name, "config": config,
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
            "rows": completed["rows"], "trace_rows": completed["trace_rows"],
            "workers": completed["workers"],
        }
        manifest["studies"].append(record)
        print(json.dumps(record), flush=True)
    (output_directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    manifest = run_matrix(args.output_directory, args.workers)
    print(json.dumps({"studies": len(manifest["studies"]), "workers": args.workers}))


if __name__ == "__main__":
    main()
