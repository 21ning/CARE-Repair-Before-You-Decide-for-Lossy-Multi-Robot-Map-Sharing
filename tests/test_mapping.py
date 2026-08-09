from __future__ import annotations

import numpy as np
import pytest

from cmvr.mapping import (
    BeliefMap,
    CellState,
    DeltaEncoder,
    MapUpdate,
    PlanningMapAdapter,
)


def test_unknown_is_distinct_from_free_and_planning_policy_is_explicit() -> None:
    belief = BeliefMap((3, 3))
    assert belief.occupancy[0, 0] == CellState.UNKNOWN
    update = MapUpdate.create(sender_id=0, x=0, y=0, cell_state=CellState.FREE, version=1, observed_at=0)
    assert belief.apply_update(update)
    assert belief.occupancy[0, 0] == CellState.FREE
    assert belief.known_mask[0, 0]
    assert not belief.known_mask[1, 1]
    assert PlanningMapAdapter("optimistic").to_planning_map(belief)[1, 1] == 0
    assert PlanningMapAdapter("pessimistic").to_planning_map(belief)[1, 1] == 1
    assert PlanningMapAdapter("penalized_unknown", unknown_penalty=2.5).traversal_costs(belief)[1, 1] == 2.5


def test_local_observation_coordinate_conversion_and_bounds() -> None:
    belief = BeliefMap((5, 5))
    local = np.array([[1, 0, 1], [0, 0, 1], [1, 0, 0]], dtype=np.uint8)
    updates = belief.integrate_local_observation(local, (2, 2), sender_id=4, observed_at=9)
    assert len(updates) == 9
    by_position = {(update.x, update.y): update for update in updates}
    assert by_position[(1, 1)].cell_state == CellState.BLOCKED
    assert by_position[(2, 2)].cell_state == CellState.FREE
    edge_belief = BeliefMap((2, 2))
    edge_updates = edge_belief.integrate_local_observation(local, (0, 0), sender_id=1, observed_at=1)
    assert {(update.x, update.y) for update in edge_updates} == {(0, 0), (0, 1), (1, 0), (1, 1)}
    with pytest.raises(IndexError):
        edge_belief.apply_update(MapUpdate.create(sender_id=0, x=4, y=4, cell_state=CellState.FREE, version=1, observed_at=1))


def test_beliefs_and_clones_never_alias() -> None:
    first, second = BeliefMap((3, 3)), BeliefMap((3, 3))
    first.apply_update(MapUpdate.create(sender_id=0, x=1, y=1, cell_state=CellState.BLOCKED, version=1, observed_at=1))
    assert second.occupancy[1, 1] == CellState.UNKNOWN
    clone = first.clone()
    clone.apply_update(MapUpdate.create(sender_id=0, x=1, y=1, cell_state=CellState.FREE, version=2, observed_at=2))
    assert first.occupancy[1, 1] == CellState.BLOCKED
    assert clone.occupancy[1, 1] == CellState.FREE


def test_update_ids_are_deterministic() -> None:
    first = MapUpdate.create(sender_id=2, x=1, y=3, cell_state=CellState.FREE, version=1, observed_at=5)
    assert first == MapUpdate.create(sender_id=2, x=1, y=3, cell_state=CellState.FREE, version=1, observed_at=5)
    newer = MapUpdate.create(sender_id=2, x=1, y=3, cell_state=CellState.BLOCKED, version=2, observed_at=6)
    assert first.update_id != newer.update_id


def test_same_version_conflict_resolves_deterministically() -> None:
    belief = BeliefMap((2, 2))
    lower = MapUpdate.create(sender_id=1, x=0, y=0, cell_state=CellState.FREE, version=1, observed_at=1)
    higher = MapUpdate.create(sender_id=2, x=0, y=0, cell_state=CellState.BLOCKED, version=1, observed_at=1)
    belief.apply_update(lower)
    assert belief.apply_update(higher)
    assert belief.occupancy[0, 0] == CellState.BLOCKED
