from __future__ import annotations

from cmvr.communication import (
    deadline_decision_repair_plan, first_path_divergence, full_replica_chunk,
    ordered_digest_peers, planning_corridor, replica_digest,
)
from cmvr.mapping import BeliefMap, MapUpdate


def test_planning_corridor_is_canonical_and_manhattan_dilated() -> None:
    cells = planning_corridor(((1, 1), (1, 2), (1, 3)), (5, 5), horizon=1, radius=1)
    assert cells == ((0, 2), (1, 1), (1, 2), (1, 3), (2, 2))


def test_deadline_plan_derives_slack_and_queries_only_unknown_witnesses() -> None:
    belief = BeliefMap((7, 7))
    for y in (1, 2):
        belief.apply_update(MapUpdate.create(
            sender_id=0, x=3, y=y, cell_state=0, version=1, observed_at=0,
        ))
    optimistic = ((3, 1), (3, 2), (3, 3), (3, 4), (3, 5))
    pessimistic = ((3, 1), (3, 2), (2, 2), (2, 3), (2, 4), (3, 4), (3, 5))
    plan = deadline_decision_repair_plan(
        belief, optimistic, pessimistic, round_trip_steps=1,
        max_horizon=8, max_cells=12,
    )
    assert first_path_divergence(optimistic, pessimistic) == 1
    assert plan.ambiguous and plan.feasible
    assert plan.decision_slack_steps == 1
    assert (3, 3) in plan.cells
    assert all(int(belief.occupancy[cell]) < 0 for cell in plan.cells)


def test_deadline_plan_suppresses_repairs_that_cannot_arrive_in_time() -> None:
    belief = BeliefMap((5, 5))
    plan = deadline_decision_repair_plan(
        belief, ((2, 1), (2, 2), (2, 3)), ((2, 1), (1, 1), (1, 2)),
        round_trip_steps=2, max_horizon=8, max_cells=12,
    )
    assert plan.ambiguous and not plan.feasible
    assert plan.decision_slack_steps == 0
    assert plan.cells == ()


def test_full_replica_chunks_cover_the_domain_without_oversized_digest() -> None:
    chunks = [full_replica_chunk((3, 4), max_cells=5, phase=phase) for phase in range(3)]
    assert all(1 <= len(chunk) <= 5 for chunk in chunks)
    assert set().union(*map(set, chunks)) == {(x, y) for x in range(3) for y in range(4)}
    assert full_replica_chunk((3, 4), max_cells=5, phase=3) == chunks[0]


def test_digest_peer_order_uses_online_distance_then_rotates_ties() -> None:
    positions = ((5, 5), (5, 4), (5, 6), (8, 5))
    assert ordered_digest_peers(requester_id=0, positions=positions, phase=0, limit=1) == (1,)
    assert ordered_digest_peers(requester_id=0, positions=positions, phase=1, limit=1) == (2,)


def test_replica_digest_changes_when_any_known_stamp_or_state_changes() -> None:
    belief = BeliefMap((4, 4))
    initial = replica_digest(belief)
    belief.apply_update(MapUpdate.create(sender_id=1, x=2, y=3, cell_state=1, version=1, observed_at=2))
    assert replica_digest(belief) != initial
