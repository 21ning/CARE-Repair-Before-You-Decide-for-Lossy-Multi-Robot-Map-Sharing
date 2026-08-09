"""Planner-independent primitives for versioned map replica repair.

This module deliberately contains no environment, true-map, or planner access.
It defines the explicit wire payloads and the receiver-local region-selection
rules used by the PSR executor.  Keeping these pieces separate makes it
possible to audit the communication protocol without reading POGEMA control
flow.
"""

from __future__ import annotations

from hashlib import sha256
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
