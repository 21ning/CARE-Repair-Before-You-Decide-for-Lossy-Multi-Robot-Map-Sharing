from __future__ import annotations

import numpy as np

from cmvr.planning import AStarPlanner


def test_astar_returns_valid_path_and_cost() -> None:
    obstacle_map = np.array(
        [[0, 0, 0, 0], [1, 1, 0, 1], [0, 0, 0, 0], [0, 1, 1, 0]], dtype=np.uint8
    )
    planner = AStarPlanner()
    result = planner.plan(obstacle_map, (0, 0), (3, 3))
    assert result.success
    assert result.path[0] == (0, 0)
    assert result.path[-1] == (3, 3)
    assert result.cost == planner.path_cost(result.path) == 6.0
    assert planner.path_is_valid(result.path, obstacle_map)


def test_astar_is_deterministic_on_symmetric_tie() -> None:
    planner = AStarPlanner()
    obstacle_map = np.zeros((3, 3), dtype=np.uint8)
    first = planner.plan(obstacle_map, (0, 0), (2, 2)).path
    second = planner.plan(obstacle_map, (0, 0), (2, 2)).path
    assert first == second == ((0, 0), (0, 1), (0, 2), (1, 2), (2, 2))


def test_astar_reports_no_path_and_invalid_endpoints() -> None:
    planner = AStarPlanner()
    separated = np.array([[0, 1, 0], [0, 1, 0], [0, 1, 0]], dtype=np.uint8)
    assert planner.plan(separated, (0, 0), (0, 2)).failure_reason == "no_path"
    assert planner.plan(separated, (-1, 0), (0, 2)).failure_reason == "invalid_start"
    assert planner.plan(separated, (0, 0), (3, 2)).failure_reason == "invalid_goal"


def test_astar_does_not_mutate_input_and_validates_paths() -> None:
    planner = AStarPlanner()
    obstacle_map = np.zeros((3, 3), dtype=np.uint8)
    original = obstacle_map.copy()
    planner.plan(obstacle_map, (0, 0), (2, 2))
    assert np.array_equal(obstacle_map, original)
    assert not planner.path_is_valid(((0, 0), (2, 0)), obstacle_map)
    assert not planner.path_is_valid(((0, 0), (0, 1), (1, 1)), np.array([[0, 0], [0, 1]]))
