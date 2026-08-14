from __future__ import annotations

from cmvr.communication import LinkConfig
from cmvr.env import (
    critical_decision_pairs, generate_natural_critical_instance,
    natural_bitmap_sha256, natural_critical_raw_seed,
    PSRClosedLoopRunner, PSRConfig, ReplicaPolicy, generate_fork_bottleneck_instance,
    generate_multifork_bottleneck_instance, generate_multifork_topology_variant_instance,
    generate_rotated_multifork_bottleneck_instance, generate_cluttered_multifork_instance,
    generate_tiled_cluttered_fork_instance,
    sample_natural_occupancy_bitmap,
)
import json
import numpy as np

from cmvr.planning import AStarPlanner


def _config() -> PSRConfig:
    return PSRConfig(
        data_bytes_per_agent_per_step=676,
        control_bytes_per_agent_per_step=2048,
        repair_interval_steps=1,
        sync_interval_steps=8,
        corridor_horizon=8,
        corridor_radius=1,
        link=LinkConfig(loss_probability=0.0, delay_steps=0, seed=1),
    )


def test_fork_bottleneck_is_deterministic_and_remote_state_changes_the_fork_choice() -> None:
    instance = generate_fork_bottleneck_instance(seed=1)
    assert instance.fingerprint() == generate_fork_bottleneck_instance(seed=1).fingerprint()
    assert instance.obstacle_density == .86328125

    no_communication = PSRClosedLoopRunner(policy=ReplicaPolicy.NO_COMMUNICATION, config=_config()).run(instance)
    one_shot = PSRClosedLoopRunner(policy=ReplicaPolicy.ONE_SHOT_DELTA, config=_config()).run(instance)

    # At the fork (step 4), the seeker chooses the locally deterministic upper
    # branch without the observer's remote blockage and the lower branch with it.
    assert no_communication.action_trace[4][1] == 1
    assert one_shot.action_trace[4][1] == 2
    assert no_communication.completion_success_rate == .5
    assert one_shot.completion_success_rate == 1.0


def test_multifork_has_four_matched_remote_route_choices() -> None:
    instance = generate_multifork_bottleneck_instance(seed=0)
    config = PSRConfig(
        data_bytes_per_agent_per_step=4459, control_bytes_per_agent_per_step=512,
        repair_interval_steps=1, max_digest_peers=1,
        link=LinkConfig(loss_probability=0.0, delay_steps=0, seed=1),
    )
    no_communication = PSRClosedLoopRunner(policy=ReplicaPolicy.NO_COMMUNICATION, config=config).run(instance)
    one_shot = PSRClosedLoopRunner(policy=ReplicaPolicy.ONE_SHOT_DELTA, config=config).run(instance)
    assert no_communication.completion_success_rate == .5
    assert one_shot.completion_success_rate == 1.0
    assert all(no_communication.action_trace[4][seeker] == 1 for seeker in (1, 3, 5, 7))
    assert all(one_shot.action_trace[4][seeker] == 2 for seeker in (1, 3, 5, 7))


def test_rotated_multifork_preserves_remote_information_mechanism() -> None:
    instance = generate_rotated_multifork_bottleneck_instance(seed=0)
    config = PSRConfig(
        data_bytes_per_agent_per_step=4459, control_bytes_per_agent_per_step=512,
        repair_interval_steps=1, max_digest_peers=1,
        link=LinkConfig(loss_probability=0.0, delay_steps=0, seed=1),
    )
    no_communication = PSRClosedLoopRunner(policy=ReplicaPolicy.NO_COMMUNICATION, config=config).run(instance)
    one_shot = PSRClosedLoopRunner(policy=ReplicaPolicy.ONE_SHOT_DELTA, config=config).run(instance)
    assert no_communication.completion_success_rate == .5
    assert one_shot.completion_success_rate == 1.0


def test_topology_variants_preserve_the_remote_route_change_mechanism() -> None:
    config = PSRConfig(
        data_bytes_per_agent_per_step=4459, control_bytes_per_agent_per_step=512,
        repair_interval_steps=1, max_digest_peers=1,
        link=LinkConfig(loss_probability=0.0, delay_steps=0, seed=1),
    )
    for radius in (2, 3):
        for topology in ("t_junction", "asymmetric_fork", "narrow_bypass"):
            instance = generate_multifork_topology_variant_instance(
                topology=topology, seed=0, observation_radius=radius,
            )
            assert instance.fingerprint() == generate_multifork_topology_variant_instance(
                topology=topology, seed=0, observation_radius=radius,
            ).fingerprint()
            no_communication = PSRClosedLoopRunner(policy=ReplicaPolicy.NO_COMMUNICATION, config=config).run(instance)
            one_shot = PSRClosedLoopRunner(policy=ReplicaPolicy.ONE_SHOT_DELTA, config=config).run(instance)
            assert no_communication.completion_success_rate == .5
            assert one_shot.completion_success_rate == 1.0
            assert one_shot.critical_pair_count == 4


def test_topology_variants_have_100_independent_physical_layouts() -> None:
    for topology in ("t_junction", "asymmetric_fork", "narrow_bypass"):
        instances = [generate_multifork_topology_variant_instance(
            topology=topology, seed=seed, observation_radius=2,
        ) for seed in range(100)]
        assert len({instance.layout_fingerprint() for instance in instances}) == 100


def test_cluttered_multifork_preserves_protected_routes_at_exact_density() -> None:
    instance = generate_cluttered_multifork_instance(seed=0, obstacle_density=.1)
    assert instance.obstacle_density == 102 / 1024
    config = PSRConfig(
        data_bytes_per_agent_per_step=4459, control_bytes_per_agent_per_step=512,
        repair_interval_steps=1, max_digest_peers=1,
        link=LinkConfig(loss_probability=0.0, delay_steps=0, seed=1),
    )
    no_communication = PSRClosedLoopRunner(policy=ReplicaPolicy.NO_COMMUNICATION, config=config).run(instance)
    one_shot = PSRClosedLoopRunner(policy=ReplicaPolicy.ONE_SHOT_DELTA, config=config).run(instance)
    assert no_communication.completion_success_rate < one_shot.completion_success_rate
    assert one_shot.completion_success_rate == 1.0


def test_tiled_cluttered_forks_scale_to_32_agents_with_exact_density() -> None:
    instance = generate_tiled_cluttered_fork_instance(seed=0, obstacle_density=.2, map_size=64, num_agents=32)
    assert instance.num_agents == 32
    assert len(instance.starts) == 32
    assert instance.obstacle_density == round(.2 * 64 * 64) / (64 * 64)


def test_cluttered_density_and_scale_studies_use_unique_physical_layouts() -> None:
    for density in (.1, .2, .3, .4):
        assert len({
            generate_cluttered_multifork_instance(
                seed=seed, obstacle_density=density, observation_radius=2,
            ).layout_fingerprint()
            for seed in range(100)
        }) == 100
    for agents, size in ((4, 24), (8, 32), (16, 48), (32, 64)):
        assert len({
            generate_tiled_cluttered_fork_instance(
                seed=seed, obstacle_density=.2, map_size=size,
                num_agents=agents, observation_radius=2,
            ).layout_fingerprint()
            for seed in range(100)
        }) == 100


def _observed_truth(
    bitmap: np.ndarray, positions: tuple[tuple[int, int], ...], radius: int,
) -> np.ndarray:
    belief = np.zeros_like(bitmap)
    for row, column in positions:
        belief[
            max(0, row - radius):row + radius + 1,
            max(0, column - radius):column + radius + 1,
        ] = bitmap[
            max(0, row - radius):row + radius + 1,
            max(0, column - radius):column + radius + 1,
        ]
    return belief


def test_natural_critical_keeps_the_presampled_bitmap_bit_exact() -> None:
    instance = generate_natural_critical_instance(
        seed=7, map_size=32, obstacle_density=.2, num_agents=8,
        observation_radius=2, max_episode_steps=64,
        candidate_draws_per_attempt=40_000,
    )
    attempt = int(instance.package_metadata["selection_attempt"])
    raw_seed = natural_critical_raw_seed(7, attempt)
    presampled = sample_natural_occupancy_bitmap(
        raw_seed=raw_seed, map_size=32, obstacle_density=.2,
    )

    assert np.array_equal(instance.obstacle_map, presampled)
    assert instance.package_metadata["raw_bitmap_seed"] == str(raw_seed)
    assert instance.package_metadata["raw_bitmap_sha256"] == natural_bitmap_sha256(presampled)
    assert instance.package_metadata["post_selection_bitmap_sha256"] == natural_bitmap_sha256(presampled)
    assert instance.package_metadata["selection_contract"] == (
        "geometry_and_counterfactual_planning_only;no_policy;no_link;"
        "no_episode_outcome;bitmap_immutable"
    )
    assert isinstance(
        json.loads(instance.package_metadata["selection_rejection_counts"]), dict,
    )
    assert "fov_radius=2" in instance.package_metadata["pair_filter"]
    assert "seeker_truth_path=12..40" in instance.package_metadata["pair_filter"]
    assert int(instance.package_metadata["candidate_draws_used_total"]) > 0


def test_natural_critical_pairs_have_auditable_action_conflicts_and_long_routes() -> None:
    radius = 2
    instance = generate_natural_critical_instance(
        seed=0, map_size=32, obstacle_density=.2, num_agents=8,
        observation_radius=radius, max_episode_steps=64,
        candidate_draws_per_attempt=40_000,
    )
    planner = AStarPlanner()
    pairs = critical_decision_pairs(instance)
    diagnostics = json.loads(instance.package_metadata["natural_pair_diagnostics"])

    assert len(pairs) == 4
    assert len(set(instance.starts + instance.goals)) == 16
    for pair, diagnostic in zip(pairs, diagnostics):
        observer_start = instance.starts[pair.observer_id]
        observer_goal = instance.goals[pair.observer_id]
        seeker_start = instance.starts[pair.seeker_id]
        seeker_goal = instance.goals[pair.seeker_id]
        assert max(
            abs(observer_start[0] - pair.obstacle[0]),
            abs(observer_start[1] - pair.obstacle[1]),
        ) <= radius
        assert max(
            abs(seeker_start[0] - pair.obstacle[0]),
            abs(seeker_start[1] - pair.obstacle[1]),
        ) > radius
        observer_path = planner.plan(
            instance.obstacle_map, observer_start, observer_goal,
        ).path
        seeker_path = planner.plan(
            instance.obstacle_map, seeker_start, seeker_goal,
        ).path
        assert 8 <= len(observer_path) - 1 <= 16
        assert 12 <= len(seeker_path) - 1 <= 40
        assert len(observer_path) - 1 == diagnostic["observer_truth_path_steps"]
        assert len(seeker_path) - 1 == diagnostic["seeker_truth_path_steps"]

        divergence = int(diagnostic["divergence_step"])
        prefix = seeker_path[:divergence]
        assert prefix[-1] == pair.commitment
        assert diagnostic["commitment_step"] == divergence - 1
        assert diagnostic["zero_delay_communication_window_steps"] == divergence - 1
        for step in range(len(prefix) - 1):
            rolling_belief = _observed_truth(
                instance.obstacle_map, prefix[:step + 1], radius,
            )
            rolling_path = planner.plan(
                rolling_belief, prefix[step], seeker_goal,
            ).path
            assert rolling_path[1] == prefix[step + 1]
        belief = _observed_truth(instance.obstacle_map, prefix, radius)
        free_scenario, blocked_scenario = belief.copy(), belief.copy()
        free_scenario[pair.obstacle] = 0
        blocked_scenario[pair.obstacle] = 1
        free_path = planner.plan(
            free_scenario, pair.commitment, seeker_goal,
        ).path
        blocked_path = planner.plan(
            blocked_scenario, pair.commitment, seeker_goal,
        ).path
        assert free_path[1] != blocked_path[1]
        assert tuple(diagnostic["free_next"]) == free_path[1]
        assert tuple(diagnostic["blocked_next"]) == blocked_path[1]
        assert seeker_path[divergence] == blocked_path[1]


def test_natural_critical_supports_requested_scales_without_tiling() -> None:
    layouts = []
    for agents, size in ((2, 24), (4, 24), (8, 32), (16, 48), (32, 64)):
        instance = generate_natural_critical_instance(
            seed=0, map_size=size, obstacle_density=.2, num_agents=agents,
            observation_radius=2, max_episode_steps=64,
            candidate_draws_per_attempt=40_000,
        )
        layouts.append(instance.layout_fingerprint())
        assert instance.num_agents == agents
        assert len(critical_decision_pairs(instance)) == agents // 2
        assert len(set(instance.starts + instance.goals)) == 2 * agents
        assert instance.package_metadata["instance_family"] == "natural_critical_random"
        assert int(instance.package_metadata["raw_maps_examined"]) >= 1
        half = size // 2
        quadrants = {
            instance.obstacle_map[
                row * half:(row + 1) * half,
                column * half:(column + 1) * half,
            ].tobytes()
            for row in range(2) for column in range(2)
        }
        assert len(quadrants) == 4
    assert len(set(layouts)) == len(layouts)


def test_natural_critical_is_deterministic_and_structurally_varies_by_seed() -> None:
    instances = [generate_natural_critical_instance(
        seed=seed, map_size=32, obstacle_density=.2, num_agents=8,
        observation_radius=2, max_episode_steps=64,
        candidate_draws_per_attempt=40_000,
    ) for seed in range(4)]
    assert instances[0].fingerprint() == generate_natural_critical_instance(
        seed=0, map_size=32, obstacle_density=.2, num_agents=8,
        observation_radius=2, max_episode_steps=64,
        candidate_draws_per_attempt=40_000,
    ).fingerprint()
    assert len({instance.layout_fingerprint() for instance in instances}) == 4
    assert len({instance.starts + instance.goals for instance in instances}) == 4
    assert len({
        instance.package_metadata["critical_decision_pairs"]
        for instance in instances
    }) == 4
