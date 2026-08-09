"""Planner-independent primitives for versioned map replica repair.

This module deliberately contains no environment, true-map, or planner access.
It defines the explicit wire payloads and the receiver-local region-selection
rules used by the PSR executor.  Keeping these pieces separate makes it
possible to audit the communication protocol without reading POGEMA control
flow.
"""

from __future__ import annotations

from hashlib import sha256
from itertools import combinations
from math import exp
from dataclasses import dataclass, field
from enum import Enum

from cmvr.communication.unreliable import LinkConfig
from cmvr.mapping import BeliefMap, MapUpdate
from cmvr.planning import Coordinate


ReplicaStamp = tuple[int, int, int, int]


class ReplicaPolicy(str, Enum):
    """Matched replica-delivery policies used by the fixed-planner runner."""

    NO_COMMUNICATION = "no_communication"
    ONE_SHOT_DELTA = "one_shot_delta"
    RETRY_ALL_ARQ = "retry_all_arq"
    PERIODIC_FULL_SYNC = "periodic_full_sync"
    PERIODIC_REGIONAL_SYNC = "periodic_regional_sync"
    FULL_REPLICA_REPAIR = "full_replica_repair"
    PATH_WEIGHTED_ARQ = "path_weighted_arq"
    MISMATCH_TRIGGERED_FULL_REPAIR = "mismatch_triggered_full_repair"
    ACTION_TRIGGERED_REPAIR = "action_triggered_repair"
    UTILITY_TRIGGERED_REPAIR = "utility_triggered_repair"
    DEADLINE_AWARE_REPAIR = "deadline_aware_repair"
    CERTIFICATE_REPAIR = "certificate_repair"


@dataclass(frozen=True)
class PSRConfig:
    """Frozen transport and planning-corridor parameters for replica repair."""

    data_bytes_per_agent_per_step: int = 26
    control_bytes_per_agent_per_step: int = 256
    repair_interval_steps: int = 4
    sync_interval_steps: int = 8
    corridor_horizon: int = 8
    corridor_radius: int = 1
    digest_base_bytes: int = 16
    digest_entry_bytes: int = 6
    ack_bytes: int = 8
    patch_base_bytes: int = 4
    replica_digest_bytes: int = 16
    path_weighted_sigma: float = 1.0
    max_digest_peers: int | None = None
    certificate_max_cells: int = 8
    certificate_uncertainty_order: int = 2
    link: LinkConfig = field(default_factory=LinkConfig)

    def __post_init__(self) -> None:
        if min(self.data_bytes_per_agent_per_step, self.control_bytes_per_agent_per_step) < 0:
            raise ValueError("per-agent budgets must be non-negative")
        if min(self.repair_interval_steps, self.sync_interval_steps, self.corridor_horizon) < 1:
            raise ValueError("intervals and horizon must be positive")
        if self.corridor_radius < 0 or min(self.digest_base_bytes, self.digest_entry_bytes, self.ack_bytes, self.patch_base_bytes, self.replica_digest_bytes) < 1:
            raise ValueError("packet sizes must be positive and radius non-negative")
        if self.path_weighted_sigma <= 0:
            raise ValueError("path_weighted_sigma must be positive")
        if self.max_digest_peers is not None and self.max_digest_peers < 1:
            raise ValueError("max_digest_peers must be positive when set")
        if self.certificate_max_cells < 1:
            raise ValueError("certificate_max_cells must be positive")
        if not 1 <= self.certificate_uncertainty_order <= self.certificate_max_cells:
            raise ValueError("certificate uncertainty order must lie in [1, max cells]")

    def max_digest_cells_per_message(self) -> int:
        """Largest digest fitting one sender's control budget.

        A full-replica baseline must not obtain an implicit oversized control
        packet.  It therefore scans the full domain in deterministic chunks
        under the same per-step cap as path-scoped repair.
        """
        return max(0, (self.control_bytes_per_agent_per_step - self.digest_base_bytes) // self.digest_entry_bytes)


@dataclass(frozen=True)
class DigestQuery:
    cells: tuple[Coordinate, ...]
    requester_stamps: tuple[ReplicaStamp, ...]
    regional_only: bool = False
    action_only: bool = False


@dataclass(frozen=True)
class DeltaPayload:
    update: MapUpdate
    task_key: tuple[str, int] | None = None
    is_repair: bool = False


@dataclass(frozen=True)
class PatchPayload:
    updates: tuple[MapUpdate, ...]


@dataclass(frozen=True)
class ReplicaDigest:
    """Fixed-size summary of a complete explicit replica, never ground truth."""

    digest: str


@dataclass(frozen=True)
class DecisionRepairPlan:
    """Receiver-local certificate for one deadline-constrained repair query."""

    ambiguous: bool
    feasible: bool
    decision_slack_steps: int | None
    round_trip_steps: int
    cells: tuple[Coordinate, ...]


@dataclass(frozen=True)
class ScenarioCertificate:
    """Exact minimum query separating all deadline-feasible scenario pairs."""

    cells: tuple[Coordinate, ...]
    candidate_cells: tuple[Coordinate, ...]
    scenario_count: int
    conflicting_pairs: int
    feasible_pairs: int
    infeasible_pairs: int


def decision_candidate_cells(
    belief: BeliefMap, optimistic_path: tuple[Coordinate, ...], *,
    max_horizon: int, max_candidates: int,
) -> tuple[Coordinate, ...]:
    """Unknown action-graph vertices ordered by earliest path influence."""
    priority: dict[Coordinate, tuple[int, int, int, int]] = {}
    for path_index, (x, y) in enumerate(optimistic_path[1:max_horizon + 1], start=1):
        for distance, cell in (
            (0, (x, y)), (1, (x - 1, y)), (1, (x + 1, y)),
            (1, (x, y - 1)), (1, (x, y + 1)),
        ):
            if not belief.in_bounds(*cell) or int(belief.occupancy[cell]) >= 0:
                continue
            key = path_index, distance, cell[0], cell[1]
            priority[cell] = min(priority.get(cell, key), key)
    return tuple(sorted(priority, key=priority.__getitem__)[:max_candidates])


def scenario_blocked_sets(
    candidates: tuple[Coordinate, ...], *, uncertainty_order: int,
) -> tuple[frozenset[Coordinate], ...]:
    """Canonical q-sparse occupancy scenarios, including all-free."""
    if uncertainty_order < 0:
        raise ValueError("uncertainty_order must be non-negative")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate cells must be unique")
    return tuple(
        frozenset(blocked)
        for order in range(min(uncertainty_order, len(candidates)) + 1)
        for blocked in combinations(candidates, order)
    )


def minimum_scenario_certificate(
    candidates: tuple[Coordinate, ...],
    scenario_paths: dict[frozenset[Coordinate], tuple[Coordinate, ...]],
    *, round_trip_steps: int,
) -> ScenarioCertificate:
    """Solve the scenario-separating query problem exactly by enumeration.

    Each pair of occupancy scenarios whose planned action sequences differ is
    distinguishable only by querying a cell in their symmetric difference.
    Pairs whose first divergence precedes the query--patch round trip are
    recorded but cannot be repaired by the current request.  Among feasible
    pairs, exhaustive cardinality-ordered enumeration returns the deterministic
    candidate-order-first minimum hitting set. Candidate sets are deliberately
    capped, so this exact solver is bounded by ``2^|candidates|``.
    """
    if round_trip_steps < 0:
        raise ValueError("round_trip_steps must be non-negative")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate cells must be unique")
    scenario_cells = set().union(*scenario_paths) if scenario_paths else set()
    if scenario_cells - set(candidates):
        raise ValueError("scenario contains a cell outside the candidate set")
    constraints: list[frozenset[Coordinate]] = []
    conflicts = infeasible = 0
    scenarios = tuple(scenario_paths)
    for left_index, left in enumerate(scenarios):
        for right in scenarios[left_index + 1:]:
            divergence = first_path_divergence(
                scenario_paths[left], scenario_paths[right],
            )
            if divergence is None:
                continue
            conflicts += 1
            difference = left.symmetric_difference(right)
            if divergence < round_trip_steps:
                infeasible += 1
            elif difference:
                constraints.append(difference)
    selected: tuple[Coordinate, ...] = ()
    for size in range(len(candidates) + 1):
        selected = next((
            subset for subset in combinations(candidates, size)
            if all(any(cell in constraint for cell in subset) for constraint in constraints)
        ), ())
        if selected or not constraints:
            break
    return ScenarioCertificate(
        selected, candidates, len(scenarios), conflicts,
        len(constraints), infeasible,
    )


def first_path_divergence(
    optimistic_path: tuple[Coordinate, ...],
    pessimistic_path: tuple[Coordinate, ...],
) -> int | None:
    """Return steps until the first different action along two local plans.

    A value of zero means the next actions already disagree. ``None`` means
    the complete coordinate sequences induce the same action sequence. An
    empty path is interpreted as waiting at the other path's start.
    """
    if not optimistic_path and not pessimistic_path:
        return None
    origin = optimistic_path[0] if optimistic_path else pessimistic_path[0]
    left = optimistic_path or (origin,)
    right = pessimistic_path or (origin,)
    last_step = max(len(left), len(right)) - 1
    for step in range(last_step):
        left_next = left[step + 1] if step + 1 < len(left) else left[-1]
        right_next = right[step + 1] if step + 1 < len(right) else right[-1]
        if left_next != right_next:
            return step
    return None


def deadline_decision_repair_plan(
    belief: BeliefMap,
    optimistic_path: tuple[Coordinate, ...],
    pessimistic_path: tuple[Coordinate, ...],
    *,
    round_trip_steps: int,
    max_horizon: int,
    max_cells: int,
) -> DecisionRepairPlan:
    """Build the byte-minimal witness query used by deadline-aware CARE.

    The optimistic/pessimistic pair detects a decision ambiguity.  The deadline
    is the last step before the operational path enters its first unknown cell,
    which is the latest point at which a returned patch can still cause a safe
    replan.  The certificate is the unknown one-hop influence set around both
    ambiguous branches up to reconvergence.  One hop is derived from the
    planner's four-neighbour action graph, not a tuned corridor radius.
    """
    if round_trip_steps < 0 or max_horizon < 1 or max_cells < 0:
        raise ValueError("deadline and query bounds must be non-negative")
    divergence = first_path_divergence(optimistic_path, pessimistic_path)
    if divergence is None:
        return DecisionRepairPlan(False, False, None, round_trip_steps, ())
    first_unknown = next((
        index for index, cell in enumerate(optimistic_path[1:max_horizon + 1], start=1)
        if int(belief.occupancy[cell]) < 0
    ), None)
    if first_unknown is None:
        return DecisionRepairPlan(True, False, None, round_trip_steps, ())
    slack = max(0, first_unknown - 1)
    feasible = slack >= round_trip_steps
    if not feasible or max_cells == 0:
        return DecisionRepairPlan(True, feasible, slack, round_trip_steps, ())

    opt_stop = min(len(optimistic_path), max_horizon + 1)
    pess_stop = min(len(pessimistic_path), max_horizon + 1)
    pessimistic_index = {
        cell: index for index, cell in enumerate(pessimistic_path[divergence + 1:pess_stop], start=divergence + 1)
    }
    reconvergence = next((
        (index, pessimistic_index[cell])
        for index, cell in enumerate(optimistic_path[divergence + 1:opt_stop], start=divergence + 1)
        if cell in pessimistic_index
    ), None)
    if reconvergence is not None:
        opt_stop, pess_stop = reconvergence[0] + 1, reconvergence[1] + 1

    branch = tuple(optimistic_path[divergence + 1:opt_stop]) + tuple(
        pessimistic_path[divergence + 1:pess_stop]
    )
    priority: dict[Coordinate, tuple[int, int, int, int]] = {}
    for branch_index, (x, y) in enumerate(branch):
        for distance, cell in (
            (0, (x, y)), (1, (x - 1, y)), (1, (x + 1, y)),
            (1, (x, y - 1)), (1, (x, y + 1)),
        ):
            if not belief.in_bounds(*cell) or int(belief.occupancy[cell]) >= 0:
                continue
            key = branch_index, distance, cell[0], cell[1]
            priority[cell] = min(priority.get(cell, key), key)
    witnesses = tuple(sorted(priority, key=priority.__getitem__)[:max_cells])
    return DecisionRepairPlan(True, feasible, slack, round_trip_steps, witnesses)


def update_stamp(update: MapUpdate) -> ReplicaStamp:
    return update.version, update.observed_at, update.sender_id, int(update.cell_state)


def belief_stamp(belief: BeliefMap, cell: Coordinate) -> ReplicaStamp:
    x, y = cell
    return int(belief.versions[x, y]), int(belief.last_observed_step[x, y]), int(belief.source_ids[x, y]), int(belief.occupancy[x, y])


def update_from_belief(belief: BeliefMap, cell: Coordinate) -> MapUpdate | None:
    x, y = cell
    if int(belief.occupancy[x, y]) < 0:
        return None
    return MapUpdate.create(
        sender_id=int(belief.source_ids[x, y]), x=x, y=y,
        cell_state=int(belief.occupancy[x, y]), version=int(belief.versions[x, y]),
        observed_at=int(belief.last_observed_step[x, y]),
    )


def replica_digest(belief: BeliefMap) -> ReplicaDigest:
    """Hash every state/stamp tuple in canonical cell order for mismatch detection."""
    content = bytearray()
    for x in range(belief.shape[0]):
        for y in range(belief.shape[1]):
            content.extend(
                f"{int(belief.occupancy[x, y])},{int(belief.versions[x, y])},"
                f"{int(belief.last_observed_step[x, y])},{int(belief.source_ids[x, y])};".encode()
            )
    return ReplicaDigest(sha256(content).hexdigest())


def planning_corridor(
    path: tuple[Coordinate, ...], shape: tuple[int, int], *, horizon: int, radius: int,
) -> tuple[Coordinate, ...]:
    """Return the canonical Manhattan-dilated imminent path corridor."""
    imminent = path[1:horizon + 1] or path[:1]
    cells: set[Coordinate] = set()
    for x, y in imminent:
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                candidate = x + dx, y + dy
                if abs(dx) + abs(dy) <= radius and 0 <= candidate[0] < shape[0] and 0 <= candidate[1] < shape[1]:
                    cells.add(candidate)
    return tuple(sorted(cells))


def full_replica_chunk(
    shape: tuple[int, int], *, max_cells: int, phase: int,
) -> tuple[Coordinate, ...]:
    """Select one canonical, rotating full-domain anti-entropy digest chunk."""
    if max_cells < 1:
        return ()
    domain = tuple((x, y) for x in range(shape[0]) for y in range(shape[1]))
    chunk_count = (len(domain) + max_cells - 1) // max_cells
    start = (phase % chunk_count) * max_cells
    return domain[start:start + max_cells]


def ordered_digest_peers(
    *, requester_id: int, positions: tuple[Coordinate, ...], phase: int, limit: int | None,
) -> tuple[int, ...]:
    """Nearest-peer ordering with deterministic round-robin tie breaking."""
    peers = [peer for peer in range(len(positions)) if peer != requester_id]
    peers.sort(key=lambda peer: (
        abs(positions[peer][0] - positions[requester_id][0]) + abs(positions[peer][1] - positions[requester_id][1]),
        (peer - requester_id - 1 - phase) % len(positions),
    ))
    return tuple(peers if limit is None else peers[:limit])


def path_distance(cell: Coordinate, path: tuple[Coordinate, ...]) -> int:
    """Minimum Manhattan distance from a map update to a receiver-local path."""
    return min((abs(cell[0] - point[0]) + abs(cell[1] - point[1]) for point in path), default=2**31 - 1)


def path_weight(cell: Coordinate, path: tuple[Coordinate, ...], *, sigma: float) -> float:
    """Gaussian path-proximity priority for the Path-Weighted ARQ baseline."""
    distance = path_distance(cell, path)
    return exp(-(distance * distance) / (2.0 * sigma * sigma))
