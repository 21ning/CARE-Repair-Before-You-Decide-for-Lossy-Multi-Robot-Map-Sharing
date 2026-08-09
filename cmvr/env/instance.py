"""Immutable, serializable POGEMA episode instances."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence, Tuple

import numpy as np
from pogema import GridConfig, pogema_v0

from cmvr.utils.config import ExperimentConfig
from cmvr.utils.seeding import seed_everything

Coordinate = Tuple[int, int]


def _pogema_metadata() -> Mapping[str, str]:
    try:
        package_version = version("pogema")
    except PackageNotFoundError:
        package_version = "unavailable"
    return MappingProxyType({"pogema_version": package_version})


@dataclass(frozen=True)
class EpisodeInstance:
    """A fixed static MAPF task, independent of a later execution policy."""

    obstacle_map: np.ndarray
    starts: Tuple[Coordinate, ...]
    goals: Tuple[Coordinate, ...]
    generation_seed: int
    map_size: int
    obstacle_density: float
    observation_radius: int
    max_episode_steps: int
    num_agents: int
    collision_system: str = "priority"
    package_metadata: Mapping[str, str] = field(default_factory=_pogema_metadata)

    def __post_init__(self) -> None:
        obstacle_map = np.asarray(self.obstacle_map, dtype=np.uint8).copy()
        if obstacle_map.shape != (self.map_size, self.map_size):
            raise ValueError("obstacle_map shape must match map_size")
        if len(self.starts) != self.num_agents or len(self.goals) != self.num_agents:
            raise ValueError("starts and goals must match num_agents")
        if not 0.0 <= self.obstacle_density <= 1.0:
            raise ValueError("obstacle_density must be in [0, 1]")
        if self.collision_system not in {"priority", "block_both"}:
            raise ValueError("unsupported collision_system")
        obstacle_map.setflags(write=False)
        object.__setattr__(self, "obstacle_map", obstacle_map)
        object.__setattr__(self, "starts", tuple(tuple(map(int, p)) for p in self.starts))
        object.__setattr__(self, "goals", tuple(tuple(map(int, p)) for p in self.goals))
        object.__setattr__(self, "package_metadata", MappingProxyType(dict(self.package_metadata)))

    def fingerprint(self) -> str:
        """Return a version-independent hash of task-defining data."""
        digest = sha256()
        digest.update(b"cmvr-episode-instance-v1\0")
        digest.update(np.asarray(self.obstacle_map, dtype=np.uint8).tobytes(order="C"))
        canonical = json.dumps(
            {
                "generation_seed": self.generation_seed,
                "map_size": self.map_size,
                "obstacle_density": self.obstacle_density,
                "observation_radius": self.observation_radius,
                "max_episode_steps": self.max_episode_steps,
                "num_agents": self.num_agents,
                "collision_system": self.collision_system,
                "starts": self.starts,
                "goals": self.goals,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        digest.update(canonical)
        return digest.hexdigest()

    def metadata_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generation_seed": self.generation_seed,
            "map_size": self.map_size,
            "obstacle_density": self.obstacle_density,
            "observation_radius": self.observation_radius,
            "max_episode_steps": self.max_episode_steps,
            "num_agents": self.num_agents,
            "collision_system": self.collision_system,
            "starts": [list(p) for p in self.starts],
            "goals": [list(p) for p in self.goals],
            "package_metadata": dict(self.package_metadata),
            "fingerprint": self.fingerprint(),
        }


def generate_instance(config: ExperimentConfig) -> EpisodeInstance:
    """Generate one fixed POGEMA task and extract its interior coordinates."""
    seed_everything(config.seed)
    grid_config = GridConfig(
        seed=config.seed,
        size=config.map_size,
        density=config.obstacle_density,
        num_agents=config.num_agents,
        collision_system=config.collision_system,
        obs_radius=config.observation_radius,
        max_episode_steps=config.max_episode_steps,
    )
    environment = pogema_v0(grid_config=grid_config)
    environment.reset()
    obstacle_map = environment.grid.get_obstacles(ignore_borders=True)
    starts = tuple(
        tuple(map(int, position))
        for position in environment.grid.get_agents_xy(ignore_borders=True)
    )
    goals = tuple(
        tuple(map(int, position))
        for position in environment.grid.get_targets_xy(ignore_borders=True)
    )
    return EpisodeInstance(
        obstacle_map=obstacle_map,
        starts=starts,
        goals=goals,
        generation_seed=config.seed,
        map_size=config.map_size,
        obstacle_density=config.obstacle_density,
        observation_radius=config.observation_radius,
        max_episode_steps=config.max_episode_steps,
        num_agents=config.num_agents,
        collision_system=config.collision_system,
    )


def save_instance(instance: EpisodeInstance, path: str | Path) -> tuple[Path, Path]:
    """Save JSON metadata and compressed map data; return their paths."""
    target = Path(path)
    if target.suffix:
        npz_path = target.with_suffix(".npz")
        json_path = target.with_suffix(".json")
    else:
        target.mkdir(parents=True, exist_ok=True)
        npz_path = target / "instance.npz"
        json_path = target / "instance.json"
    npz_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(npz_path, obstacle_map=instance.obstacle_map)
    json_path.write_text(
        json.dumps(instance.metadata_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return json_path, npz_path


def load_instance(path: str | Path) -> EpisodeInstance:
    """Load an instance saved by :func:`save_instance` and verify its hash."""
    source = Path(path)
    if source.is_dir():
        json_path, npz_path = source / "instance.json", source / "instance.npz"
    elif source.suffix == ".json":
        json_path, npz_path = source, source.with_suffix(".npz")
    elif source.suffix == ".npz":
        npz_path, json_path = source, source.with_suffix(".json")
    else:
        raise ValueError("instance path must be a directory, .json, or .npz")
    metadata = json.loads(json_path.read_text(encoding="utf-8"))
    with np.load(npz_path, allow_pickle=False) as arrays:
        obstacle_map = arrays["obstacle_map"]
    instance = EpisodeInstance(
        obstacle_map=obstacle_map,
        starts=tuple(tuple(p) for p in metadata["starts"]),
        goals=tuple(tuple(p) for p in metadata["goals"]),
        generation_seed=int(metadata["generation_seed"]),
        map_size=int(metadata["map_size"]),
        obstacle_density=float(metadata["obstacle_density"]),
        observation_radius=int(metadata["observation_radius"]),
        max_episode_steps=int(metadata["max_episode_steps"]),
        num_agents=int(metadata["num_agents"]),
        collision_system=str(metadata.get("collision_system", "priority")),
        package_metadata=metadata.get("package_metadata", {}),
    )
    if instance.fingerprint() != metadata["fingerprint"]:
        raise ValueError("instance fingerprint mismatch: files are inconsistent")
    return instance
