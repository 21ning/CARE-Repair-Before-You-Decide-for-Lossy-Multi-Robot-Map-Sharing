from __future__ import annotations

from cmvr.communication import LinkConfig
from cmvr.env import (
    PSRClosedLoopRunner, PSRConfig, ReplicaPolicy, generate_fork_bottleneck_instance,
    generate_multifork_bottleneck_instance, generate_multifork_topology_variant_instance,
    generate_rotated_multifork_bottleneck_instance, generate_cluttered_multifork_instance,
    generate_tiled_cluttered_fork_instance,
)


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
