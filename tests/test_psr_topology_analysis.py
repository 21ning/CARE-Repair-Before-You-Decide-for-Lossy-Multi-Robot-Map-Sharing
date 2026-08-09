from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts.analyze_psr_topology_variants import TOPOLOGIES, analyze_directories


def _rows() -> list[dict[str, str]]:
    policies = (
        "one_shot_delta", "retry_all_arq", "path_weighted_arq",
        "mismatch_triggered_full_repair", "utility_triggered_repair",
    )
    fields = {
        "completion_success_rate": "1", "episode_length": "20", "attempted_bytes": "100",
        "attempted_data_bytes": "50", "attempted_control_bytes": "25", "attempted_repair_bytes": "25",
        "delivered_bytes": "70", "delivered_data_bytes": "35", "delivered_control_bytes": "20",
        "delivered_repair_bytes": "15", "attempted_retransmission_messages": "2",
        "attempted_retransmission_bytes": "26",
    }
    return [
        {
            "seed": str(seed), "layout_seed": str(seed), "network_seed": str(seed),
            "policy": policy, "loss_probability": "0.3", "delay_steps": "0",
            "instance_fingerprint": f"instance-{seed}", **fields,
        }
        for seed in range(100) for policy in policies
    ]


def test_topology_analysis_requires_all_frozen_families(tmp_path: Path) -> None:
    directories = {}
    for topology, family in TOPOLOGIES.items():
        directory = tmp_path / topology
        directory.mkdir()
        (directory / "summary.json").write_text(json.dumps({"config": {"instance_family": family}}))
        with (directory / "results.csv").open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(_rows()[0]))
            writer.writeheader(); writer.writerows(_rows())
        directories[topology] = directory
    summaries, comparisons = analyze_directories(directories)
    assert len(summaries) == 15
    assert len(comparisons) == 144
