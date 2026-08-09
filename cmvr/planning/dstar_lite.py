"""Deterministic incremental D* Lite for four-neighbour occupancy grids."""

from __future__ import annotations

from heapq import heappop, heappush
from itertools import count
from math import inf
from time import perf_counter
from typing import Iterable, Sequence

import numpy as np

from .base import Coordinate, PlanResult


class DStarLitePlanner:
    """Incrementally repair shortest paths as a robot moves and its map changes.

    One instance represents one receiver/goal/map stream.  Calls with the same
    grid shape and goal reuse ``g``/``rhs`` values; changed occupancy cells are
    propagated through the D* Lite update equations instead of rebuilding the
    search from scratch.  Heap and path-extraction ties are resolved by row and
    column, making repeated runs bit-for-bit deterministic.
    """

    _NEIGHBOURS: tuple[Coordinate, ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))

    def __init__(self) -> None:
        self._grid: np.ndarray | None = None
        self._goal: Coordinate | None = None
        self._start: Coordinate | None = None
        self._last_start: Coordinate | None = None
        self._km = 0.0
        self._g: dict[Coordinate, float] = {}
        self._rhs: dict[Coordinate, float] = {}
        self._queue: list[tuple[float, float, int, int, int, Coordinate]] = []
        self._queued_key: dict[Coordinate, tuple[float, float]] = {}
        self._serial = count()

    def plan(
        self, map_belief: np.ndarray, start: Coordinate, goal: Coordinate,
    ) -> PlanResult:
        started = perf_counter()
        grid = np.asarray(map_belief, dtype=np.int8)
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
            self._initialize(grid, start, goal)
            return PlanResult(True, (start,), 0.0, 0, None, self._elapsed_ms(started))

        if self._must_reinitialize(grid, goal):
            self._initialize(grid, start, goal)
        else:
            assert self._grid is not None and self._last_start is not None
            self._km += self._manhattan(self._last_start, start)
            self._start = start
            self._last_start = start
            changed = tuple(map(tuple, np.argwhere(self._grid != grid)))
            self._grid = grid.copy()
            affected: set[Coordinate] = set(changed)
            for cell in changed:
                affected.update(self._neighbours(self._grid, cell))
            for cell in sorted(affected):
                self._update_vertex(cell)

        expanded = self._compute_shortest_path()
        if self._value(self._g, start) == inf:
            return self._failure("no_path", started, expanded)
        path = self._extract_path(start, goal)
        if not path:
            return self._failure("no_path", started, expanded)
        return PlanResult(
            True, path, self.path_cost(path), expanded, None,
            self._elapsed_ms(started),
        )

    @staticmethod
    def path_cost(path: Sequence[Coordinate]) -> float:
        return float(max(len(path) - 1, 0)) if path else inf

    def path_is_valid(
        self, path: Sequence[Coordinate], reference_map: np.ndarray,
    ) -> bool:
        if not path:
            return False
        grid = np.asarray(reference_map)
        previous: Coordinate | None = None
        for coordinate in path:
            if not self._in_bounds(grid, coordinate) or self._blocked(grid, coordinate):
                return False
            if previous is not None and self._manhattan(previous, coordinate) != 1:
                return False
            previous = coordinate
        return True

    def _must_reinitialize(self, grid: np.ndarray, goal: Coordinate) -> bool:
        return (
            self._grid is None or self._grid.shape != grid.shape
            or self._goal != goal or self._last_start is None
        )

    def _initialize(
        self, grid: np.ndarray, start: Coordinate, goal: Coordinate,
    ) -> None:
        self._grid = grid.copy()
        self._goal = goal
        self._start = start
        self._last_start = start
        self._km = 0.0
        self._g.clear()
        self._rhs = {goal: 0.0}
        self._queue.clear()
        self._queued_key.clear()
        self._serial = count()
        self._push(goal, self._calculate_key(goal))

    def _calculate_key(self, cell: Coordinate) -> tuple[float, float]:
        assert self._start is not None
        best = min(self._value(self._g, cell), self._value(self._rhs, cell))
        return best + self._manhattan(self._start, cell) + self._km, best

    def _push(self, cell: Coordinate, key: tuple[float, float]) -> None:
        self._queued_key[cell] = key
        heappush(self._queue, (*key, cell[0], cell[1], next(self._serial), cell))

    def _remove(self, cell: Coordinate) -> None:
        self._queued_key.pop(cell, None)

    def _top_key(self) -> tuple[float, float]:
        self._discard_stale()
        return self._queue[0][:2] if self._queue else (inf, inf)

    def _pop(self) -> tuple[tuple[float, float], Coordinate]:
        self._discard_stale()
        first, second, _, _, _, cell = heappop(self._queue)
        self._queued_key.pop(cell, None)
        return (first, second), cell

    def _discard_stale(self) -> None:
        while self._queue:
            first, second, _, _, _, cell = self._queue[0]
            if self._queued_key.get(cell) == (first, second):
                return
            heappop(self._queue)

    def _update_vertex(self, cell: Coordinate) -> None:
        assert self._grid is not None and self._goal is not None
        if cell != self._goal:
            if self._blocked(self._grid, cell):
                self._rhs[cell] = inf
            else:
                self._rhs[cell] = min(
                    (self._edge_cost(cell, successor) + self._value(self._g, successor)
                     for successor in self._neighbours(self._grid, cell)),
                    default=inf,
                )
        self._remove(cell)
        if self._value(self._g, cell) != self._value(self._rhs, cell):
            self._push(cell, self._calculate_key(cell))

    def _compute_shortest_path(self) -> int:
        assert self._start is not None and self._grid is not None
        expanded = 0
        while (
            self._top_key() < self._calculate_key(self._start)
            or self._value(self._rhs, self._start) != self._value(self._g, self._start)
        ):
            old_key, cell = self._pop()
            new_key = self._calculate_key(cell)
            if old_key < new_key:
                self._push(cell, new_key)
            elif self._value(self._g, cell) > self._value(self._rhs, cell):
                self._g[cell] = self._value(self._rhs, cell)
                expanded += 1
                for predecessor in self._neighbours(self._grid, cell):
                    self._update_vertex(predecessor)
            else:
                self._g[cell] = inf
                expanded += 1
                self._update_vertex(cell)
                for predecessor in self._neighbours(self._grid, cell):
                    self._update_vertex(predecessor)
        return expanded

    def _extract_path(
        self, start: Coordinate, goal: Coordinate,
    ) -> tuple[Coordinate, ...]:
        assert self._grid is not None
        path = [start]
        current = start
        seen = {start}
        while current != goal:
            choices = [
                (self._edge_cost(current, cell) + self._value(self._g, cell),
                 self._manhattan(cell, goal), cell[0], cell[1], cell)
                for cell in self._neighbours(self._grid, current)
                if not self._blocked(self._grid, cell)
            ]
            if not choices:
                return ()
            value, _, _, _, successor = min(choices)
            if value == inf or successor in seen:
                return ()
            path.append(successor)
            seen.add(successor)
            current = successor
        return tuple(path)

    def _edge_cost(self, left: Coordinate, right: Coordinate) -> float:
        assert self._grid is not None
        return inf if self._blocked(self._grid, left) or self._blocked(self._grid, right) else 1.0

    def _neighbours(
        self, grid: np.ndarray, coordinate: Coordinate,
    ) -> Iterable[Coordinate]:
        row, col = coordinate
        for row_delta, col_delta in self._NEIGHBOURS:
            candidate = row + row_delta, col + col_delta
            if self._in_bounds(grid, candidate):
                yield candidate

    @staticmethod
    def _value(table: dict[Coordinate, float], cell: Coordinate) -> float:
        return table.get(cell, inf)

    @staticmethod
    def _in_bounds(grid: np.ndarray, coordinate: Coordinate) -> bool:
        return 0 <= coordinate[0] < grid.shape[0] and 0 <= coordinate[1] < grid.shape[1]

    @staticmethod
    def _blocked(grid: np.ndarray, coordinate: Coordinate) -> bool:
        return bool(grid[coordinate] == 1)

    @staticmethod
    def _manhattan(left: Coordinate, right: Coordinate) -> int:
        return abs(left[0] - right[0]) + abs(left[1] - right[1])

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return (perf_counter() - started) * 1_000.0

    def _failure(self, reason: str, started: float, expanded: int = 0) -> PlanResult:
        return PlanResult(False, (), inf, expanded, reason, self._elapsed_ms(started))
