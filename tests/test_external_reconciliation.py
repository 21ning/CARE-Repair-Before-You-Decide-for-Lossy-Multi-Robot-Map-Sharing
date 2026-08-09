from __future__ import annotations

from cmvr.communication import (
    DeltaPayload, MerkleTree, build_iblt, encode_delta, peel_iblt,
    record_scuttle_update, scuttle_depth_updates, scuttle_max_versions,
    scuttle_version, subtract_iblt,
)
from cmvr.mapping import BeliefMap, CellState, MapUpdate


def _update(
    sender_id: int, x: int, y: int, observed_at: int,
    *, state: CellState = CellState.BLOCKED,
) -> MapUpdate:
    return MapUpdate.create(
        sender_id=sender_id, x=x, y=y, cell_state=state,
        version=1, observed_at=observed_at,
    )


def test_scuttle_depth_preserves_per_source_progress_under_truncation() -> None:
    archive: dict[int, dict[tuple[int, int], MapUpdate]] = {}
    source_zero = (
        _update(0, 0, 0, 0),
        _update(0, 0, 1, 0),
        _update(0, 1, 0, 1),
    )
    source_one = (_update(1, 4, 4, 0),)
    for update in source_zero + source_one:
        assert record_scuttle_update(archive, update, map_width=8)

    ordered = scuttle_depth_updates(
        archive, (0, 0), map_width=8, tie_seed="test-exchange",
    )

    # Depth scheduling completes the source with the deepest backlog first.
    assert ordered[:3] == source_zero
    assert ordered[3:] == source_one
    assert [scuttle_version(update, 8) for update in ordered[:3]] == sorted(
        scuttle_version(update, 8) for update in source_zero
    )
    maxima = scuttle_max_versions(archive, source_count=2, map_width=8)
    assert maxima == (
        scuttle_version(source_zero[-1], 8),
        scuttle_version(source_one[-1], 8),
    )


def test_scuttle_archive_keeps_newest_current_mapping_per_origin_and_key() -> None:
    archive: dict[int, dict[tuple[int, int], MapUpdate]] = {}
    old = _update(0, 2, 2, 1, state=CellState.FREE)
    new = _update(0, 2, 2, 3, state=CellState.BLOCKED)

    assert record_scuttle_update(archive, new, map_width=8)
    assert not record_scuttle_update(archive, old, map_width=8)
    assert archive[0][(2, 2)] == new


def test_merkle_tree_localizes_one_changed_map_cell() -> None:
    left = BeliefMap((5, 5))
    right = BeliefMap((5, 5))
    changed = _update(2, 3, 1, 7)
    assert right.apply_update(changed)
    left_tree = MerkleTree(left)
    right_tree = MerkleTree(right)

    assert left_tree.digest(1) != right_tree.digest(1)
    node = 1
    while not left_tree.is_leaf(node):
        mismatches = [
            child for child in left_tree.children(node)
            if left_tree.digest(child) != right_tree.digest(child)
        ]
        assert len(mismatches) == 1
        node = mismatches[0]
    assert left_tree.cell(node) == (changed.x, changed.y)


def test_iblt_subtraction_recovers_both_sides_of_small_set_difference() -> None:
    first = encode_delta(DeltaPayload(_update(0, 1, 1, 1)), receiver_id=0)
    shared = encode_delta(DeltaPayload(_update(1, 2, 2, 2)), receiver_id=0)
    second = encode_delta(DeltaPayload(_update(2, 3, 3, 3)), receiver_id=0)
    parameters = dict(cell_count=31, hash_count=3, hash_seed=17)

    difference = subtract_iblt(
        build_iblt((first, shared), **parameters),
        build_iblt((shared, second), **parameters),
    )
    success, positive, negative = peel_iblt(difference)

    assert success
    assert set(positive) == {first}
    assert set(negative) == {second}
