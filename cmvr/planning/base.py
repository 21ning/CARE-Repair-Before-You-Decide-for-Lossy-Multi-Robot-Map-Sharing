"""Planner contracts shared by the deterministic baseline harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol, Sequence, Tuple

import numpy as np

Coordinate = Tuple[int, int]


@dataclass(frozen=True)
class PlanResult:
    """The outcome of one planner call.

    A successful result always includes both the requested start and goal. A
    failure has an empty path, infinite cost, and a machine-readable reason.
    """

    success: bool
    path: Tuple[Coordinate, ...]
    cost: float
    expanded_nodes: int
    failure_reason: Optional[str]
    planner_runtime_ms: float


class Planner(Protocol):
    """A deterministic static-grid planner used by the Milestone A runner."""

    def plan(
        self,
        map_belief: np.ndarray,
        start: Coordinate,
        goal: Coordinate,
    ) -> PlanResult:
        ...

    def path_cost(self, path: Sequence[Coordinate]) -> float:
        ...

    def path_is_valid(
        self, path: Sequence[Coordinate], reference_map: np.ndarray
    ) -> bool:
        ...

