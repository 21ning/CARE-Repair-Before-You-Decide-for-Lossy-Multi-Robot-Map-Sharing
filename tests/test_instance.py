from __future__ import annotations

import numpy as np

from cmvr.env.instance import critical_decision_pairs, generate_instance, load_instance, save_instance
from cmvr.env.structured_instances import generate_cluttered_multifork_instance
from cmvr.utils.config import ExperimentConfig


def _config(seed: int) -> ExperimentConfig:
    return ExperimentConfig(
        seed=seed,
        map_size=12,
        obstacle_density=0.1,
        num_agents=3,
        observation_radius=3,
        max_episode_steps=48,
    )


def test_same_seed_recreates_same_instance() -> None:
    first = generate_instance(_config(23))
    second = generate_instance(_config(23))
    assert first.fingerprint() == second.fingerprint()
    assert np.array_equal(first.obstacle_map, second.obstacle_map)
    assert first.starts == second.starts
    assert first.goals == second.goals


def test_different_seeds_produce_different_instance() -> None:
    assert generate_instance(_config(23)).fingerprint() != generate_instance(_config(24)).fingerprint()


def test_save_load_preserves_instance_fingerprint(tmp_path) -> None:
    instance = generate_instance(_config(25))
    save_instance(instance, tmp_path)
    restored = load_instance(tmp_path)
    assert restored.fingerprint() == instance.fingerprint()
    assert np.array_equal(restored.obstacle_map, instance.obstacle_map)
    assert restored.starts == instance.starts
    assert restored.goals == instance.goals


def test_layout_fingerprint_excludes_sensor_radius_and_critical_pairs_are_valid() -> None:
    instances = tuple(generate_cluttered_multifork_instance(
        seed=9, obstacle_density=.2, observation_radius=radius,
    ) for radius in (1, 2, 3))
    assert len({instance.layout_fingerprint() for instance in instances}) == 1
    assert len({instance.fingerprint() for instance in instances}) == 3
    pairs = critical_decision_pairs(instances[1])
    assert len(pairs) == 4
    assert {pair.observer_id for pair in pairs} == {0, 2, 4, 6}
    assert {pair.seeker_id for pair in pairs} == {1, 3, 5, 7}
    assert all(instances[1].obstacle_map[pair.obstacle] == 1 for pair in pairs)


def test_layout_fingerprint_detects_duplicate_geometry_despite_seed_label() -> None:
    first = generate_cluttered_multifork_instance(seed=4, obstacle_density=.2)
    relabeled = first.__class__(
        obstacle_map=first.obstacle_map.copy(), starts=first.starts, goals=first.goals,
        generation_seed=999, map_size=first.map_size,
        obstacle_density=first.obstacle_density,
        observation_radius=first.observation_radius,
        max_episode_steps=first.max_episode_steps, num_agents=first.num_agents,
        collision_system=first.collision_system, package_metadata=first.package_metadata,
    )
    assert first.fingerprint() != relabeled.fingerprint()
    assert first.layout_fingerprint() == relabeled.layout_fingerprint()
