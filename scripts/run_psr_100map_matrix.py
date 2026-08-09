#!/usr/bin/env python3
"""Run the final PSR-UT evidence matrix with 100 independent matched maps."""

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


MAP_SEEDS = list(range(100))
DENSITIES = (.10, .20, .30, .40)
EXTERNAL_POLICIES = [
    "one_shot_delta", "retry_all_arq", "path_weighted_arq",
    "mismatch_triggered_full_repair", "utility_triggered_repair",
]


def base_config(*, density: float, instance_family: str = "multifork_cluttered") -> dict:
    return {
        "instance_family": instance_family,
        "seeds": MAP_SEEDS,
        "map_size": 32, "obstacle_densities": [density], "num_agents": 8,
        "observation_radius": 3, "max_episode_steps": 25,
        "data_bytes_per_agent_per_step": 4459, "control_bytes_per_agent_per_step": 512,
        "max_digest_peers": 1, "repair_interval_steps": 1, "sync_interval_steps": 8,
        "corridor_horizon": 8, "corridor_radius": 1,
        "digest_base_bytes": 16, "digest_entry_bytes": 6, "replica_digest_bytes": 16,
        "path_weighted_sigma": 1.0, "ack_bytes": 8, "patch_base_bytes": 4,
        "link_seed": 20260808, "workers": 32,
    }


def formal_studies(*, workers: int) -> list[tuple[str, dict]]:
    if workers < 1:
        raise ValueError("workers must be positive")
    studies: list[tuple[str, dict]] = []
    loss = base_config(density=.20)
    loss.update({"loss_probabilities": [0.0, .1, .2, .3, .4, .5], "delay_steps": [0], "policies": EXTERNAL_POLICIES})
    studies.append(("loss_sweep", loss))
    for density in DENSITIES:
        study = base_config(density=density)
        study.update({"loss_probabilities": [.3], "delay_steps": [0], "policies": EXTERNAL_POLICIES})
        studies.append((f"obstacle_density_{int(density * 100):02d}", study))
    delay = base_config(density=.20)
    delay.update({"loss_probabilities": [.3], "delay_steps": [0, 1, 2, 4], "policies": EXTERNAL_POLICIES})
    studies.append(("delay_sweep", delay))
    for interval in (1, 4):
        study = base_config(density=.20)
        study.update({"repair_interval_steps": interval, "loss_probabilities": [.3], "delay_steps": [0], "policies": ["utility_triggered_repair"]})
        studies.append((f"timing_k{interval}", study))
    scope = base_config(density=.20)
    scope.update({"loss_probabilities": [.3], "delay_steps": [0], "policies": ["full_replica_repair", "utility_triggered_repair"]})
    studies.append(("repair_scope", scope))
    for density in DENSITIES:
        study = base_config(density=density, instance_family="random")
        study.update({"loss_probabilities": [.3], "delay_steps": [0], "policies": ["one_shot_delta", "retry_all_arq", "utility_triggered_repair"]})
        studies.append((f"random_negative_density_{int(density * 100):02d}", study))
    for name, config in studies:
        config["workers"] = workers
    return studies


def run_matrix(*, output_directory: Path, workers: int) -> dict:
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty PSR-UT matrix output: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    studies = formal_studies(workers=workers)
    manifest = {
        "design": "100 independent matched maps with one independent network trace per map",
        "map_seeds": MAP_SEEDS,
        "workers": workers, "studies": [],
    }
    for name, config in studies:
        result = run_suite(config, output_directory / name)
        manifest["studies"].append({
            "study": name, "config": config,
            "config_sha256": hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest(),
            "rows": result["rows"], "trace_rows": result["trace_rows"], "workers": result["workers"],
        })
        print(json.dumps({"study": name, "rows": result["rows"], "workers": result["workers"]}), flush=True)
    (output_directory / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, default=Path("results/psr_ut_formal_100map_matrix"))
    parser.add_argument("--workers", type=int, default=32)
    args = parser.parse_args()
    manifest = run_matrix(output_directory=args.output_directory, workers=args.workers)
    print(json.dumps({"studies": len(manifest["studies"]), "workers": manifest["workers"]}))


if __name__ == "__main__":
    main()
