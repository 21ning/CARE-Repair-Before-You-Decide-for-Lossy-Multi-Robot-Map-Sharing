from __future__ import annotations

import csv

from scripts.run_psr_suite import run_suite


def test_psr_suite_persists_matched_rows_and_traces(tmp_path) -> None:
    config = {
        "seeds": [2], "map_size": 10, "obstacle_densities": [.15], "num_agents": 3,
        "observation_radius": 3, "max_episode_steps": 12,
        "data_bytes_per_agent_per_step": 52, "control_bytes_per_agent_per_step": 256,
        "repair_interval_steps": 2, "sync_interval_steps": 4,
        "corridor_horizon": 4, "corridor_radius": 1,
        "digest_base_bytes": 16, "digest_entry_bytes": 6, "ack_bytes": 8, "patch_base_bytes": 4,
        "loss_probabilities": [0.0, .3], "delay_steps": [0],
        "policies": ["one_shot_delta", "utility_triggered_repair"], "link_seed": 7,
    }
    summary = run_suite(config, tmp_path)
    rows = list(csv.DictReader((tmp_path / "results.csv").open()))
    assert summary["rows"] == 4
    assert len(rows) == 4
    assert {row["policy"] for row in rows} == {"one_shot_delta", "utility_triggered_repair"}
    assert all(row["instance_fingerprint"] == rows[0]["instance_fingerprint"] for row in rows)
    assert (tmp_path / "traces.csv").is_file()


def test_psr_suite_can_persist_preregistered_fork_instances(tmp_path) -> None:
    config = {
        "instance_family": "fork_bottleneck_upper_block",
        "seeds": [2], "map_size": 16, "obstacle_densities": [.86328125], "num_agents": 2,
        "observation_radius": 3, "max_episode_steps": 25,
        "data_bytes_per_agent_per_step": 676, "control_bytes_per_agent_per_step": 2048,
        "repair_interval_steps": 1, "sync_interval_steps": 8,
        "corridor_horizon": 8, "corridor_radius": 1,
        "digest_base_bytes": 16, "digest_entry_bytes": 6, "ack_bytes": 8, "patch_base_bytes": 4,
        "loss_probabilities": [0.0], "delay_steps": [0],
        "policies": ["no_communication", "one_shot_delta"], "link_seed": 7,
    }
    summary = run_suite(config, tmp_path)
    rows = list(csv.DictReader((tmp_path / "results.csv").open()))
    assert summary["rows"] == 2
    assert rows[0]["instance_fingerprint"] == rows[1]["instance_fingerprint"]


def test_parallel_policy_execution_reproduces_serial_rows(tmp_path) -> None:
    base = {
        "instance_family": "fork_bottleneck_upper_block",
        "seeds": [0, 1], "map_size": 16, "obstacle_densities": [.86328125], "num_agents": 2,
        "observation_radius": 3, "max_episode_steps": 25,
        "data_bytes_per_agent_per_step": 676, "control_bytes_per_agent_per_step": 2048,
        "repair_interval_steps": 1, "sync_interval_steps": 8,
        "corridor_horizon": 8, "corridor_radius": 1,
        "digest_base_bytes": 16, "digest_entry_bytes": 6, "ack_bytes": 8, "patch_base_bytes": 4,
        "loss_probabilities": [.3], "delay_steps": [0],
        "policies": ["one_shot_delta", "utility_triggered_repair"], "link_seed": 7,
    }
    serial, parallel = tmp_path / "serial", tmp_path / "parallel"
    run_suite({**base, "workers": 1}, serial)
    run_suite({**base, "workers": 2}, parallel)
    timing = {"planning_cpu_ms", "utility_trigger_cpu_ms", "episode_cpu_ms"}
    serial_rows = [{key: value for key, value in row.items() if key not in timing} for row in csv.DictReader((serial / "results.csv").open())]
    parallel_rows = [{key: value for key, value in row.items() if key not in timing} for row in csv.DictReader((parallel / "results.csv").open())]
    assert serial_rows == parallel_rows
    assert (serial / "traces.csv").read_text() == (parallel / "traces.csv").read_text()


def test_psr_suite_crosses_independent_layout_and_network_seeds(tmp_path) -> None:
    config = {
        "instance_family": "fork_bottleneck_upper_block",
        "layout_seeds": [7, 11], "network_seeds": [3, 5],
        "map_size": 16, "obstacle_densities": [.86328125], "num_agents": 2,
        "observation_radius": 3, "max_episode_steps": 25,
        "data_bytes_per_agent_per_step": 676, "control_bytes_per_agent_per_step": 2048,
        "repair_interval_steps": 1, "sync_interval_steps": 8,
        "corridor_horizon": 8, "corridor_radius": 1,
        "digest_base_bytes": 16, "digest_entry_bytes": 6, "ack_bytes": 8, "patch_base_bytes": 4,
        "loss_probabilities": [.3], "delay_steps": [0],
        "policies": ["utility_triggered_repair"], "link_seed": 7,
    }
    run_suite(config, tmp_path)
    rows = list(csv.DictReader((tmp_path / "results.csv").open()))
    assert [(row["seed"], row["layout_seed"], row["network_seed"]) for row in rows] == [
        ("0", "7", "3"), ("1", "7", "5"), ("2", "11", "3"), ("3", "11", "5"),
    ]
    assert rows[0]["instance_fingerprint"] == rows[1]["instance_fingerprint"]
    assert rows[0]["instance_fingerprint"] != rows[2]["instance_fingerprint"]
    assert {(row["topology_family"], row["map_size"], row["num_agents"]) for row in rows} == {
        ("fork_bottleneck_upper_block", "16", "2")
    }
