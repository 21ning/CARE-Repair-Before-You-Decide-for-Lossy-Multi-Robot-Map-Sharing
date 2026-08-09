from __future__ import annotations

import numpy as np

from cmvr.env.instance import generate_instance, load_instance, save_instance
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
