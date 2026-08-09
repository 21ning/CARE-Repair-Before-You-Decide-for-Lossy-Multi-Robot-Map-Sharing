"""A deterministic four-neighbour A* planner for fully known static maps."""

from __future__ import annotations

from heapq import heappop, heappush
from itertools import count
from time import perf_counter
from typing import Dict, Iterable, Sequence, Tuple

import numpy as np

from .base import Coordinate, PlanResult


class AStarPlanner:
    """Four-neighbour A* with stable, documented ordering.

    Neighbours are generated in ``up, down, left, right`` order. Heap entries
    are ordered by ``(f, h, g, row, column, insertion_order)``. Consequently,
    equal-cost symmetric choices are resolved by row, then column, then the
    stable insertion counter; no set or random iteration decides a route.
    """

    _NEIGHBOURS: Tuple[Coordinate, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

    def plan(
        self, map_belief: np.ndarray, start: Coordinate, goal: Coordinate
    ) -> PlanResult:
        started = perf_counter()
        grid = np.asarray(map_belief)
        if grid.ndim != 2:
            return self._failure("invalid_map", started)
        if not self._in_bounds(grid, start):
            return self._failure("invalid_start", started)
        if not self._in_bounds(grid, goal):
            return self._failure("invalid_goal", started)
        if self._blocked(grid, start):
            return self._failure("blocked_start", started)
        if self._blocked(grid, goal):
            return self._failure("blocked_goal", started)
        if start == goal:
            return PlanResult(
                success=True,
                path=(start,),
                cost=0.0,
                expanded_nodes=0,
                failure_reason=None,
                planner_runtime_ms=self._elapsed_ms(started),
            )

        serial = count()
        open_heap: list[tuple[int, int, int, int, int, int, Coordinate]] = []
        start_h = self._manhattan(start, goal)
        heappush(open_heap, (start_h, start_h, 0, start[0], start[1], next(serial), start))
        parent: Dict[Coordinate, Coordinate] = {}
        best_cost: Dict[Coordinate, int] = {start: 0}
        expanded = 0

        while open_heap:
            _, _, g_cost, _, _, _, current = heappop(open_heap)
            if g_cost != best_cost.get(current):
                continue
            expanded += 1
            if current == goal:
                path = self._reconstruct_path(parent, start, goal)
                return PlanResult(
                    success=True,
                    path=path,
                    cost=float(g_cost),
                    expanded_nodes=expanded,
                    failure_reason=None,
                    planner_runtime_ms=self._elapsed_ms(started),
                )
            for neighbour in self._neighbours(grid, current):
                if self._blocked(grid, neighbour):
                    continue
                candidate_cost = g_cost + 1
                if candidate_cost >= best_cost.get(neighbour, float("inf")):
                    continue
                best_cost[neighbour] = candidate_cost
                parent[neighbour] = current
                heuristic = self._manhattan(neighbour, goal)
                heappush(
                    open_heap,
                    (
                        candidate_cost + heuristic,
                        heuristic,
                        candidate_cost,
                        neighbour[0],
                        neighbour[1],
                        next(serial),
                        neighbour,
                    ),
                )
        return self._failure("no_path", started, expanded)

    @staticmethod
    def path_cost(path: Sequence[Coordinate]) -> float:
        return float(max(len(path) - 1, 0)) if path else float("inf")

    def path_is_valid(
        self, path: Sequence[Coordinate], reference_map: np.ndarray
    ) -> bool:
        if not path:
            return False
        grid = np.asarray(reference_map)
        if grid.ndim != 2:
            return False
        previous: Coordinate | None = None
        for coordinate in path:
            if not self._in_bounds(grid, coordinate) or self._blocked(grid, coordinate):
                return False
            if previous is not None and self._manhattan(previous, coordinate) != 1:
                return False
            previous = coordinate
        return True

    def _neighbours(
        self, grid: np.ndarray, coordinate: Coordinate
    ) -> Iterable[Coordinate]:
        row, col = coordinate
        for row_delta, col_delta in self._NEIGHBOURS:
            candidate = (row + row_delta, col + col_delta)
            if self._in_bounds(grid, candidate):
                yield candidate

    @staticmethod
    def _in_bounds(grid: np.ndarray, coordinate: Coordinate) -> bool:
        row, col = coordinate
        return 0 <= row < grid.shape[0] and 0 <= col < grid.shape[1]

    @staticmethod
    def _blocked(grid: np.ndarray, coordinate: Coordinate) -> bool:
        return bool(grid[coordinate] == 1)

    @staticmethod
    def _manhattan(left: Coordinate, right: Coordinate) -> int:
        return abs(left[0] - right[0]) + abs(left[1] - right[1])

    @staticmethod
    def _reconstruct_path(
        parent: Dict[Coordinate, Coordinate], start: Coordinate, goal: Coordinate
    ) -> Tuple[Coordinate, ...]:
        reverse_path = [goal]
        current = goal
        while current != start:
            current = parent[current]
            reverse_path.append(current)
        return tuple(reversed(reverse_path))

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return (perf_counter() - started) * 1000.0

    def _failure(self, reason: str, started: float, expanded: int = 0) -> PlanResult:
        return PlanResult(
            success=False,
            path=(),
            cost=float("inf"),
            expanded_nodes=expanded,
            failure_reason=reason,
            planner_runtime_ms=self._elapsed_ms(started),
        )
