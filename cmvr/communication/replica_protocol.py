"""Planner-independent primitives for versioned map replica repair.

This module deliberately contains no environment, true-map, or planner access.
It defines the explicit wire payloads and the receiver-local region-selection
rules used by the PSR executor.  Keeping these pieces separate makes it
possible to audit the communication protocol without reading POGEMA control
flow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
from itertools import combinations
from math import ceil, exp
from random import Random

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
    # Rejected auxiliary variants retained only for the matched route-witness
    # gate ablation.  Final CARE is CERTIFICATE_REPAIR: the exact scenario
    # certificate already applies its action-divergence/round-trip deadline and
    # does not union either route-witness variant.
    CERTIFICATE_REPAIR_ROUTE_GATE = "certificate_repair_route_gate"
    CERTIFICATE_REPAIR_NO_COMMITMENT_GATE = "certificate_repair_no_commitment_gate"
    # Canonical names state exactly what the codec-matched adaptations do.  The
    # legacy aliases retain config compatibility without claiming that these
    # binary-cell selectors reproduce the source papers' richer models/codecs.
    OCBC_FS_REPAIR = "ocbc_forward_simulation"
    OCBC_FORWARD_SIMULATION = "ocbc_forward_simulation"
    PGSC_REPAIR = "path_guided_compression"
    PATH_GUIDED_COMPRESSION = "path_guided_compression"
    BRD_REPAIR = "rate_distortion_compression"
    RATE_DISTORTION_COMPRESSION = "rate_distortion_compression"
    VOI_PER_BYTE_REPAIR = "voi_repair"
    VOI_REPAIR = "voi_repair"
    PATH_AWARE_TOP_K_REPAIR = "path_aware_top_k_repair"
    SINGLE_CELL_SENSITIVITY_REPAIR = "single_cell_sensitivity_repair"
    SCUTTLEBUTT_DEPTH = "scuttlebutt_depth"
    MERKLE_ANTI_ENTROPY = "merkle_anti_entropy"
    IBLT_RECONCILIATION = "iblt_reconciliation"


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
    iblt_cells: int = 21
    iblt_hashes: int = 3
    iblt_hash_seed: int = 20260809
    iblt_partitions: int = 16
    merkle_fanout: int = 16
    merkle_session_steps: int = 4
    external_candidate_multiplier: int = 2
    ocbc_samples: int = 128
    algorithm_seed: int = 20260813
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
        if self.iblt_cells < self.iblt_hashes or self.iblt_hashes < 2:
            raise ValueError("IBLT requires cells >= hashes >= 2")
        if not 0 <= self.iblt_hash_seed <= 2**32 - 1:
            raise ValueError("IBLT hash seed must fit 32 bits")
        if self.iblt_partitions < 1:
            raise ValueError("IBLT partition count must be positive")
        if self.iblt_hash_seed + self.iblt_partitions - 1 > 2**32 - 1:
            raise ValueError("IBLT partition seeds must fit 32 bits")
        if not 2 <= self.merkle_fanout <= 255:
            raise ValueError("Merkle fanout must lie in [2, 255]")
        if self.merkle_session_steps < 1:
            raise ValueError("Merkle session length must be positive")
        if self.external_candidate_multiplier < 1 or self.ocbc_samples < 1:
            raise ValueError("external candidate multiplier and OCBC samples must be positive")
        if self.algorithm_seed < 0:
            raise ValueError("algorithm seed must be non-negative")

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


@dataclass(frozen=True)
class TaskAwareRepairPlan:
    """Heuristic query plan without joint uncertainty scenarios."""

    cells: tuple[Coordinate, ...]
    candidate_cells: tuple[Coordinate, ...]
    sensitive_cells: int = 0
    infeasible_cells: int = 0


def path_guided_spatial_coverage_plan(
    belief: BeliefMap, path: tuple[Coordinate, ...], *,
    max_horizon: int, max_cells: int, sigma: float,
    coverage_sigma: float | None = None, candidate_multiplier: int = 2,
) -> TaskAwareRepairPlan:
    """Greedily cover path-weighted uncertainty with exact-cell queries.

    This *Path-Guided Spatial-Coverage* (PGSC) rule is a codec-matched inspired
    adaptation, not a reproduction of multiresolution map compression.  For
    unknown demand cells ``u`` it greedily maximizes the monotone facility-
    location objective

    ``sum_u path_weight(u) * max_{s in S} spatial_kernel(u, s)``.

    The diversity term makes PGSC different from path-proximity Top-K while
    every selected member of ``S`` remains an ordinary exact versioned cell;
    no untransmitted cell is reconstructed or written into the replica.
    """
    coverage_sigma = sigma if coverage_sigma is None else coverage_sigma
    if (
        max_horizon < 1 or max_cells < 0 or sigma <= 0
        or coverage_sigma <= 0 or candidate_multiplier < 1
    ):
        raise ValueError("PGSC bounds and kernel widths must be valid")
    all_candidates = tuple(
        (x, y) for x in range(belief.shape[0]) for y in range(belief.shape[1])
        if int(belief.occupancy[x, y]) < 0
    )
    imminent = path[1:max_horizon + 1] or path[:1]
    if not all_candidates or max_cells == 0:
        return TaskAwareRepairPlan((), all_candidates)

    # A bounded path-weighted proposal pool keeps the greedy coverage step
    # practical on large maps.  This is a declared compute cap, not hidden map
    # compression: every proposal and selected item is still an exact cell.
    proposal_count = min(
        len(all_candidates), max_cells * candidate_multiplier,
    )
    candidates = tuple(sorted(
        all_candidates,
        key=lambda cell: (
            -path_weight(cell, imminent, sigma=sigma),
            path_distance(cell, imminent), cell[0], cell[1],
        ),
    )[:proposal_count])

    demand_weights = {
        cell: path_weight(cell, imminent, sigma=sigma) for cell in candidates
    }
    covered = {cell: 0.0 for cell in candidates}
    remaining = set(candidates)
    selected: list[Coordinate] = []
    while remaining and len(selected) < max_cells:
        best_cell: Coordinate | None = None
        best_gain = -1.0
        for cell in sorted(remaining):
            gain = 0.0
            for demand in candidates:
                dx = demand[0] - cell[0]
                dy = demand[1] - cell[1]
                similarity = exp(
                    -(dx * dx + dy * dy)
                    / (2.0 * coverage_sigma * coverage_sigma)
                )
                gain += demand_weights[demand] * max(
                    0.0, similarity - covered[demand],
                )
            key = (
                gain,
                -path_distance(cell, imminent),
                -cell[0],
                -cell[1],
            )
            best_key = (
                best_gain,
                -path_distance(best_cell, imminent) if best_cell is not None else -2**31,
                -best_cell[0] if best_cell is not None else -2**31,
                -best_cell[1] if best_cell is not None else -2**31,
            )
            if key > best_key:
                best_cell, best_gain = cell, gain
        assert best_cell is not None
        selected.append(best_cell)
        remaining.remove(best_cell)
        for demand in candidates:
            dx = demand[0] - best_cell[0]
            dy = demand[1] - best_cell[1]
            covered[demand] = max(
                covered[demand],
                exp(
                    -(dx * dx + dy * dy)
                    / (2.0 * coverage_sigma * coverage_sigma)
                ),
            )
    return TaskAwareRepairPlan(tuple(selected), candidates)


def bernoulli_rate_distortion_plan(
    belief: BeliefMap, path: tuple[Coordinate, ...], *,
    max_horizon: int, max_cells: int, sigma: float,
    prior_blocked_probability: float = 0.2,
    prior_strength: float = 1.0,
    decoder_radius: int | None = None,
) -> TaskAwareRepairPlan:
    """Minimize Bernoulli decoder distortion using lossless exact cells.

    This *Bernoulli Rate--Distortion* (BRD) rule is a zero-or-exact discrete
    adaptation, not a reproduction of the continuous Gaussian transform and
    quantizer in the source work.  A receiver-local kernel decoder estimates
    ``q_u = P(blocked)`` exclusively from that receiver's known cells and a
    frozen Beta prior.  Leaving ``u`` at zero rate incurs weighted squared
    distortion ``path_weight(u) * q_u * (1-q_u)``; sending its canonical exact
    record removes that term.  Since every record has the same wire rate, BRD
    selects the largest distortion reductions under the common cell budget.
    """
    if max_horizon < 1 or max_cells < 0 or sigma <= 0:
        raise ValueError("BRD bounds and kernel width must be valid")
    if not 0.0 < prior_blocked_probability < 1.0 or prior_strength <= 0:
        raise ValueError("BRD prior probability and strength must be positive")
    decoder_radius = ceil(3.0 * sigma) if decoder_radius is None else decoder_radius
    if decoder_radius < 1:
        raise ValueError("BRD decoder radius must be positive")
    candidates = tuple(
        (x, y) for x in range(belief.shape[0]) for y in range(belief.shape[1])
        if int(belief.occupancy[x, y]) < 0
    )
    imminent = path[1:max_horizon + 1] or path[:1]
    probabilities = bernoulli_local_decoder_probabilities(
        belief, candidates, sigma=sigma,
        prior_blocked_probability=prior_blocked_probability,
        prior_strength=prior_strength, decoder_radius=decoder_radius,
    )
    ranked = tuple(sorted(
        candidates,
        key=lambda cell: (
            -(
                path_weight(cell, imminent, sigma=sigma)
                * probabilities[cell] * (1.0 - probabilities[cell])
            ),
            path_distance(cell, imminent), cell[0], cell[1],
        ),
    ))
    return TaskAwareRepairPlan(ranked[:max_cells], ranked)


def bernoulli_local_decoder_probabilities(
    belief: BeliefMap, candidates: tuple[Coordinate, ...], *, sigma: float,
    prior_blocked_probability: float = 0.2, prior_strength: float = 1.0,
    decoder_radius: int | None = None,
) -> dict[Coordinate, float]:
    """Return receiver-local Bernoulli predictions without truth/peer access."""
    if len(set(candidates)) != len(candidates):
        raise ValueError("Bernoulli decoder candidates must be unique")
    if sigma <= 0 or not 0.0 < prior_blocked_probability < 1.0 or prior_strength <= 0:
        raise ValueError("Bernoulli decoder kernel and prior must be positive")
    decoder_radius = ceil(3.0 * sigma) if decoder_radius is None else decoder_radius
    if decoder_radius < 1:
        raise ValueError("Bernoulli decoder radius must be positive")
    result: dict[Coordinate, float] = {}
    for x, y in candidates:
        if not belief.in_bounds(x, y) or int(belief.occupancy[x, y]) >= 0:
            raise ValueError("Bernoulli decoder candidates must be local UNKNOWN cells")
        blocked_mass = prior_strength * prior_blocked_probability
        total_mass = prior_strength
        for nx in range(max(0, x - decoder_radius), min(belief.shape[0], x + decoder_radius + 1)):
            for ny in range(max(0, y - decoder_radius), min(belief.shape[1], y + decoder_radius + 1)):
                state = int(belief.occupancy[nx, ny])
                if state < 0:
                    continue
                dx, dy = nx - x, ny - y
                weight = exp(-(dx * dx + dy * dy) / (2.0 * sigma * sigma))
                blocked_mass += weight * float(state == 1)
                total_mass += weight
        result[(x, y)] = blocked_mass / total_mass
    return result


# Backwards-compatible import names.  Their implementations and public
# documentation intentionally use the honest PGSC/BRD adaptation names.
path_guided_compression_plan = path_guided_spatial_coverage_plan
rate_distortion_compression_plan = bernoulli_rate_distortion_plan


def ocbc_forward_simulation_plan(
    candidates: tuple[Coordinate, ...],
    optimistic_path: tuple[Coordinate, ...],
    blocked_paths: dict[Coordinate, tuple[Coordinate, ...]], *,
    max_horizon: int, max_cells: int, samples: int, seed: int,
    blocked_probabilities: dict[Coordinate, float] | None = None,
) -> TaskAwareRepairPlan:
    """Select exact cells with an OCBC-inspired forward-simulation score.

    This is *OCBC-FS Repair*, an inspired adaptation rather than an exact OCBC
    reproduction.  Joint Bernoulli worlds are sampled with a fixed compute
    budget from caller-supplied local priors (or an explicit 0.5 default).
    Each cell arm is valued by its expected bounded safe-progress improvement,
    and positive arms are selected under the exact-cell query cap.  The source
    OCBC algorithm additionally models teammate beliefs and uses CSAR; neither
    is silently approximated here.  No belief map, peer replica, or true map is
    accepted by this pure selector.
    """
    if max_horizon < 1 or max_cells < 0 or samples < 1:
        raise ValueError("OCBC bounds and sample budget must be positive")
    if len(set(candidates)) != len(candidates):
        raise ValueError("OCBC candidates must be unique")
    if set(blocked_paths) != set(candidates):
        raise ValueError("OCBC requires one blocked counterfactual per candidate")
    probabilities = _validated_blocked_probabilities(
        candidates, blocked_probabilities,
    )
    rng = Random(seed)
    worlds = tuple(
        frozenset(
            cell for cell in candidates if rng.random() < probabilities[cell]
        )
        for _ in range(samples)
    )
    baseline = tuple(
        _bounded_safe_progress(optimistic_path, world, max_horizon)
        for world in worlds
    )
    ranked: list[tuple[float, int, Coordinate]] = []
    for index, cell in enumerate(candidates):
        reward = sum(
            max(
                0.0,
                (
                    _bounded_safe_progress(blocked_paths[cell], world, max_horizon)
                    if cell in world else baseline[sample_index]
                ) - baseline[sample_index],
            )
            for sample_index, world in enumerate(worlds)
        ) / samples
        if reward > 0:
            ranked.append((-reward, index, cell))
    ranked.sort()
    selected = tuple(item[2] for item in ranked[:max_cells])
    return TaskAwareRepairPlan(selected, candidates, sensitive_cells=len(ranked))


def voi_per_byte_plan(
    candidates: tuple[Coordinate, ...],
    optimistic_path: tuple[Coordinate, ...],
    blocked_paths: dict[Coordinate, tuple[Coordinate, ...]], *,
    max_horizon: int, max_cells: int,
    blocked_probabilities: dict[Coordinate, float] | None = None,
    query_entry_bytes: int = 6, patch_entry_bytes: int = 13,
) -> TaskAwareRepairPlan:
    """Rank exact cells by locally estimated task value per marginal byte.

    This *VoI-per-Byte Repair* rule is a codec-matched task-value adaptation,
    not a claim to reproduce a particular belief-space communication system.
    Revealing FREE leaves the optimistic plan unchanged; revealing BLOCKED
    invokes the supplied local counterfactual.  Its expected bounded-progress
    gain is divided by the actual marginal query-plus-patch record cost.  The
    fixed query/patch headers do not affect ranking and remain charged by the
    transport.  Priors are explicit inputs, and the pure selector accepts no
    true map or peer replica.
    """
    if max_horizon < 1 or max_cells < 0:
        raise ValueError("VoI bounds must be valid")
    if query_entry_bytes < 1 or patch_entry_bytes < 1:
        raise ValueError("VoI wire entry sizes must be positive")
    if len(set(candidates)) != len(candidates):
        raise ValueError("VoI candidates must be unique")
    if set(blocked_paths) != set(candidates):
        raise ValueError("VoI requires one blocked counterfactual per candidate")
    probabilities = _validated_blocked_probabilities(
        candidates, blocked_probabilities,
    )
    marginal_bytes = query_entry_bytes + patch_entry_bytes
    ranked = []
    for index, cell in enumerate(candidates):
        blocked = frozenset((cell,))
        baseline = _bounded_safe_progress(optimistic_path, blocked, max_horizon)
        informed = _bounded_safe_progress(blocked_paths[cell], blocked, max_horizon)
        score = probabilities[cell] * max(0.0, informed - baseline) / marginal_bytes
        if score > 0:
            ranked.append((-score, index, cell))
    ranked.sort()
    selected = tuple(item[2] for item in ranked[:max_cells])
    return TaskAwareRepairPlan(selected, candidates, sensitive_cells=len(ranked))


def _validated_blocked_probabilities(
    candidates: tuple[Coordinate, ...],
    probabilities: dict[Coordinate, float] | None,
) -> dict[Coordinate, float]:
    """Validate explicit local priors without consulting hidden state."""
    if probabilities is None:
        return {cell: 0.5 for cell in candidates}
    if set(probabilities) != set(candidates):
        raise ValueError("blocked probabilities require exactly one value per candidate")
    if any(not 0.0 <= float(value) <= 1.0 for value in probabilities.values()):
        raise ValueError("blocked probabilities must lie in [0, 1]")
    return {cell: float(probabilities[cell]) for cell in candidates}


def _bounded_safe_progress(
    path: tuple[Coordinate, ...], blocked: frozenset[Coordinate], horizon: int,
) -> float:
    """Normalized progress before the first sampled blocked transition."""
    if not path:
        return 0.0
    safe_steps = 0
    for cell in path[1:horizon + 1]:
        if cell in blocked:
            break
        safe_steps += 1
    if len(path) - 1 <= horizon and safe_steps == len(path) - 1:
        return 1.0
    return safe_steps / horizon


def decision_candidate_cells(
    belief: BeliefMap, optimistic_path: tuple[Coordinate, ...], *,
    max_horizon: int, max_candidates: int | None,
) -> tuple[Coordinate, ...]:
    """Unknown action-graph vertices ordered by earliest path influence."""
    if max_horizon < 1:
        raise ValueError("max_horizon must be positive")
    if max_candidates is not None and max_candidates < 1:
        raise ValueError("max_candidates must be positive when set")
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
    ordered = tuple(sorted(priority, key=priority.__getitem__))
    return ordered if max_candidates is None else ordered[:max_candidates]


def path_aware_top_k_plan(
    belief: BeliefMap, optimistic_path: tuple[Coordinate, ...], *,
    max_horizon: int, max_cells: int,
) -> TaskAwareRepairPlan:
    """Take the earliest and closest path-adjacent unknown cells.

    This is deliberately a path heuristic: it neither replans a
    counterfactual map nor enumerates joint occupancy scenarios.  Candidate
    ordering is earliest future path index, then graph distance and coordinate.
    """
    if max_cells < 0:
        raise ValueError("max_cells must be non-negative")
    candidates = decision_candidate_cells(
        belief, optimistic_path,
        max_horizon=max_horizon, max_candidates=None,
    )
    return TaskAwareRepairPlan(candidates[:max_cells], candidates)


def single_cell_sensitivity_plan(
    candidates: tuple[Coordinate, ...],
    optimistic_path: tuple[Coordinate, ...],
    blocked_paths: dict[Coordinate, tuple[Coordinate, ...]],
    *, round_trip_steps: int, max_cells: int,
) -> TaskAwareRepairPlan:
    """Rank independent blocked-cell counterfactuals by action sensitivity.

    Immediate next-action changes rank first, followed by the earliest later
    path divergence.  A cell whose first divergence precedes the query--patch
    round trip is recorded but excluded because its information cannot arrive
    in time.  Unlike CARE, this function never compares multi-cell scenarios
    and never solves a hitting set.
    """
    if round_trip_steps < 0 or max_cells < 0:
        raise ValueError("deadline and query bounds must be non-negative")
    if len(set(candidates)) != len(candidates):
        raise ValueError("candidate cells must be unique")
    if set(blocked_paths) != set(candidates):
        raise ValueError("each candidate requires exactly one blocked path")
    ranked: list[tuple[tuple[bool, int, int], Coordinate]] = []
    sensitive = infeasible = 0
    for candidate_index, cell in enumerate(candidates):
        divergence = first_path_divergence(
            optimistic_path, blocked_paths[cell],
        )
        if divergence is None:
            continue
        sensitive += 1
        if divergence < round_trip_steps:
            infeasible += 1
            continue
        ranked.append(((divergence != 0, divergence, candidate_index), cell))
    ranked.sort(key=lambda item: item[0])
    selected = tuple(cell for _, cell in ranked[:max_cells])
    return TaskAwareRepairPlan(
        selected, candidates, sensitive_cells=sensitive,
        infeasible_cells=infeasible,
    )


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
    enforce_deadline: bool = True,
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
    if (not feasible and enforce_deadline) or max_cells == 0:
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
