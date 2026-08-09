"""Predefined fixed-goal bottleneck tasks for communication mechanism tests.

These instances are intentionally separate from random POGEMA maps.  They test
whether a remote observation can change a route choice *before* a robot reaches
the locally observable blockage; they are not a replacement for the random-map
robustness gate.
"""

from __future__ import annotations

from types import MappingProxyType

import numpy as np

from .instance import EpisodeInstance


def generate_fork_bottleneck_instance(
    *, seed: int, map_size: int = 16, observation_radius: int = 3,
    max_episode_steps: int = 25,
) -> EpisodeInstance:
    """Create a two-agent fork where a remote upper-branch blockage matters.

    The seeker has a locally visible fork but cannot see the upper-branch block
    before committing to the deterministic upper tie.  The observer starts on
    the far side of that block and can report its local 7×7 map immediately.
    `seed` selects one of three block columns and also remains part of the
    immutable instance fingerprint.
    """
    if map_size != 16:
        raise ValueError("the preregistered fork-bottleneck geometry requires a 16x16 map")
    if observation_radius != 3:
        raise ValueError("the preregistered fork-bottleneck geometry requires observation_radius=3")
    if max_episode_steps < 20:
        raise ValueError("fork-bottleneck episodes need at least 20 steps")

    obstacle_map = np.ones((map_size, map_size), dtype=np.uint8)
    _carve_fork(obstacle_map)
    block_column = 9 + (seed % 3)
    obstacle_map[4, block_column] = 1

    starts = ((4, block_column + 1), (8, 1))
    goals = ((4, block_column + 2), (8, 13))
    return EpisodeInstance(
        obstacle_map=obstacle_map,
        starts=starts,
        goals=goals,
        generation_seed=seed,
        map_size=map_size,
        obstacle_density=float(obstacle_map.mean()),
        observation_radius=observation_radius,
        max_episode_steps=max_episode_steps,
        num_agents=2,
        collision_system="priority",
        package_metadata=MappingProxyType({
            "instance_family": "fork_bottleneck_upper_block",
            "geometry_version": "1",
            "block_column": str(block_column),
        }),
    )


def generate_multifork_bottleneck_instance(
    *, seed: int, map_size: int = 32, observation_radius: int = 3,
    max_episode_steps: int = 25,
) -> EpisodeInstance:
    """Create four disjoint fork pairs in a 32×32 fixed-goal MAPF instance."""
    if map_size != 32:
        raise ValueError("the preregistered multi-fork geometry requires a 32x32 map")
    if observation_radius != 3:
        raise ValueError("the preregistered multi-fork geometry requires observation_radius=3")
    obstacle_map = np.ones((map_size, map_size), dtype=np.uint8)
    starts: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []
    for pair, (row_offset, column_offset) in enumerate(((0, 0), (0, 16), (16, 0), (16, 16))):
        tile = np.ones((16, 16), dtype=np.uint8)
        _carve_fork(tile)
        block_column = 9 + ((seed + pair) % 3)
        tile[4, block_column] = 1
        obstacle_map[row_offset:row_offset + 16, column_offset:column_offset + 16] = tile
        starts.extend(((row_offset + 4, column_offset + block_column + 1), (row_offset + 8, column_offset + 1)))
        goals.extend(((row_offset + 4, column_offset + block_column + 2), (row_offset + 8, column_offset + 13)))
    return EpisodeInstance(
        obstacle_map=obstacle_map, starts=tuple(starts), goals=tuple(goals), generation_seed=seed,
        map_size=map_size, obstacle_density=float(obstacle_map.mean()), observation_radius=observation_radius,
        max_episode_steps=max_episode_steps, num_agents=8, collision_system="priority",
        package_metadata=MappingProxyType({"instance_family": "multifork_bottleneck_upper_block", "geometry_version": "1", "pairs": "4"}),
    )


def generate_rotated_multifork_bottleneck_instance(
    *, seed: int, map_size: int = 32, observation_radius: int = 3,
    max_episode_steps: int = 25,
) -> EpisodeInstance:
    """Coordinate-rotated validation of the multi-fork family.

    This is a separate instance family so that it cannot change the previously
    frozen horizontal multi-fork results.
    """
    base = generate_multifork_bottleneck_instance(
        seed=seed, map_size=map_size, observation_radius=observation_radius,
        max_episode_steps=max_episode_steps,
    )
    return EpisodeInstance(
        obstacle_map=np.rot90(base.obstacle_map, 1).copy(),
        starts=tuple(_rotate_counterclockwise(point, map_size) for point in base.starts),
        goals=tuple(_rotate_counterclockwise(point, map_size) for point in base.goals),
        generation_seed=seed, map_size=map_size, obstacle_density=base.obstacle_density,
        observation_radius=observation_radius, max_episode_steps=max_episode_steps,
        num_agents=base.num_agents, collision_system=base.collision_system,
        package_metadata=MappingProxyType({"instance_family": "multifork_bottleneck_rotated", "geometry_version": "1", "pairs": "4"}),
    )


def generate_multifork_topology_variant_instance(
    *, topology: str, seed: int, map_size: int = 32, observation_radius: int = 3,
    max_episode_steps: int = 25,
) -> EpisodeInstance:
    """Create four matched decision-critical bottlenecks of a new topology.

    Each tile preserves the causal condition of the original fork family: an
    observer can see a blockage before its paired seeker can see it locally,
    and that blockage changes the seeker's imminent route choice.  The three
    variants deliberately alter the decision geometry, rather than merely
    rotating the original tile.
    """
    if map_size != 32:
        raise ValueError("multifork topology variants require a 32x32 map")
    if observation_radius < 1:
        raise ValueError("observation_radius must be positive")
    carvers = {
        "t_junction": _carve_t_junction,
        "asymmetric_fork": _carve_asymmetric_fork,
        "narrow_bypass": _carve_narrow_bypass,
    }
    try:
        carver = carvers[topology]
    except KeyError as error:
        raise ValueError(f"unsupported topology variant: {topology}") from error

    obstacle_map = np.ones((map_size, map_size), dtype=np.uint8)
    starts: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []
    critical_pairs: list[str] = []
    for pair, (row_offset, column_offset) in enumerate(((0, 0), (0, 16), (16, 0), (16, 16))):
        tile, observer_start, observer_goal, seeker_start, seeker_goal = carver(seed)
        _open_isolated_background_pockets(
            tile, seed=seed * 4 + pair, count=8,
        )
        obstacle_map[row_offset:row_offset + 16, column_offset:column_offset + 16] = tile
        starts.extend((
            (row_offset + observer_start[0], column_offset + observer_start[1]),
            (row_offset + seeker_start[0], column_offset + seeker_start[1]),
        ))
        goals.extend((
            (row_offset + observer_goal[0], column_offset + observer_goal[1]),
            (row_offset + seeker_goal[0], column_offset + seeker_goal[1]),
        ))
        if topology == "t_junction":
            obstacle, commitment = (8, 12), (8, 8)
        elif topology == "asymmetric_fork":
            obstacle, commitment = (4, 9 + (seed % 2)), (8, 5)
        else:
            obstacle, commitment = (5, 9 + (seed % 2)), (8, 5)
        critical_pairs.append(
            f"{2 * pair},{2 * pair + 1},"
            f"{row_offset + obstacle[0]},{column_offset + obstacle[1]},"
            f"{row_offset + commitment[0]},{column_offset + commitment[1]}"
        )
    return EpisodeInstance(
        obstacle_map=obstacle_map, starts=tuple(starts), goals=tuple(goals), generation_seed=seed,
        map_size=map_size, obstacle_density=float(obstacle_map.mean()), observation_radius=observation_radius,
        max_episode_steps=max_episode_steps, num_agents=8, collision_system="priority",
        package_metadata=MappingProxyType({
            "instance_family": f"multifork_{topology}", "geometry_version": "1", "pairs": "4",
            "critical_decision_pairs": ";".join(critical_pairs),
        }),
    )


def generate_cluttered_multifork_instance(
    *, seed: int, obstacle_density: float, map_size: int = 32, num_agents: int = 8,
    observation_radius: int = 3, max_episode_steps: int = 25,
) -> EpisodeInstance:
    """Decision-critical wall crossings with exact non-critical background clutter.

    The protected cells encode two routes per seeker and the remote-blockage
    timing. Random obstacles are sampled only outside that protected geometry,
    so the requested *total* obstacle density cannot destroy the causal task.
    """
    if not 0.0 < obstacle_density < 1.0:
        raise ValueError("obstacle_density must be in (0, 1)")
    if num_agents % 2 or num_agents < 4:
        raise ValueError("cluttered multifork requires an even number of at least four agents")
    pairs = num_agents // 2
    if map_size % pairs or map_size // pairs < 4:
        raise ValueError("map must provide at least four columns per observer-seeker pair")
    barrier = map_size // 2
    if barrier < 8 or barrier + 7 >= map_size or barrier - 7 < 0:
        raise ValueError("map is too small for the decision-critical timing geometry")

    obstacle_map = np.zeros((map_size, map_size), dtype=np.uint8)
    fixed_obstacles: set[tuple[int, int]] = {(barrier, column) for column in range(map_size)}
    protected_free: set[tuple[int, int]] = set()
    starts: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []
    critical_pairs: list[str] = []
    slot_width = map_size // pairs
    for pair in range(pairs):
        left = pair * slot_width
        primary = left + 1
        alternate = left + slot_width - 2
        branch = barrier + 5
        start = (barrier + 7, primary)
        goal = (barrier - 7, primary)
        observer_start = (barrier - 1, min(primary + 1, left + slot_width - 1))
        observer_goal = (barrier - 2, min(primary + 1, left + slot_width - 1))
        starts.extend((observer_start, start)); goals.extend((observer_goal, goal))
        observer_id = 2 * pair
        critical_pairs.append(
            f"{observer_id},{observer_id + 1},{barrier},{primary},{branch},{primary}"
        )
        # The alternate crossing and the two routes are never cluttered.
        protected_free.update((row, primary) for row in range(barrier + 1, barrier + 8))
        protected_free.update((branch, column) for column in range(min(primary, alternate), max(primary, alternate) + 1))
        protected_free.update((row, alternate) for row in range(barrier - 7, branch + 1))
        protected_free.update((barrier - 7, column) for column in range(min(primary, alternate), max(primary, alternate) + 1))
        protected_free.update({observer_start, observer_goal, (barrier, alternate)})
        # A short primary lane forces an early route choice before local sensing
        # can reveal its blocked wall crossing.
        for row in range(barrier + 1, branch):
            for column in (primary - 1, primary + 1):
                if left <= column < left + slot_width:
                    fixed_obstacles.add((row, column))
        fixed_obstacles.add((barrier, primary))

    for cell in protected_free:
        fixed_obstacles.discard(cell)
    for row, column in fixed_obstacles:
        obstacle_map[row, column] = 1
    target_obstacles = round(obstacle_density * map_size * map_size)
    candidates = [
        (row, column) for row in range(map_size) for column in range(map_size)
        if (row, column) not in fixed_obstacles and (row, column) not in protected_free
    ]
    extra = target_obstacles - len(fixed_obstacles)
    if extra < 0 or extra > len(candidates):
        raise ValueError("requested density is incompatible with protected critical geometry")
    rng = np.random.default_rng(seed)
    for index in rng.choice(len(candidates), size=extra, replace=False):
        obstacle_map[candidates[int(index)]] = 1
    return EpisodeInstance(
        obstacle_map=obstacle_map, starts=tuple(starts), goals=tuple(goals), generation_seed=seed,
        map_size=map_size, obstacle_density=float(obstacle_map.mean()), observation_radius=observation_radius,
        max_episode_steps=max_episode_steps, num_agents=num_agents, collision_system="priority",
        package_metadata=MappingProxyType({
            "instance_family": "multifork_cluttered", "geometry_version": "1", "pairs": str(pairs),
            "background_clutter_seed": str(seed), "target_obstacle_density": str(obstacle_density),
            "critical_decision_pairs": ";".join(critical_pairs),
        }),
    )


def generate_tiled_cluttered_fork_instance(
    *, seed: int, obstacle_density: float, map_size: int, num_agents: int,
    observation_radius: int = 3, max_episode_steps: int = 25,
) -> EpisodeInstance:
    """Scale a causal observer--seeker task by tiling independent fork cells.

    Unlike a single global barrier with ever-narrower slots, every pair keeps
    an 12x12-or-larger decision cell.  This preserves two protected routes at
    32 agents on 64x64 while background clutter is sampled only outside those
    routes.
    """
    if num_agents % 2 or num_agents < 4:
        raise ValueError("tiled cluttered forks require an even number of at least four agents")
    pairs = num_agents // 2
    grid = int(np.ceil(np.sqrt(pairs)))
    if map_size % grid:
        raise ValueError("map_size must divide the tiled scale grid")
    tile_size = map_size // grid
    if tile_size < 12:
        raise ValueError("each tiled causal fork needs at least 12x12 cells")
    obstacle_map = np.zeros((map_size, map_size), dtype=np.uint8)
    fixed_obstacles: set[tuple[int, int]] = set()
    protected_free: set[tuple[int, int]] = set()
    starts: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []
    barrier = tile_size // 2
    margin = min(5, barrier - 1)
    for pair in range(pairs):
        tile_row, tile_column = divmod(pair, grid)
        top, left = tile_row * tile_size, tile_column * tile_size
        primary, alternate = 1, tile_size - 2
        branch = barrier + margin - 2
        start, goal = (barrier + margin, primary), (barrier - margin, primary)
        observer_start, observer_goal = (barrier - 1, primary + 1), (barrier - 2, primary + 1)
        starts.extend(((top + observer_start[0], left + observer_start[1]), (top + start[0], left + start[1])))
        goals.extend(((top + observer_goal[0], left + observer_goal[1]), (top + goal[0], left + goal[1])))
        for column in range(tile_size):
            fixed_obstacles.add((top + barrier, left + column))
        protected_free.update((top + row, left + primary) for row in range(barrier + 1, barrier + margin + 1))
        protected_free.update((top + branch, left + column) for column in range(primary, alternate + 1))
        protected_free.update((top + row, left + alternate) for row in range(barrier - margin, branch + 1))
        protected_free.update((top + barrier - margin, left + column) for column in range(primary, alternate + 1))
        protected_free.update({(top + barrier, left + alternate), (top + observer_start[0], left + observer_start[1]), (top + observer_goal[0], left + observer_goal[1])})
        for row in range(barrier + 1, branch):
            for column in (primary - 1, primary + 1):
                if 0 <= column < tile_size:
                    fixed_obstacles.add((top + row, left + column))
        fixed_obstacles.add((top + barrier, left + primary))
    for cell in protected_free:
        fixed_obstacles.discard(cell)
    for row, column in fixed_obstacles:
        obstacle_map[row, column] = 1
    target = round(obstacle_density * map_size * map_size)
    candidates = [(row, column) for row in range(map_size) for column in range(map_size)
                  if (row, column) not in fixed_obstacles and (row, column) not in protected_free]
    extra = target - len(fixed_obstacles)
    if extra < 0 or extra > len(candidates):
        raise ValueError("requested density is incompatible with tiled protected geometry")
    rng = np.random.default_rng(seed)
    for index in rng.choice(len(candidates), size=extra, replace=False):
        obstacle_map[candidates[int(index)]] = 1
    return EpisodeInstance(
        obstacle_map=obstacle_map, starts=tuple(starts), goals=tuple(goals), generation_seed=seed,
        map_size=map_size, obstacle_density=float(obstacle_map.mean()), observation_radius=observation_radius,
        max_episode_steps=max_episode_steps, num_agents=num_agents, collision_system="priority",
        package_metadata=MappingProxyType({"instance_family": "tiled_cluttered_fork", "geometry_version": "1", "pairs": str(pairs), "background_clutter_seed": str(seed)}),
    )


def _carve_fork(obstacle_map: np.ndarray) -> None:
    """Carve two symmetric, one-cell-wide routes from the fork to the goal."""
    for column in range(1, 6):
        obstacle_map[8, column] = 0
    for row in range(4, 9):
        obstacle_map[row, 5] = 0
        obstacle_map[row, 13] = 0
    for column in range(5, 14):
        obstacle_map[4, column] = 0
    for row in range(8, 13):
        obstacle_map[row, 5] = 0
        obstacle_map[row, 13] = 0
    for column in range(5, 14):
        obstacle_map[12, column] = 0


def _empty_tile() -> np.ndarray:
    return np.ones((16, 16), dtype=np.uint8)


def _open_isolated_background_pockets(
    tile: np.ndarray, *, seed: int, count: int,
) -> None:
    """Add seeded map diversity without changing the decision-route graph."""
    route = {tuple(map(int, cell)) for cell in np.argwhere(tile == 0)}
    candidates = [
        (row, column)
        for row in range(1, tile.shape[0] - 1)
        for column in range(1, tile.shape[1] - 1)
        if int(tile[row, column]) == 1
        and all(
            (row + delta_row, column + delta_column) not in route
            for delta_row, delta_column in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
        )
    ]
    rng = np.random.default_rng(seed)
    selected: list[tuple[int, int]] = []
    for candidate_index in rng.permutation(len(candidates)):
        candidate = candidates[int(candidate_index)]
        if any(
            abs(candidate[0] - other[0]) + abs(candidate[1] - other[1]) <= 1
            for other in selected
        ):
            continue
        selected.append(candidate)
        if len(selected) == count:
            break
    if len(selected) != count:
        raise RuntimeError("could not place the requested isolated background pockets")
    for cell in selected:
        tile[cell] = 0


def _carve_t_junction(seed: int) -> tuple[np.ndarray, tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:
    """A vertical approach to a T whose shorter arm contains a remote block."""
    tile = _empty_tile()
    for row in range(8, 15):
        tile[row, 8] = 0
    for column in range(3, 14):
        tile[8, column] = 0
    for row in range(4, 9):
        tile[row, 3] = 0
    for column in range(3, 14):
        tile[4, column] = 0
    for row in range(4, 9):
        tile[row, 13] = 0
    tile[8, 14] = 0
    tile[8, 12] = 1
    return tile, (8, 13), (8, 14), (14, 8), (4, 13)


def _carve_asymmetric_fork(seed: int) -> tuple[np.ndarray, tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:
    """A Y-like asymmetric split: a short blocked arm and a longer bypass."""
    tile = _empty_tile()
    for column in range(1, 6):
        tile[8, column] = 0
    for row in range(4, 12):
        tile[row, 5] = 0
        tile[row, 13] = 0
    for column in range(5, 14):
        tile[4, column] = 0
        tile[11, column] = 0
    block_column = 9 + (seed % 2)
    tile[4, block_column] = 1
    return tile, (4, block_column + 1), (4, block_column + 2), (8, 1), (4, 13)


def _carve_narrow_bypass(seed: int) -> tuple[np.ndarray, tuple[int, int], tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Two one-cell corridors where only the longer bypass avoids the block."""
    tile = _empty_tile()
    for column in range(1, 6):
        tile[8, column] = 0
    for row in range(5, 13):
        tile[row, 5] = 0
        tile[row, 13] = 0
    for column in range(5, 14):
        tile[5, column] = 0
        tile[12, column] = 0
    block_column = 9 + (seed % 2)
    tile[5, block_column] = 1
    return tile, (5, block_column + 1), (5, block_column + 2), (8, 1), (5, 13)


def _rotate_counterclockwise(point: tuple[int, int], size: int) -> tuple[int, int]:
    row, column = point
    return size - 1 - column, row
