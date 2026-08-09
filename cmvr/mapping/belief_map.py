"""Deep-copyable per-agent map beliefs with explicit UNKNOWN state."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

import numpy as np

from .cell_state import CellState
from .map_update import DEFAULT_PACKET_FORMAT, MapUpdate, PacketFormat


@dataclass(frozen=True)
class PlanningMapAdapter:
    """Convert an explicit belief into an online planning grid without truth access."""

    unknown_policy: str = "optimistic"
    unknown_penalty: float = 3.0

    def __post_init__(self) -> None:
        if self.unknown_policy not in {"optimistic", "pessimistic", "penalized_unknown"}:
            raise ValueError("unsupported unknown planning policy")
        if self.unknown_penalty < 1.0:
            raise ValueError("unknown_penalty must be at least one")

    def to_planning_map(self, belief: "BeliefMap") -> np.ndarray:
        """Return a non-mutating planner grid.

        Optimistic maps use UNKNOWN=0. Pessimistic maps treat unknown cells as
        blocked. The current unit-cost A* interface represents penalized unknown
        cells as traversable (the default use remains optimistic); the penalty is
        exposed via :meth:`traversal_costs` for weighted planners.
        """
        result = belief.occupancy.copy()
        if self.unknown_policy == "pessimistic":
            result[result == CellState.UNKNOWN] = CellState.BLOCKED
        else:
            result[result == CellState.UNKNOWN] = CellState.FREE
        return result.astype(np.int8, copy=False)

    def traversal_costs(self, belief: "BeliefMap") -> np.ndarray:
        costs = np.ones(belief.shape, dtype=np.float64)
        if self.unknown_policy == "penalized_unknown":
            costs[belief.occupancy == CellState.UNKNOWN] = self.unknown_penalty
        return costs


class BeliefMap:
    """Independent map state held by one receiver only."""

    def __init__(self, shape: tuple[int, int]) -> None:
        if len(shape) != 2 or min(shape) <= 0:
            raise ValueError("belief-map shape must be positive and two-dimensional")
        self.occupancy = np.full(shape, CellState.UNKNOWN, dtype=np.int8)
        self.versions = np.zeros(shape, dtype=np.int64)
        self.last_observed_step = np.full(shape, -1, dtype=np.int64)
        self.source_ids = np.full(shape, -1, dtype=np.int64)

    @property
    def shape(self) -> tuple[int, int]:
        return tuple(self.occupancy.shape)

    @property
    def known_mask(self) -> np.ndarray:
        return self.occupancy != CellState.UNKNOWN

    def clone(self) -> "BeliefMap":
        cloned = BeliefMap(self.shape)
        cloned.occupancy = self.occupancy.copy()
        cloned.versions = self.versions.copy()
        cloned.last_observed_step = self.last_observed_step.copy()
        cloned.source_ids = self.source_ids.copy()
        return cloned

    def apply_update(self, update: MapUpdate) -> bool:
        """Apply a newer update, resolving equal-version conflicts deterministically."""
        self._validate_coordinate(update.x, update.y)
        current_stamp = (
            int(self.versions[update.x, update.y]),
            int(self.last_observed_step[update.x, update.y]),
            int(self.source_ids[update.x, update.y]),
            int(self.occupancy[update.x, update.y]),
        )
        incoming_stamp = (update.version, update.observed_at, update.sender_id, int(update.cell_state))
        if incoming_stamp <= current_stamp:
            return False
        self.occupancy[update.x, update.y] = int(update.cell_state)
        self.versions[update.x, update.y] = update.version
        self.last_observed_step[update.x, update.y] = update.observed_at
        self.source_ids[update.x, update.y] = update.sender_id
        return True

    def integrate_local_observation(
        self,
        local_obstacles: np.ndarray,
        center: tuple[int, int],
        *,
        sender_id: int,
        observed_at: int,
        packet_format: PacketFormat = DEFAULT_PACKET_FORMAT,
    ) -> tuple[MapUpdate, ...]:
        """Integrate only supplied local cells and emit changes as stable updates."""
        observed = np.asarray(local_obstacles)
        if observed.ndim != 2 or observed.shape[0] != observed.shape[1] or observed.shape[0] % 2 != 1:
            raise ValueError("local obstacle observation must be an odd square matrix")
        radius = observed.shape[0] // 2
        updates: list[MapUpdate] = []
        for local_x in range(observed.shape[0]):
            for local_y in range(observed.shape[1]):
                global_x = center[0] + local_x - radius
                global_y = center[1] + local_y - radius
                if not self.in_bounds(global_x, global_y):
                    continue
                state = CellState.BLOCKED if int(observed[local_x, local_y]) else CellState.FREE
                if self.occupancy[global_x, global_y] == state:
                    continue
                update = MapUpdate.create(
                    sender_id=sender_id,
                    x=global_x,
                    y=global_y,
                    cell_state=state,
                    version=int(self.versions[global_x, global_y]) + 1,
                    observed_at=observed_at,
                    packet_format=packet_format,
                )
                if self.apply_update(update):
                    updates.append(update)
        return tuple(updates)

    def fingerprint(self) -> str:
        digest = sha256()
        for array in (self.occupancy, self.versions, self.last_observed_step, self.source_ids):
            digest.update(np.ascontiguousarray(array).tobytes())
        return digest.hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "shape": list(self.shape),
            "occupancy": self.occupancy.tolist(),
            "versions": self.versions.tolist(),
            "last_observed_step": self.last_observed_step.tolist(),
            "source_ids": self.source_ids.tolist(),
            "fingerprint": self.fingerprint(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "BeliefMap":
        belief = cls(tuple(int(value) for value in data["shape"]))
        belief.occupancy = np.asarray(data["occupancy"], dtype=np.int8)
        belief.versions = np.asarray(data["versions"], dtype=np.int64)
        belief.last_observed_step = np.asarray(data["last_observed_step"], dtype=np.int64)
        belief.source_ids = np.asarray(data["source_ids"], dtype=np.int64)
        if belief.fingerprint() != data["fingerprint"]:
            raise ValueError("belief fingerprint mismatch")
        return belief

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.shape[0] and 0 <= y < self.shape[1]

    def _validate_coordinate(self, x: int, y: int) -> None:
        if not self.in_bounds(x, y):
            raise IndexError(f"belief coordinate out of bounds: {(x, y)}")
