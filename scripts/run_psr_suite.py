#!/usr/bin/env python3
"""Run matched closed-loop PSR-UT reliability experiments into a new directory."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cmvr.communication import LinkConfig
from cmvr.env import (
    PSRClosedLoopRunner, PSRConfig, ReplicaPolicy, generate_fork_bottleneck_instance, generate_multifork_bottleneck_instance,
    generate_rotated_multifork_bottleneck_instance, generate_multifork_topology_variant_instance,
    generate_cluttered_multifork_instance, generate_tiled_cluttered_fork_instance,
    generate_natural_critical_instance,
    generate_instance, load_instance, save_instance,
)
from cmvr.utils.config import ExperimentConfig


RESULT_FIELDS = [
    "seed", "topology_family", "map_size", "num_agents", "observation_radius",
    "layout_seed", "network_seed", "instance_fingerprint", "layout_fingerprint",
    "density", "loss_probability", "delay_steps", "planner", "policy",
    "episode_length", "completion_success_rate", "observer_success_rate",
    "seeker_success_rate", "critical_pair_success_rate",
    "all_seekers_success", "instance_success_rate", "completed_mask",
    "observer_ids", "seeker_ids", "critical_pairs", "completion_steps",
    "mean_seeker_completion_step", "mean_observer_completion_step",
    "mean_seeker_completion_step_censored",
    "mean_replica_error", "mean_path_repairable_error", "mean_path_truth_error",
    "mean_recovery_latency", "unresolved_repair_events", "repair_events",
    "attempted_messages", "attempted_bytes", "lost_messages", "lost_bytes",
    "delivered_messages", "delivered_bytes", "deferred_messages",
    "attempted_retransmission_messages", "attempted_retransmission_bytes",
    "attempted_data_bytes", "delivered_data_bytes", "attempted_control_bytes",
    "delivered_control_bytes", "attempted_repair_bytes", "delivered_repair_bytes",
    "optimistic_planning_calls", "pessimistic_planning_calls", "utility_trigger_checks",
    "utility_triggered_receivers", "corridor_query_receivers", "planning_cpu_ms",
    "deadline_trigger_checks", "deadline_ambiguous_receivers",
    "deadline_feasible_receivers", "deadline_infeasible_receivers",
    "deadline_query_cells", "mean_decision_slack",
    "certificate_checks", "certificate_scenario_planning_calls",
    "certificate_conflicting_pairs", "certificate_feasible_pairs",
    "certificate_infeasible_pairs", "certificate_candidate_cells",
    "certificate_query_cells", "certificate_candidate_cap_checks",
    "certificate_candidate_cap_hits", "certificate_candidate_cap_hit_rate",
    "mean_uncapped_certificate_candidates",
    "commitment_gate_checks", "commitment_gate_closed",
    "commitment_raw_query_cells", "commitment_suppressed_query_cells",
    "critical_pair_count", "critical_peer_observation_events",
    "critical_self_observation_events", "critical_route_commitment_events",
    "mean_critical_peer_observation_step", "mean_critical_self_observation_step",
    "mean_route_commitment_step", "mean_visibility_gap_steps",
    "mean_usable_communication_window_steps", "decision_before_self_observation_rate",
    "task_aware_checks", "task_aware_candidate_cells", "task_aware_query_cells",
    "closest_work_planning_calls", "closest_work_simulation_samples",
    "single_cell_planning_calls", "single_cell_sensitive_cells",
    "single_cell_infeasible_cells", "task_aware_cpu_ms",
    "scuttle_digest_exchanges", "scuttle_patch_updates",
    "merkle_nodes_compared", "merkle_leaf_repairs",
    "iblt_decode_attempts", "iblt_decode_successes", "iblt_patch_updates",
    "utility_trigger_cpu_ms", "certificate_cpu_ms",
    "episode_cpu_ms",
]
TRACE_FIELDS = [
    "seed", "observation_radius", "density", "loss_probability", "delay_steps", "planner", "policy", "step",
    "replica_error", "path_repairable_error", "path_truth_error", "repair_events", "candidate_updates",
]


def output_directory(config: dict, override: str | None) -> Path:
    directory = Path(override or config["output_directory"])
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty PSR output: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def link_seed(seed: int, density: float, loss: float, delay: int, config_seed: int) -> int:
    material = f"{config_seed}|{seed}|{density:.6f}|{loss:.6f}|{delay}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big")


def runner_config(config: dict, *, seed: int, density: float, loss: float, delay: int) -> PSRConfig:
    link = LinkConfig(
        loss_probability=loss, delay_steps=delay,
        seed=link_seed(seed, density, loss, delay, int(config["link_seed"])),
        burst_start_step=config.get("burst_start_step"),
        burst_length_steps=int(config.get("burst_length_steps", 0)),
    )
    return PSRConfig(
        data_bytes_per_agent_per_step=int(config["data_bytes_per_agent_per_step"]),
        control_bytes_per_agent_per_step=int(config["control_bytes_per_agent_per_step"]),
        repair_interval_steps=int(config["repair_interval_steps"]),
        sync_interval_steps=int(config["sync_interval_steps"]),
        corridor_horizon=int(config["corridor_horizon"]),
        corridor_radius=int(config["corridor_radius"]),
        digest_base_bytes=int(config["digest_base_bytes"]),
        digest_entry_bytes=int(config["digest_entry_bytes"]),
        ack_bytes=int(config["ack_bytes"]),
        patch_base_bytes=int(config["patch_base_bytes"]),
        replica_digest_bytes=int(config.get("replica_digest_bytes", 16)),
        path_weighted_sigma=float(config.get("path_weighted_sigma", 1.0)),
        max_digest_peers=config.get("max_digest_peers"),
        certificate_max_cells=int(config.get("certificate_max_cells", 8)),
        certificate_uncertainty_order=int(config.get("certificate_uncertainty_order", 2)),
        iblt_cells=int(config.get("iblt_cells", 21)),
        iblt_hashes=int(config.get("iblt_hashes", 3)),
        iblt_hash_seed=int(config.get("iblt_hash_seed", 20260809)),
        iblt_partitions=int(config.get("iblt_partitions", 16)),
        merkle_fanout=int(config.get("merkle_fanout", 16)),
        merkle_session_steps=int(config.get("merkle_session_steps", 4)),
        external_candidate_multiplier=int(config.get("external_candidate_multiplier", 2)),
        ocbc_samples=int(config.get("ocbc_samples", 128)),
        algorithm_seed=int(config.get("algorithm_seed", 20260813)),
        link=link,
    )


def _run_policy_task(task: tuple[dict, float, int, int, int, int, float, int, str, str, str]) -> tuple[dict, list[dict]]:
    """Run one independent policy episode for deterministic process parallelism."""
    config, density, observation_radius, trial_seed, layout_seed, network_seed, loss, delay, planner_name, policy_name, instance_path = task
    # Instances are selected/generated and frozen before any policy executes.
    # Workers load those exact files rather than rerunning an expensive natural
    # selector for every policy, which also makes outcome-independent selection
    # operationally explicit.
    instance = load_instance(instance_path)
    run_config = runner_config(config, seed=network_seed, density=density, loss=loss, delay=delay)
    result = PSRClosedLoopRunner(
        policy=ReplicaPolicy(policy_name), config=run_config, planner=planner_name,
    ).run(instance)
    row = {
        "seed": trial_seed, "topology_family": config.get("instance_family", "random"),
        "map_size": int(config["map_size"]), "num_agents": int(config["num_agents"]),
        "observation_radius": observation_radius,
        "layout_seed": layout_seed, "network_seed": network_seed,
        "instance_fingerprint": instance.fingerprint(),
        "layout_fingerprint": instance.layout_fingerprint(), "density": density,
        "loss_probability": loss, "delay_steps": delay, "planner": planner_name,
        "policy": policy_name,
        "episode_length": result.episode_length,
        "completion_success_rate": result.completion_success_rate,
        "observer_success_rate": result.observer_success_rate,
        "seeker_success_rate": result.seeker_success_rate,
        "critical_pair_success_rate": result.critical_pair_success_rate,
        "all_seekers_success": int(all(result.completed[index] for index in result.seeker_ids)) if result.seeker_ids else int(all(result.completed)),
        "instance_success_rate": result.instance_success_rate,
        "completed_mask": "".join("1" if value else "0" for value in result.completed),
        "observer_ids": json.dumps(result.observer_ids, separators=(",", ":")),
        "seeker_ids": json.dumps(result.seeker_ids, separators=(",", ":")),
        "critical_pairs": json.dumps(result.critical_pairs, separators=(",", ":")),
        "completion_steps": json.dumps(result.completion_steps, separators=(",", ":")),
        "mean_seeker_completion_step": result.mean_seeker_completion_step,
        "mean_observer_completion_step": result.mean_observer_completion_step,
        "mean_seeker_completion_step_censored": result.mean_seeker_completion_step_censored,
        "mean_replica_error": result.mean_replica_error,
        "mean_path_repairable_error": result.mean_path_repairable_error,
        "mean_path_truth_error": result.mean_path_truth_error,
        "mean_recovery_latency": result.mean_recovery_latency,
        "unresolved_repair_events": result.unresolved_repair_events,
        "repair_events": result.repair_events,
        "optimistic_planning_calls": result.optimistic_planning_calls,
        "pessimistic_planning_calls": result.pessimistic_planning_calls,
        "utility_trigger_checks": result.utility_trigger_checks,
        "utility_triggered_receivers": result.utility_triggered_receivers,
        "corridor_query_receivers": result.corridor_query_receivers,
        "deadline_trigger_checks": result.deadline_trigger_checks,
        "deadline_ambiguous_receivers": result.deadline_ambiguous_receivers,
        "deadline_feasible_receivers": result.deadline_feasible_receivers,
        "deadline_infeasible_receivers": result.deadline_infeasible_receivers,
        "deadline_query_cells": result.deadline_query_cells,
        "mean_decision_slack": result.mean_decision_slack,
        "certificate_checks": result.certificate_checks,
        "certificate_scenario_planning_calls": result.certificate_scenario_planning_calls,
        "certificate_conflicting_pairs": result.certificate_conflicting_pairs,
        "certificate_feasible_pairs": result.certificate_feasible_pairs,
        "certificate_infeasible_pairs": result.certificate_infeasible_pairs,
        "certificate_candidate_cells": result.certificate_candidate_cells,
        "certificate_query_cells": result.certificate_query_cells,
        "certificate_candidate_cap_checks": result.certificate_candidate_cap_checks,
        "certificate_candidate_cap_hits": result.certificate_candidate_cap_hits,
        "certificate_candidate_cap_hit_rate": result.certificate_candidate_cap_hit_rate,
        "mean_uncapped_certificate_candidates": result.mean_uncapped_certificate_candidates,
        "commitment_gate_checks": result.commitment_gate_checks,
        "commitment_gate_closed": result.commitment_gate_closed,
        "commitment_raw_query_cells": result.commitment_raw_query_cells,
        "commitment_suppressed_query_cells": result.commitment_suppressed_query_cells,
        "critical_pair_count": result.critical_pair_count,
        "critical_peer_observation_events": result.critical_peer_observation_events,
        "critical_self_observation_events": result.critical_self_observation_events,
        "critical_route_commitment_events": result.critical_route_commitment_events,
        "mean_critical_peer_observation_step": result.mean_critical_peer_observation_step,
        "mean_critical_self_observation_step": result.mean_critical_self_observation_step,
        "mean_route_commitment_step": result.mean_route_commitment_step,
        "mean_visibility_gap_steps": result.mean_visibility_gap_steps,
        "mean_usable_communication_window_steps": result.mean_usable_communication_window_steps,
        "decision_before_self_observation_rate": result.decision_before_self_observation_rate,
        "task_aware_checks": result.task_aware_checks,
        "task_aware_candidate_cells": result.task_aware_candidate_cells,
        "task_aware_query_cells": result.task_aware_query_cells,
        "closest_work_planning_calls": result.closest_work_planning_calls,
        "closest_work_simulation_samples": result.closest_work_simulation_samples,
        "single_cell_planning_calls": result.single_cell_planning_calls,
        "single_cell_sensitive_cells": result.single_cell_sensitive_cells,
        "single_cell_infeasible_cells": result.single_cell_infeasible_cells,
        "task_aware_cpu_ms": result.task_aware_cpu_ms,
        "scuttle_digest_exchanges": result.scuttle_digest_exchanges,
        "scuttle_patch_updates": result.scuttle_patch_updates,
        "merkle_nodes_compared": result.merkle_nodes_compared,
        "merkle_leaf_repairs": result.merkle_leaf_repairs,
        "iblt_decode_attempts": result.iblt_decode_attempts,
        "iblt_decode_successes": result.iblt_decode_successes,
        "iblt_patch_updates": result.iblt_patch_updates,
        "planning_cpu_ms": result.planning_cpu_ms,
        "utility_trigger_cpu_ms": result.utility_trigger_cpu_ms,
        "certificate_cpu_ms": result.certificate_cpu_ms,
        "episode_cpu_ms": result.episode_cpu_ms,
        **result.network_summary,
    }
    traces = [{
        "seed": trial_seed, "observation_radius": observation_radius,
        "density": density, "loss_probability": loss,
        "delay_steps": delay, "planner": planner_name, "policy": policy_name,
        "step": trace.step,
        "replica_error": trace.replica_error,
        "path_repairable_error": trace.path_repairable_error,
        "path_truth_error": trace.path_truth_error,
        "repair_events": trace.repair_events,
        "candidate_updates": trace.candidate_updates,
    } for trace in result.traces]
    return row, traces


def run_suite(config: dict, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    instances = output / "instances"
    instances.mkdir()
    tasks = []
    accepted_layouts: list[dict] = []
    instance_paths: dict[tuple[float, int, int], str] = {}
    layout_seeds = config.get("layout_seeds")
    network_seeds = config.get("network_seeds")
    if (layout_seeds is None) != (network_seeds is None):
        raise ValueError("layout_seeds and network_seeds must be supplied together")
    if layout_seeds is None:
        seeds = config.get("seeds")
        if seeds is None:
            seeds = range(int(config["seed_count"]))
        trial_plan = [(int(seed), int(seed), int(seed)) for seed in seeds]
    else:
        trial_plan = [
            (layout_index * len(network_seeds) + network_index, int(layout_seed), int(network_seed))
            for layout_index, layout_seed in enumerate(layout_seeds)
            for network_index, network_seed in enumerate(network_seeds)
        ]
    configured_radii = config.get("observation_radii")
    if configured_radii is None:
        configured_radii = [config["observation_radius"]]
    observation_radii = tuple(dict.fromkeys(int(value) for value in configured_radii))
    if not observation_radii or min(observation_radii) < 1:
        raise ValueError("observation radii must be positive")
    for density in config["obstacle_densities"]:
        density_tag = f"{float(density):.2f}".replace(".", "p")
        for observation_radius in observation_radii:
            for layout_seed in dict.fromkeys(layout_seed for _, layout_seed, _ in trial_plan):
                instance = _instance_for_condition(
                    config, seed=layout_seed, density=float(density),
                    observation_radius=observation_radius,
                )
                json_path, _ = save_instance(
                    instance,
                    instances / (
                        f"density-{density_tag}_radius-{observation_radius}_layout-"
                        f"{layout_seed}_{instance.fingerprint()[:12]}.json"
                    ),
                )
                instance_paths[(float(density), observation_radius, layout_seed)] = str(json_path.resolve())
                if config.get("instance_family") == "natural_critical_random":
                    accepted_layouts.append({
                        "layout_seed": layout_seed,
                        "observation_radius": observation_radius,
                        "instance_fingerprint": instance.fingerprint(),
                        "layout_fingerprint": instance.layout_fingerprint(),
                        "starts": [list(cell) for cell in instance.starts],
                        "goals": [list(cell) for cell in instance.goals],
                        "metadata": dict(instance.package_metadata),
                    })
            for trial_seed, layout_seed, network_seed in trial_plan:
                for loss in config["loss_probabilities"]:
                    for delay in config["delay_steps"]:
                        planners = config.get("planners", [config.get("planner", "astar")])
                        for planner_name in planners:
                            for policy_name in config["policies"]:
                                tasks.append((
                                    config, float(density), observation_radius,
                                    trial_seed, layout_seed, network_seed, float(loss),
                                    int(delay), str(planner_name), str(policy_name),
                                    instance_paths[(float(density), observation_radius, layout_seed)],
                                ))
    # Persist the complete accepted population before any policy worker starts.
    # This makes the selection boundary observable on disk even if execution is
    # interrupted, and prevents a result-dependent process from rewriting the
    # population manifest after seeing outcomes.
    if accepted_layouts:
        (output / "accepted_layout_manifest.json").write_text(json.dumps({
            "selection_precedes_all_policy_execution": True,
            "selection_uses_policy_or_link_outcomes": False,
            "records": accepted_layouts,
        }, indent=2) + "\n")
    workers = int(config.get("workers", 1))
    if workers < 1:
        raise ValueError("workers must be positive")
    if workers == 1:
        completed = map(_run_policy_task, tasks)
    else:
        executor = ProcessPoolExecutor(max_workers=min(workers, len(tasks)))
        completed = executor.map(_run_policy_task, tasks)
    rows = traces = 0
    with (output / "results.csv").open("x", newline="") as result_file, (output / "traces.csv").open("x", newline="") as trace_file:
        result_writer = csv.DictWriter(result_file, fieldnames=RESULT_FIELDS)
        trace_writer = csv.DictWriter(trace_file, fieldnames=TRACE_FIELDS)
        result_writer.writeheader()
        trace_writer.writeheader()
        try:
            for row, trace_rows in completed:
                result_writer.writerow(row)
                result_file.flush()
                rows += 1
                trace_writer.writerows(trace_rows)
                traces += len(trace_rows)
                trace_file.flush()
        finally:
            if workers > 1:
                executor.shutdown(wait=True)
    summary = {"rows": rows, "trace_rows": traces, "workers": workers, "config": config, "output_directory": str(output)}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _instance_for_condition(
    config: dict, *, seed: int, density: float,
    observation_radius: int | None = None,
):
    observation_radius = int(
        config["observation_radius"] if observation_radius is None else observation_radius
    )
    family = config.get("instance_family", "random")
    if family == "random":
        return generate_instance(ExperimentConfig(
            seed=seed, map_size=int(config["map_size"]), obstacle_density=density,
            num_agents=int(config["num_agents"]), observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
        ))
    if family == "fork_bottleneck_upper_block":
        return generate_fork_bottleneck_instance(
            seed=seed, map_size=int(config["map_size"]),
            observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
        )
    if family == "multifork_bottleneck_upper_block":
        return generate_multifork_bottleneck_instance(
            seed=seed, map_size=int(config["map_size"]),
            observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
        )
    if family == "multifork_bottleneck_rotated":
        return generate_rotated_multifork_bottleneck_instance(
            seed=seed, map_size=int(config["map_size"]),
            observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
        )
    if family in {"multifork_t_junction", "multifork_asymmetric_fork", "multifork_narrow_bypass"}:
        return generate_multifork_topology_variant_instance(
            topology=family.removeprefix("multifork_"), seed=seed,
            map_size=int(config["map_size"]), observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
        )
    if family == "multifork_cluttered":
        return generate_cluttered_multifork_instance(
            seed=seed, obstacle_density=density, map_size=int(config["map_size"]),
            num_agents=int(config["num_agents"]), observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
        )
    if family == "tiled_cluttered_fork":
        return generate_tiled_cluttered_fork_instance(
            seed=seed, obstacle_density=density, map_size=int(config["map_size"]),
            num_agents=int(config["num_agents"]), observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
        )
    if family == "natural_critical_random":
        return generate_natural_critical_instance(
            seed=seed, obstacle_density=density, map_size=int(config["map_size"]),
            num_agents=int(config["num_agents"]), observation_radius=observation_radius,
            max_episode_steps=int(config["max_episode_steps"]),
            corridor_horizon=int(config.get("corridor_horizon", 8)),
            max_raw_attempts=int(config.get("natural_max_raw_attempts", 128)),
            candidate_draws_per_attempt=config.get("natural_candidate_draws_per_attempt"),
        )
    raise ValueError(f"unsupported PSR instance_family: {family}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Frozen YAML experiment configuration.")
    parser.add_argument("--output-directory")
    parser.add_argument("--workers", type=int, help="Independent policy episodes to run concurrently")
    args = parser.parse_args()
    config = yaml.safe_load(Path(args.config).read_text())
    if args.workers is not None:
        config["workers"] = args.workers
    print(json.dumps(run_suite(config, output_directory(config, args.output_directory))))


if __name__ == "__main__":
    main()
