from __future__ import annotations

import pytest

from cmvr.communication import (
    ACK_BYTES, DELTA_BYTES, DIGEST_ENTRY_BYTES, DIGEST_HEADER_BYTES,
    IBLT_CELL_BYTES, IBLT_HEADER_BYTES, MERKLE_CHILDREN_HEADER_BYTES,
    MERKLE_MATCH_BYTES, MERKLE_PROBE_BYTES, PATCH_HEADER_BYTES, REPLICA_DIGEST_BYTES,
    SCUTTLE_DIGEST_ENTRY_BYTES, SCUTTLE_DIGEST_HEADER_BYTES,
    DeltaPayload, DigestQuery, IBLTCell, IBLTSketch, MerkleChildren,
    MerkleMatch, MerkleProbe, PatchPayload, ScuttleDigest, WireFormatError, ack_token,
    decode_ack, decode_delta, decode_digest_query, decode_iblt_sketch,
    decode_merkle_children, decode_merkle_match, decode_merkle_probe, decode_patch,
    decode_replica_digest, decode_scuttle_digest, encode_ack, encode_delta,
    encode_digest_query, encode_iblt_sketch, encode_merkle_children,
    encode_merkle_match, encode_merkle_probe, encode_patch, encode_replica_digest,
    encode_scuttle_digest, replica_digest,
)
from cmvr.mapping import BeliefMap, CellState, MapUpdate


def _update(*, sender_id: int = 3, x: int = 17, y: int = 29) -> MapUpdate:
    return MapUpdate.create(
        sender_id=sender_id, x=x, y=y, cell_state=CellState.BLOCKED,
        version=19, observed_at=42,
    )


def test_delta_round_trip_reconstructs_id_flags_and_exact_length() -> None:
    update = _update()
    payload = DeltaPayload(update, task_key=(update.update_id, 7), is_repair=True)
    encoded = encode_delta(payload, receiver_id=7)

    assert len(encoded) == DELTA_BYTES == update.encoded_size_bytes
    assert update.update_id.encode() not in encoded
    assert decode_delta(encoded, receiver_id=7) == payload


def test_delta_rejects_corruption_and_unrepresentable_coordinates() -> None:
    encoded = bytearray(encode_delta(DeltaPayload(_update()), receiver_id=1))
    encoded[5] ^= 1
    with pytest.raises(WireFormatError, match="CRC"):
        decode_delta(bytes(encoded), receiver_id=1)
    with pytest.raises(WireFormatError, match="x=256"):
        encode_delta(DeltaPayload(_update(x=256)), receiver_id=1)


def test_digest_round_trip_packs_complete_stamps_into_six_bytes_each() -> None:
    payload = DigestQuery(
        cells=((0, 1), (63, 63)),
        requester_stamps=(
            (0, -1, -1, int(CellState.UNKNOWN)),
            (255, 64, 31, int(CellState.BLOCKED)),
        ),
        regional_only=True,
        action_only=False,
    )
    encoded = encode_digest_query(payload)

    assert len(encoded) == DIGEST_HEADER_BYTES + 2 * DIGEST_ENTRY_BYTES
    assert decode_digest_query(encoded) == payload


def test_digest_rejects_reserved_bits_and_out_of_range_cells() -> None:
    payload = DigestQuery(((0, 0),), ((0, -1, -1, -1),))
    encoded = bytearray(encode_digest_query(payload))
    encoded[DIGEST_HEADER_BYTES] |= 0xF0
    with pytest.raises(WireFormatError, match="reserved bits"):
        decode_digest_query(bytes(encoded))
    with pytest.raises(WireFormatError, match="digest x=64"):
        encode_digest_query(DigestQuery(((64, 0),), ((0, -1, -1, -1),)))


def test_patch_round_trip_has_four_byte_header_and_thirteen_byte_cells() -> None:
    payload = PatchPayload((_update(), _update(sender_id=4, x=2, y=5)))
    encoded = encode_patch(payload)

    assert len(encoded) == PATCH_HEADER_BYTES + 2 * DELTA_BYTES
    assert decode_patch(encoded) == payload


def test_ack_and_replica_digest_have_real_fixed_width_encodings() -> None:
    update = _update()
    key = update.update_id, 7
    encoded_ack = encode_ack(key)
    assert len(encoded_ack) == ACK_BYTES
    assert decode_ack(encoded_ack) == ack_token(key)

    belief = BeliefMap((4, 4))
    belief.apply_update(_update(x=2, y=3))
    encoded_digest = encode_replica_digest(replica_digest(belief))
    assert len(encoded_digest) == REPLICA_DIGEST_BYTES
    assert decode_replica_digest(encoded_digest) == encoded_digest


def test_scuttle_digest_round_trip_has_exact_dense_version_vector_size() -> None:
    payload = ScuttleDigest((0, 17, 2**32 - 1), reply_requested=False)
    encoded = encode_scuttle_digest(payload)

    assert len(encoded) == SCUTTLE_DIGEST_HEADER_BYTES + 3 * SCUTTLE_DIGEST_ENTRY_BYTES
    assert decode_scuttle_digest(encoded) == payload


def test_merkle_messages_round_trip_with_fixed_hash_widths() -> None:
    probe = MerkleProbe(19, b"a" * 16)
    children = MerkleChildren(9, tuple(bytes((index,)) * 16 for index in range(16)))
    match = MerkleMatch(27)

    encoded_probe = encode_merkle_probe(probe)
    encoded_children = encode_merkle_children(children)
    encoded_match = encode_merkle_match(match)

    assert len(encoded_probe) == MERKLE_PROBE_BYTES
    assert len(encoded_children) == MERKLE_CHILDREN_HEADER_BYTES + 16 * 16
    assert len(encoded_match) == MERKLE_MATCH_BYTES
    assert decode_merkle_probe(encoded_probe) == probe
    assert decode_merkle_children(encoded_children) == children
    assert decode_merkle_match(encoded_match) == match


def test_iblt_round_trip_accounts_for_every_transmitted_cell() -> None:
    cells = (
        IBLTCell(1, b"a" * 13, b"b" * 8),
        IBLTCell(-1, b"c" * 13, b"d" * 8),
        IBLTCell(0, bytes(13), bytes(8)),
    )
    payload = IBLTSketch(hash_count=2, hash_seed=23, cells=cells)
    encoded = encode_iblt_sketch(payload)

    assert len(encoded) == IBLT_HEADER_BYTES + len(cells) * IBLT_CELL_BYTES
    assert decode_iblt_sketch(encoded) == payload
