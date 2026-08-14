"""Natural decision-critical tasks selected from untouched random maps.

The structured benchmark in :mod:`cmvr.env.structured_instances` protects a
hand-designed route graph before adding clutter.  This module provides a
deliberately different external-validity family.  It first samples an entire
Bernoulli occupancy bitmap and never changes a cell afterwards.  Starts, goals,
and observer--seeker landmarks are then selected only when the sampled graph
already contains the required action conflict.

Selection uses map geometry and deterministic counterfactual planning only.  It
does not execute a communication policy, inspect a loss trace, or condition on
episode success.  The accepted raw seed, untouched-bitmap digest, rejection
counts, and pair diagnostics are stored in ``package_metadata`` so that the
conditioning procedure remains auditable.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Iterable

import numpy as np

from cmvr.planning import AStarPlanner

from .instance import EpisodeInstance


Coordinate = tuple[int, int]
_NEIGHBOURS: tuple[Coordinate, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))
_GENERATOR_VERSION = "natural-critical-v1"


@dataclass(frozen=True)
class _PairCandidate:
    seeker_start: Coordinate
    seeker_goal: Coordinate
    obstacle: Coordinate
    commitment: Coordinate
    divergence_step: int
    free_next: Coordinate
    blocked_next: Coordinate
    seeker_truth_path: tuple[Coordinate, ...]
    observer_starts: tuple[Coordinate, ...]
    score: str


@dataclass(frozen=True)
class _SelectedPair:
    observer_start: Coordinate
    observer_goal: Coordinate
    observer_truth_path: tuple[Coordinate, ...]
    candidate: _PairCandidate


def natural_critical_raw_seed(seed: int, attempt: int) -> int:
    """Derive the auditable raw-map seed for one deterministic acceptance try."""
    if seed < 0 or attempt < 0:
        raise ValueError("seed and attempt must be non-negative")
    material = f"{_GENERATOR_VERSION}|{seed}|{attempt}".encode("utf-8")
    return int.from_bytes(sha256(material).digest()[:8], "big") % (2**63 - 1)


def sample_natural_occupancy_bitmap(
    *, raw_seed: int, map_size: int, obstacle_density: float,
) -> np.ndarray:
    """Sample the raw Bernoulli map used by the natural-critical selector.

    This function is public specifically so an audit can reproduce the bitmap
    from metadata and verify that critical-task construction did not rewrite it.
    """
    if raw_seed < 0:
        raise ValueError("raw_seed must be non-negative")
    if map_size < 2:
        raise ValueError("map_size must be at least two")
    if not 0.0 < obstacle_density < 1.0:
        raise ValueError("obstacle_density must be in (0, 1)")
    rng = np.random.default_rng(raw_seed)
    return (rng.random((map_size, map_size)) < obstacle_density).astype(np.uint8)


def natural_bitmap_sha256(bitmap: np.ndarray) -> str:
    """Return the canonical digest recorded before and after pair selection."""
    array = np.asarray(bitmap, dtype=np.uint8)
    digest = sha256()
    digest.update(b"care-natural-occupancy-v1\0")
    digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def generate_natural_critical_instance(
    *, seed: int, map_size: int, obstacle_density: float, num_agents: int,
    observation_radius: int = 2, max_episode_steps: int = 64,
    corridor_horizon: int = 8, max_raw_attempts: int = 128,
    candidate_draws_per_attempt: int | None = None,
) -> EpisodeInstance:
    """Select observer--seeker conflicts already present in random occupancy.

    Supported agent counts are 2/4/8/16.  Thirty-two agents are also accepted
    on a 64x64-or-larger map, but are intentionally not required by the frozen
    external-validity design because the canonical wire codec caps maps at 64.

    A seeker candidate must have a 12--40 step truth-map path.  In the map known
    after accumulating local observations along its common path prefix, setting
    one still-hidden natural obstacle FREE versus BLOCKED must change the next
    action at a commitment no later than ``corridor_horizon``.  The truth-map
    action must agree with the BLOCKED scenario.  Its observer sees the obstacle
    at time zero and receives a distinct truth-map goal 8--16 steps away.
    """
    _validate_parameters(
        seed=seed, map_size=map_size, obstacle_density=obstacle_density,
        num_agents=num_agents, observation_radius=observation_radius,
        max_episode_steps=max_episode_steps, corridor_horizon=corridor_horizon,
        max_raw_attempts=max_raw_attempts,
    )
    pair_count = num_agents // 2
    draws = candidate_draws_per_attempt
    if draws is None:
        draws = max(60_000, min(180_000, 24_000 * pair_count))
    if draws < 1:
        raise ValueError("candidate_draws_per_attempt must be positive")

    aggregate_rejections: defaultdict[str, int] = defaultdict(int)
    for attempt in range(max_raw_attempts):
        raw_seed = natural_critical_raw_seed(seed, attempt)
        bitmap = sample_natural_occupancy_bitmap(
            raw_seed=raw_seed, map_size=map_size,
            obstacle_density=obstacle_density,
        )
        before_digest = natural_bitmap_sha256(bitmap)
        candidates, selected, rejection_counts = _select_natural_pairs(
            bitmap, raw_seed=raw_seed, pair_count=pair_count,
            observation_radius=observation_radius,
            corridor_horizon=corridor_horizon, candidate_draws=draws,
        )
        for reason, count in rejection_counts.items():
            aggregate_rejections[reason] += count
        if len(selected) != pair_count:
            aggregate_rejections["raw_map_insufficient_disjoint_pairs"] += 1
            continue
        after_digest = natural_bitmap_sha256(bitmap)
        if after_digest != before_digest:  # defensive proof obligation
            raise RuntimeError("natural-critical selection modified the raw bitmap")
        return _build_instance(
            bitmap=bitmap, seed=seed, raw_seed=raw_seed, attempt=attempt,
            target_density=obstacle_density, observation_radius=observation_radius,
            max_episode_steps=max_episode_steps, corridor_horizon=corridor_horizon,
            candidates_examined=len(candidates), selected=selected,
            candidate_draws_per_attempt=draws,
            rejection_counts=dict(sorted(aggregate_rejections.items())),
            bitmap_digest=before_digest,
        )
    raise RuntimeError(
        "could not find enough disjoint natural decision conflicts in "
        f"{max_raw_attempts} untouched random maps; "
        f"rejections={dict(sorted(aggregate_rejections.items()))}"
    )


def _validate_parameters(
    *, seed: int, map_size: int, obstacle_density: float, num_agents: int,
    observation_radius: int, max_episode_steps: int, corridor_horizon: int,
    max_raw_attempts: int,
) -> None:
    if seed < 0:
        raise ValueError("seed must be non-negative")
    if num_agents not in {2, 4, 8, 16, 32}:
        raise ValueError("natural-critical instances support 2/4/8/16/32 agents")
    minimum_sizes = {2: 24, 4: 24, 8: 32, 16: 48, 32: 64}
    if map_size < minimum_sizes[num_agents]:
        raise ValueError(
            f"{num_agents} natural-critical agents require map_size >= "
            f"{minimum_sizes[num_agents]}"
        )
    if not 0.0 < obstacle_density < 1.0:
        raise ValueError("obstacle_density must be in (0, 1)")
    if observation_radius < 1:
        raise ValueError("observation_radius must be positive")
    if corridor_horizon < observation_radius + 2:
        raise ValueError("corridor_horizon is too short for a hidden commitment")
    if max_episode_steps < 40:
        raise ValueError("natural-critical episodes require at least 40 steps")
    if max_raw_attempts < 1:
        raise ValueError("max_raw_attempts must be positive")


def _select_natural_pairs(
    bitmap: np.ndarray, *, raw_seed: int, pair_count: int,
    observation_radius: int, corridor_horizon: int, candidate_draws: int,
) -> tuple[list[_PairCandidate], list[_SelectedPair], dict[str, int]]:
    free_cells = tuple(tuple(map(int, cell)) for cell in np.argwhere(bitmap == 0))
    rejections: defaultdict[str, int] = defaultdict(int)
    if len(free_cells) < 4 * pair_count or not bool(np.any(bitmap == 1)):
        rejections["insufficient_free_or_blocked_cells"] += 1
        return [], [], dict(rejections)

    planner = AStarPlanner()
    rng_seed = int.from_bytes(
        sha256(f"candidate-draws|{raw_seed}".encode()).digest()[:8], "big"
    )
    rng = np.random.default_rng(rng_seed)
    candidates: list[_PairCandidate] = []
    seen: set[tuple[Coordinate, Coordinate]] = set()
    selected: list[_SelectedPair] = []
    for draw in range(candidate_draws):
        seeker_start = free_cells[int(rng.integers(len(free_cells)))]
        seeker_goal = free_cells[int(rng.integers(len(free_cells)))]
        key = seeker_start, seeker_goal
        if key in seen:
            rejections["duplicate_draw"] += 1
            continue
        seen.add(key)
        candidate = _candidate_from_draw(
            bitmap, planner=planner, raw_seed=raw_seed, draw=draw,
            seeker_start=seeker_start, seeker_goal=seeker_goal,
            observation_radius=observation_radius,
            corridor_horizon=corridor_horizon, rejections=rejections,
        )
        if candidate is None:
            continue
        candidates.append(candidate)
        selected = _pack_candidates(
            bitmap, candidates, raw_seed=raw_seed, pair_count=pair_count,
            observation_radius=observation_radius,
        )
        if len(selected) == pair_count:
            rejections["candidate_draws_unused_after_success"] += candidate_draws - draw - 1
            break
    if len(selected) != pair_count:
        rejections["set_packing_shortfall"] += pair_count - len(selected)
    return candidates, selected, dict(sorted(rejections.items()))


def _candidate_from_draw(
    bitmap: np.ndarray, *, planner: AStarPlanner, raw_seed: int, draw: int,
    seeker_start: Coordinate, seeker_goal: Coordinate,
    observation_radius: int, corridor_horizon: int,
    rejections: defaultdict[str, int],
) -> _PairCandidate | None:
    seeker_goal_distance = _manhattan(seeker_start, seeker_goal)
    if not 10 <= seeker_goal_distance <= 40:
        rejections["distance_prefilter"] += 1
        return None

    initial_belief = _observed_map(bitmap, (seeker_start,), observation_radius)
    # Plan once on the seeker's optimistic local map, then inspect only natural
    # blocked cells already lying on that route.  This raises selector efficiency
    # without manufacturing an obstacle or targeting a policy outcome.
    free_path = planner.plan(initial_belief, seeker_start, seeker_goal).path
    if not free_path:
        rejections["initial_scenario_not_plannable"] += 1
        return None
    last_candidate_index = min(
        len(free_path), corridor_horizon + observation_radius + 3,
    )
    natural_obstacles = tuple(
        cell for cell in free_path[observation_radius + 1:last_candidate_index]
        if int(bitmap[cell]) == 1
    )
    if not natural_obstacles:
        rejections["no_natural_block_on_optimistic_route"] += 1
        return None

    truth_path: tuple[Coordinate, ...] | None = None
    for obstacle in natural_obstacles:
        if _chebyshev(seeker_start, obstacle) <= observation_radius:
            rejections["obstacle_initially_visible"] += 1
            continue
        blocked_scenario = initial_belief.copy()
        blocked_scenario[obstacle] = 1
        blocked_path = planner.plan(
            blocked_scenario, seeker_start, seeker_goal,
        ).path
        divergence = _first_divergence(free_path, blocked_path)
        if divergence is None or not 2 <= divergence <= corridor_horizon:
            rejections["divergence_outside_window"] += 1
            continue
        prefix = free_path[:divergence]
        if any(int(bitmap[cell]) for cell in prefix):
            rejections["common_prefix_not_truth_free"] += 1
            continue
        if any(
            _chebyshev(position, obstacle) <= observation_radius
            for position in prefix
        ):
            rejections["obstacle_visible_before_commitment"] += 1
            continue

        commitment = prefix[-1]
        commitment_belief = _observed_map(bitmap, prefix, observation_radius)
        commitment_free = commitment_belief.copy()
        commitment_blocked = commitment_belief.copy()
        commitment_free[obstacle] = 0
        commitment_blocked[obstacle] = 1
        free_commit_path = planner.plan(
            commitment_free, commitment, seeker_goal,
        ).path
        blocked_commit_path = planner.plan(
            commitment_blocked, commitment, seeker_goal,
        ).path
        if (
            len(free_commit_path) < 2 or len(blocked_commit_path) < 2
            or free_commit_path[1] == blocked_commit_path[1]
        ):
            rejections["no_action_conflict_at_commitment"] += 1
            continue

        if truth_path is None:
            truth_path = planner.plan(bitmap, seeker_start, seeker_goal).path
        if not 12 <= len(truth_path) - 1 <= 40:
            rejections["seeker_truth_path_outside_12_40"] += 1
            continue
        if (
            len(truth_path) <= divergence
            or truth_path[:divergence] != prefix
            or truth_path[divergence] != blocked_commit_path[1]
        ):
            rejections["truth_does_not_validate_blocked_action"] += 1
            continue
        if not _dynamic_prefix_is_consistent(
            bitmap, planner=planner, prefix=prefix, goal=seeker_goal,
            observation_radius=observation_radius,
        ):
            rejections["dynamic_prefix_inconsistent"] += 1
            continue

        reserved = set(prefix) | {
            seeker_start, seeker_goal, obstacle, commitment,
            free_commit_path[1], blocked_commit_path[1],
        }
        observer_starts = tuple(sorted(
            (
                cell for cell in _square_cells(bitmap.shape, obstacle, observation_radius)
                if int(bitmap[cell]) == 0 and cell not in reserved
            ),
            key=lambda cell: _score(raw_seed, draw, "observer-start", cell),
        ))
        if not observer_starts:
            rejections["no_observer_start"] += 1
            continue
        return _PairCandidate(
            seeker_start=seeker_start, seeker_goal=seeker_goal,
            obstacle=obstacle, commitment=commitment,
            divergence_step=divergence,
            free_next=free_commit_path[1], blocked_next=blocked_commit_path[1],
            seeker_truth_path=truth_path, observer_starts=observer_starts,
            score=_score(
                raw_seed, draw, "pair", seeker_start, seeker_goal, obstacle,
            ),
        )
    return None


def _pack_candidates(
    bitmap: np.ndarray, candidates: Iterable[_PairCandidate], *, raw_seed: int,
    pair_count: int, observation_radius: int,
) -> list[_SelectedPair]:
    selected: list[_SelectedPair] = []
    occupied: set[Coordinate] = set()
    start_cells: list[Coordinate] = []
    obstacles: list[Coordinate] = []
    for candidate in sorted(candidates, key=lambda item: item.score):
        seeker_keys = {
            candidate.seeker_start, candidate.seeker_goal,
            candidate.obstacle, candidate.commitment,
        }
        if seeker_keys & occupied:
            continue
        if any(_manhattan(candidate.obstacle, other) < 4 for other in obstacles):
            continue
        if any(
            _chebyshev(candidate.seeker_start, other) <= 1
            for other in start_cells
        ):
            continue
        observer = _choose_observer_route(
            bitmap, candidate, raw_seed=raw_seed, occupied=occupied | seeker_keys,
            existing_starts=tuple(start_cells) + (candidate.seeker_start,),
            observation_radius=observation_radius,
        )
        if observer is None:
            continue
        selected.append(observer)
        occupied.update({
            observer.observer_start, observer.observer_goal,
            candidate.seeker_start, candidate.seeker_goal,
            candidate.obstacle, candidate.commitment,
        })
        start_cells.extend((observer.observer_start, candidate.seeker_start))
        obstacles.append(candidate.obstacle)
        if len(selected) == pair_count:
            break
    return selected


def _choose_observer_route(
    bitmap: np.ndarray, candidate: _PairCandidate, *, raw_seed: int,
    occupied: set[Coordinate], existing_starts: tuple[Coordinate, ...],
    observation_radius: int,
) -> _SelectedPair | None:
    excluded_route = set(candidate.seeker_truth_path[:candidate.divergence_step + 1])
    for observer_start in candidate.observer_starts:
        if observer_start in occupied:
            continue
        if any(_chebyshev(observer_start, other) <= 1 for other in existing_starts):
            continue
        parents, distances = _bounded_bfs(bitmap, observer_start, max_distance=16)
        goals = [
            cell for cell, distance in distances.items()
            if 8 <= distance <= 16 and cell not in occupied
            and cell != candidate.seeker_start and cell != candidate.seeker_goal
        ]
        goals.sort(key=lambda cell: _score(
            raw_seed, candidate.score, "observer-goal", observer_start, cell,
        ))
        for observer_goal in goals:
            route = _reconstruct_bfs_path(parents, observer_start, observer_goal)
            # Keep the observer from occupying the seeker's pre-commitment lane;
            # later interaction is permitted and is part of the non-tiled MAPF.
            if set(route[1:]) & excluded_route:
                continue
            return _SelectedPair(
                observer_start=observer_start, observer_goal=observer_goal,
                observer_truth_path=route, candidate=candidate,
            )
    return None


def _build_instance(
    *, bitmap: np.ndarray, seed: int, raw_seed: int, attempt: int,
    target_density: float, observation_radius: int, max_episode_steps: int,
    corridor_horizon: int, candidates_examined: int,
    candidate_draws_per_attempt: int,
    selected: list[_SelectedPair], rejection_counts: dict[str, int],
    bitmap_digest: str,
) -> EpisodeInstance:
    starts: list[Coordinate] = []
    goals: list[Coordinate] = []
    critical_pairs: list[str] = []
    diagnostics = []
    for pair_index, pair in enumerate(selected):
        candidate = pair.candidate
        observer_id, seeker_id = 2 * pair_index, 2 * pair_index + 1
        starts.extend((pair.observer_start, candidate.seeker_start))
        goals.extend((pair.observer_goal, candidate.seeker_goal))
        critical_pairs.append(
            f"{observer_id},{seeker_id},{candidate.obstacle[0]},"
            f"{candidate.obstacle[1]},{candidate.commitment[0]},"
            f"{candidate.commitment[1]}"
        )
        diagnostics.append({
            "pair": pair_index,
            "observer_truth_path_steps": len(pair.observer_truth_path) - 1,
            "seeker_truth_path_steps": len(candidate.seeker_truth_path) - 1,
            "divergence_step": candidate.divergence_step,
            "commitment_step": candidate.divergence_step - 1,
            "zero_delay_communication_window_steps": candidate.divergence_step - 1,
            "obstacle_chebyshev_from_seeker_start": _chebyshev(
                candidate.seeker_start, candidate.obstacle,
            ),
            "free_next": list(candidate.free_next),
            "blocked_next": list(candidate.blocked_next),
        })
    if len(set(starts + goals)) != len(starts) + len(goals):
        raise RuntimeError("natural-critical selector produced duplicate starts/goals")
    metadata = MappingProxyType({
        "instance_family": "natural_critical_random",
        "geometry_version": "1",
        "generator_version": _GENERATOR_VERSION,
        "sampling_distribution": "iid_bernoulli_occupancy",
        "target_obstacle_density": repr(target_density),
        "raw_bitmap_seed": str(raw_seed),
        "raw_bitmap_sha256": bitmap_digest,
        "post_selection_bitmap_sha256": natural_bitmap_sha256(bitmap),
        "selection_attempt": str(attempt),
        "raw_maps_examined": str(attempt + 1),
        "candidate_draw_budget_per_attempt": str(candidate_draws_per_attempt),
        "candidate_draws_used_total": str(
            (attempt + 1) * candidate_draws_per_attempt
            - rejection_counts.get("candidate_draws_unused_after_success", 0)
        ),
        "accepted_candidate_count": str(candidates_examined),
        "selection_rejection_counts": json.dumps(
            rejection_counts, sort_keys=True, separators=(",", ":"),
        ),
        "selection_contract": (
            "geometry_and_counterfactual_planning_only;no_policy;no_link;"
            "no_episode_outcome;bitmap_immutable"
        ),
        "pair_filter": (
            f"fov_radius={observation_radius};divergence=2..{corridor_horizon};"
            "seeker_truth_path=12..40;observer_truth_path=8..16;"
            "truth_action=blocked_scenario"
        ),
        "pairs": str(len(selected)),
        "critical_decision_pairs": ";".join(critical_pairs),
        "natural_pair_diagnostics": json.dumps(
            diagnostics, sort_keys=True, separators=(",", ":"),
        ),
    })
    return EpisodeInstance(
        obstacle_map=bitmap, starts=tuple(starts), goals=tuple(goals),
        generation_seed=seed, map_size=int(bitmap.shape[0]),
        obstacle_density=float(bitmap.mean()),
        observation_radius=observation_radius,
        max_episode_steps=max_episode_steps, num_agents=2 * len(selected),
        collision_system="priority", package_metadata=metadata,
    )


def _observed_map(
    bitmap: np.ndarray, positions: Iterable[Coordinate], radius: int,
) -> np.ndarray:
    # UNKNOWN is optimistic FREE in the benchmark's planning adapter.
    observed = np.zeros_like(bitmap, dtype=np.uint8)
    height, width = bitmap.shape
    for row, column in positions:
        row_slice = slice(max(0, row - radius), min(height, row + radius + 1))
        column_slice = slice(
            max(0, column - radius), min(width, column + radius + 1),
        )
        observed[row_slice, column_slice] = bitmap[row_slice, column_slice]
    return observed


def _dynamic_prefix_is_consistent(
    bitmap: np.ndarray, *, planner: AStarPlanner,
    prefix: tuple[Coordinate, ...], goal: Coordinate,
    observation_radius: int,
) -> bool:
    """Verify that normal optimistic replanning actually reaches commitment."""
    for index in range(len(prefix) - 1):
        belief = _observed_map(bitmap, prefix[:index + 1], observation_radius)
        path = planner.plan(belief, prefix[index], goal).path
        if len(path) < 2 or path[1] != prefix[index + 1]:
            return False
    return True


def _first_divergence(
    left: tuple[Coordinate, ...], right: tuple[Coordinate, ...],
) -> int | None:
    for index, (left_cell, right_cell) in enumerate(zip(left, right)):
        if left_cell != right_cell:
            return index
    return None


def _bounded_bfs(
    bitmap: np.ndarray, start: Coordinate, *, max_distance: int,
) -> tuple[dict[Coordinate, Coordinate], dict[Coordinate, int]]:
    parents: dict[Coordinate, Coordinate] = {}
    distances = {start: 0}
    queue: deque[Coordinate] = deque((start,))
    while queue:
        current = queue.popleft()
        distance = distances[current]
        if distance == max_distance:
            continue
        for delta in _NEIGHBOURS:
            candidate = current[0] + delta[0], current[1] + delta[1]
            if (
                candidate in distances or not _in_bounds(bitmap.shape, candidate)
                or int(bitmap[candidate]) == 1
            ):
                continue
            parents[candidate] = current
            distances[candidate] = distance + 1
            queue.append(candidate)
    return parents, distances


def _reconstruct_bfs_path(
    parents: dict[Coordinate, Coordinate], start: Coordinate, goal: Coordinate,
) -> tuple[Coordinate, ...]:
    reverse = [goal]
    while reverse[-1] != start:
        reverse.append(parents[reverse[-1]])
    return tuple(reversed(reverse))


def _square_cells(
    shape: tuple[int, int], center: Coordinate, radius: int,
) -> Iterable[Coordinate]:
    for row in range(max(0, center[0] - radius), min(shape[0], center[0] + radius + 1)):
        for column in range(
            max(0, center[1] - radius), min(shape[1], center[1] + radius + 1),
        ):
            yield row, column


def _score(*values: object) -> str:
    return sha256("|".join(map(str, values)).encode("utf-8")).hexdigest()


def _manhattan(left: Coordinate, right: Coordinate) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def _chebyshev(left: Coordinate, right: Coordinate) -> int:
    return max(abs(left[0] - right[0]), abs(left[1] - right[1]))


def _in_bounds(shape: tuple[int, int], cell: Coordinate) -> bool:
    return 0 <= cell[0] < shape[0] and 0 <= cell[1] < shape[1]
