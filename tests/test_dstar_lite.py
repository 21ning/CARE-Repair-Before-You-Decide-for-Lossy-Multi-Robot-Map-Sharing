from __future__ import annotations

import numpy as np

from cmvr.planning import AStarPlanner, DStarLitePlanner


def test_dstar_lite_matches_astar_shortest_cost() -> None:
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[2:8, 4] = 1
    grid[5, 4] = 0
    start, goal = (7, 1), (1, 7)
    astar = AStarPlanner().plan(grid, start, goal)
    dstar = DStarLitePlanner().plan(grid, start, goal)
    assert dstar.success
    assert dstar.cost == astar.cost
    assert DStarLitePlanner().path_is_valid(dstar.path, grid)


def test_dstar_lite_repairs_state_after_map_change_and_start_motion() -> None:
    grid = np.zeros((7, 9), dtype=np.int8)
    planner = DStarLitePlanner()
    first = planner.plan(grid, (3, 1), (3, 7))
    assert first.success

    changed = grid.copy()
    changed[3, 4] = 1
    second = planner.plan(changed, first.path[1], (3, 7))
    reference = AStarPlanner().plan(changed, first.path[1], (3, 7))
    assert second.success
    assert second.cost == reference.cost
    assert (3, 4) not in second.path


def test_dstar_lite_is_deterministic() -> None:
    grid = np.zeros((6, 6), dtype=np.int8)
    left = DStarLitePlanner().plan(grid, (5, 0), (0, 5))
    right = DStarLitePlanner().plan(grid, (5, 0), (0, 5))
    assert left.path == right.path
