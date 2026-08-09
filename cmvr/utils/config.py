"""Typed configuration for the deterministic full-map baseline harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ExperimentConfig:
    seed: int
    map_size: int
    obstacle_density: float
    num_agents: int
    observation_radius: int
    max_episode_steps: int
    planner: str = "astar"
    output_directory: str = "outputs"
    save_action_trace: bool = True
    save_instance: bool = True
    collision_system: str = "priority"

    def __post_init__(self) -> None:
        if self.planner != "astar":
            raise ValueError("Milestone A supports only planner='astar'")
        if self.map_size < 2:
            raise ValueError("map_size must be at least 2")
        if not 0.0 <= self.obstacle_density <= 1.0:
            raise ValueError("obstacle_density must be in [0, 1]")
        if self.num_agents < 1 or self.observation_radius < 1:
            raise ValueError("num_agents and observation_radius must be positive")
        if self.max_episode_steps < 1:
            raise ValueError("max_episode_steps must be positive")
        if self.collision_system not in {"priority", "block_both"}:
            raise ValueError("collision_system must be 'priority' or 'block_both'")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_config(path: str | Path) -> ExperimentConfig:
    source = Path(path)
    data = yaml.safe_load(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("configuration must contain a mapping")
    return ExperimentConfig(**data)


def save_resolved_config(config: ExperimentConfig, path: str | Path) -> None:
    Path(path).write_text(
        yaml.safe_dump(config.to_dict(), sort_keys=True), encoding="utf-8"
    )
