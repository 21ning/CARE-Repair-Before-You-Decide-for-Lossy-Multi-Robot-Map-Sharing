"""Canonical binary wire codec for every charged protocol payload.

The lossy channel carries these bytes directly. Directed-link addressing and
delivery metadata remain in :class:`NetworkMessage`; every application byte
counted by the experiments is therefore the length of a payload produced here.
"""

from __future__ import annotations

from binascii import crc_hqx
from hashlib import sha256
from struct import Struct

from cmvr.mapping import CellState, MapUpdate

from .external_reconciliation import (
    HASH_BYTES, IBLT_CHECKSUM_BYTES, IBLT_KEY_BYTES, IBLTCell, IBLTSketch,
    MerkleChildren, MerkleMatch, MerkleProbe, ScuttleDigest,
)
from .replica_protocol import (
    DeltaPayload, DigestQuery, PatchPayload, ReplicaDigest, ReplicaStamp,
)


WIRE_VERSION = 1
DELTA_BYTES = 13
DIGEST_HEADER_BYTES = 16
DIGEST_ENTRY_BYTES = 6
PATCH_HEADER_BYTES = 4
ACK_BYTES = 8
REPLICA_DIGEST_BYTES = 16
SCUTTLE_DIGEST_HEADER_BYTES = 4
SCUTTLE_DIGEST_ENTRY_BYTES = 5
MERKLE_PROBE_BYTES = 20
MERKLE_CHILDREN_HEADER_BYTES = 4
MERKLE_MATCH_BYTES = 4
IBLT_HEADER_BYTES = 8
IBLT_CELL_BYTES = 23

_ACK_REQUESTED = 0x01
_IS_REPAIR = 0x02
_DELTA_ALLOWED_FLAGS = _ACK_REQUESTED | _IS_REPAIR
_DIGEST_REGIONAL = 0x01
_DIGEST_ACTION_ONLY = 0x02
_DIGEST_ALLOWED_FLAGS = _DIGEST_REGIONAL | _DIGEST_ACTION_ONLY

_DELTA_BODY = Struct("!BBBBBHI")
_DELTA_CRC = Struct("!H")
_DIGEST_HEADER = Struct("!BBH12x")
_PATCH_HEADER = Struct("!BBH")
_SCUTTLE_HEADER = Struct("!BBH")
_SCUTTLE_ENTRY = Struct("!BI")
_MERKLE_PROBE = Struct("!BBH16s")
_MERKLE_HEADER = Struct("!BBH")
_IBLT_HEADER = Struct("!BBHI")
_IBLT_CELL = Struct("!h13s8s")

_SCUTTLE_REPLY_REQUESTED = 0x01


class WireFormatError(ValueError):
    """Raised when a payload cannot be represented or safely decoded."""


def encode_delta(payload: DeltaPayload, *, receiver_id: int) -> bytes:
    """Encode one versioned cell update into the canonical 13-byte format."""
    update = payload.update
    _bounded("sender_id", update.sender_id, 0, 255)
    _bounded("receiver_id", receiver_id, 0, 255)
    _bounded("x", update.x, 0, 255)
    _bounded("y", update.y, 0, 255)
    _bounded("version", update.version, 0, 65_535)
    _bounded("observed_at", update.observed_at, 0, 2**32 - 1)
    if update.cell_state not in {CellState.FREE, CellState.BLOCKED}:
        raise WireFormatError("delta packets cannot encode UNKNOWN cells")
    if update.encoded_size_bytes != DELTA_BYTES:
        raise WireFormatError(
            f"MapUpdate declares {update.encoded_size_bytes} bytes; wire format requires {DELTA_BYTES}"
        )

    flags = 0
    if payload.task_key is not None:
        if payload.task_key != (update.update_id, receiver_id):
            raise WireFormatError("delta ACK task key does not match update and receiver")
        flags |= _ACK_REQUESTED
    if payload.is_repair:
        flags |= _IS_REPAIR
    header = (WIRE_VERSION << 4) | flags
    body = _DELTA_BODY.pack(
        header, update.sender_id, update.x, update.y, int(update.cell_state),
        update.version, update.observed_at,
    )
    encoded = body + _DELTA_CRC.pack(crc_hqx(body, 0xFFFF))
    assert len(encoded) == DELTA_BYTES
    return encoded


def decode_delta(data: bytes, *, receiver_id: int) -> DeltaPayload:
    """Decode and checksum-validate one canonical cell update."""
    _exact_length("delta", data, DELTA_BYTES)
    body, checksum = data[:-_DELTA_CRC.size], data[-_DELTA_CRC.size:]
    if crc_hqx(body, 0xFFFF) != _DELTA_CRC.unpack(checksum)[0]:
        raise WireFormatError("delta CRC mismatch")
    header, sender_id, x, y, state, version, observed_at = _DELTA_BODY.unpack(body)
    flags = _decode_header(header, _DELTA_ALLOWED_FLAGS, "delta")
    try:
        cell_state = CellState(state)
    except ValueError as error:
        raise WireFormatError(f"invalid delta cell state: {state}") from error
    if cell_state == CellState.UNKNOWN:
        raise WireFormatError("delta packets cannot contain UNKNOWN cells")
    update = MapUpdate.create(
        sender_id=sender_id, x=x, y=y, cell_state=cell_state,
        version=version, observed_at=observed_at,
    )
    task_key = (update.update_id, receiver_id) if flags & _ACK_REQUESTED else None
    return DeltaPayload(update, task_key=task_key, is_repair=bool(flags & _IS_REPAIR))


def encode_digest_query(payload: DigestQuery) -> bytes:
    """Encode a stamped cell query as a 16-byte header plus 6 bytes per cell."""
    if len(payload.cells) != len(payload.requester_stamps):
        raise WireFormatError("digest cells and stamps must have equal length")
    _bounded("digest entry count", len(payload.cells), 0, 65_535)
    flags = (
        (_DIGEST_REGIONAL if payload.regional_only else 0)
        | (_DIGEST_ACTION_ONLY if payload.action_only else 0)
    )
    entries = b"".join(
        _encode_digest_entry(cell, stamp)
        for cell, stamp in zip(payload.cells, payload.requester_stamps)
    )
    encoded = _DIGEST_HEADER.pack(WIRE_VERSION, flags, len(payload.cells)) + entries
    assert len(encoded) == DIGEST_HEADER_BYTES + DIGEST_ENTRY_BYTES * len(payload.cells)
    return encoded


def decode_digest_query(data: bytes) -> DigestQuery:
    """Decode a stamped regional query and reject non-canonical headers."""
    if len(data) < DIGEST_HEADER_BYTES:
        raise WireFormatError("digest query is shorter than its header")
    version, flags, count = _DIGEST_HEADER.unpack(data[:DIGEST_HEADER_BYTES])
    if version != WIRE_VERSION:
        raise WireFormatError(f"unsupported digest wire version: {version}")
    if flags & ~_DIGEST_ALLOWED_FLAGS:
        raise WireFormatError(f"digest contains reserved flags: 0x{flags:02x}")
    if any(data[4:DIGEST_HEADER_BYTES]):
        raise WireFormatError("digest reserved header bytes must be zero")
    expected = DIGEST_HEADER_BYTES + count * DIGEST_ENTRY_BYTES
    _exact_length("digest query", data, expected)
    cells = []
    stamps = []
    for offset in range(DIGEST_HEADER_BYTES, expected, DIGEST_ENTRY_BYTES):
        cell, stamp = _decode_digest_entry(data[offset:offset + DIGEST_ENTRY_BYTES])
        cells.append(cell)
        stamps.append(stamp)
    return DigestQuery(
        tuple(cells), tuple(stamps),
        regional_only=bool(flags & _DIGEST_REGIONAL),
        action_only=bool(flags & _DIGEST_ACTION_ONLY),
    )


def encode_patch(payload: PatchPayload) -> bytes:
    """Encode a patch as a 4-byte header followed by canonical cell deltas."""
    _bounded("patch update count", len(payload.updates), 0, 65_535)
    encoded_updates = b"".join(
        encode_delta(DeltaPayload(update), receiver_id=0)
        for update in payload.updates
    )
    encoded = _PATCH_HEADER.pack(WIRE_VERSION, 0, len(payload.updates)) + encoded_updates
    assert len(encoded) == PATCH_HEADER_BYTES + DELTA_BYTES * len(payload.updates)
    return encoded


def decode_patch(data: bytes) -> PatchPayload:
    """Decode every cell in a canonical patch."""
    if len(data) < PATCH_HEADER_BYTES:
        raise WireFormatError("patch is shorter than its header")
    version, flags, count = _PATCH_HEADER.unpack(data[:PATCH_HEADER_BYTES])
    if version != WIRE_VERSION:
        raise WireFormatError(f"unsupported patch wire version: {version}")
    if flags:
        raise WireFormatError("patch reserved flags must be zero")
    expected = PATCH_HEADER_BYTES + count * DELTA_BYTES
    _exact_length("patch", data, expected)
    updates = tuple(
        decode_delta(data[offset:offset + DELTA_BYTES], receiver_id=0).update
        for offset in range(PATCH_HEADER_BYTES, expected, DELTA_BYTES)
    )
    return PatchPayload(updates)


def ack_token(task_key: tuple[str, int]) -> bytes:
    """Return the transmitted 64-bit token for a deterministic delivery task."""
    update_id, receiver_id = task_key
    try:
        update_digest = bytes.fromhex(update_id)
    except ValueError as error:
        raise WireFormatError("ACK task update_id must be hexadecimal") from error
    if len(update_digest) != 32:
        raise WireFormatError("ACK task update_id must be one SHA-256 digest")
    _bounded("ACK receiver_id", receiver_id, 0, 255)
    return sha256(update_digest + bytes((receiver_id,))).digest()[:ACK_BYTES]


def encode_ack(task_key: tuple[str, int]) -> bytes:
    return ack_token(task_key)


def decode_ack(data: bytes) -> bytes:
    _exact_length("ACK", data, ACK_BYTES)
    return data


def encode_replica_digest(payload: ReplicaDigest) -> bytes:
    """Transmit the first 128 bits of the canonical SHA-256 replica digest."""
    try:
        digest = bytes.fromhex(payload.digest)
    except ValueError as error:
        raise WireFormatError("replica digest must be hexadecimal") from error
    if len(digest) != 32:
        raise WireFormatError("replica digest must contain 256 bits before truncation")
    return digest[:REPLICA_DIGEST_BYTES]


def decode_replica_digest(data: bytes) -> bytes:
    _exact_length("replica digest", data, REPLICA_DIGEST_BYTES)
    return data


def encode_scuttle_digest(payload: ScuttleDigest) -> bytes:
    """Encode one maximum version per update origin."""
    _bounded("Scuttlebutt source count", len(payload.max_versions), 0, 65_535)
    flags = _SCUTTLE_REPLY_REQUESTED if payload.reply_requested else 0
    entries = []
    for source_id, maximum in enumerate(payload.max_versions):
        _bounded("Scuttlebutt source id", source_id, 0, 255)
        _bounded("Scuttlebutt maximum version", maximum, 0, 2**32 - 1)
        entries.append(_SCUTTLE_ENTRY.pack(source_id, maximum))
    encoded = _SCUTTLE_HEADER.pack(WIRE_VERSION, flags, len(entries)) + b"".join(entries)
    assert len(encoded) == SCUTTLE_DIGEST_HEADER_BYTES + SCUTTLE_DIGEST_ENTRY_BYTES * len(entries)
    return encoded


def decode_scuttle_digest(data: bytes) -> ScuttleDigest:
    """Decode a dense, canonically source-ordered Scuttlebutt digest."""
    if len(data) < SCUTTLE_DIGEST_HEADER_BYTES:
        raise WireFormatError("Scuttlebutt digest is shorter than its header")
    version, flags, count = _SCUTTLE_HEADER.unpack(data[:SCUTTLE_DIGEST_HEADER_BYTES])
    if version != WIRE_VERSION:
        raise WireFormatError(f"unsupported Scuttlebutt wire version: {version}")
    if flags & ~_SCUTTLE_REPLY_REQUESTED:
        raise WireFormatError(f"Scuttlebutt digest contains reserved flags: 0x{flags:02x}")
    expected = SCUTTLE_DIGEST_HEADER_BYTES + count * SCUTTLE_DIGEST_ENTRY_BYTES
    _exact_length("Scuttlebutt digest", data, expected)
    maxima = []
    for source_id, offset in enumerate(
        range(SCUTTLE_DIGEST_HEADER_BYTES, expected, SCUTTLE_DIGEST_ENTRY_BYTES)
    ):
        encoded_source, maximum = _SCUTTLE_ENTRY.unpack(
            data[offset:offset + SCUTTLE_DIGEST_ENTRY_BYTES]
        )
        if encoded_source != source_id:
            raise WireFormatError("Scuttlebutt digest sources are not canonical")
        maxima.append(maximum)
    return ScuttleDigest(tuple(maxima), bool(flags & _SCUTTLE_REPLY_REQUESTED))


def encode_merkle_probe(payload: MerkleProbe) -> bytes:
    _bounded("Merkle node index", payload.node_index, 1, 65_535)
    if len(payload.digest) != HASH_BYTES:
        raise WireFormatError("Merkle probe hash has the wrong width")
    return _MERKLE_PROBE.pack(WIRE_VERSION, 0, payload.node_index, payload.digest)


def decode_merkle_probe(data: bytes) -> MerkleProbe:
    _exact_length("Merkle probe", data, MERKLE_PROBE_BYTES)
    version, flags, node_index, digest = _MERKLE_PROBE.unpack(data)
    if version != WIRE_VERSION or flags:
        raise WireFormatError("invalid Merkle probe header")
    if node_index < 1:
        raise WireFormatError("Merkle node indices start at one")
    return MerkleProbe(node_index, digest)


def encode_merkle_children(payload: MerkleChildren) -> bytes:
    _bounded("Merkle parent index", payload.node_index, 1, 65_535)
    _bounded("Merkle child count", len(payload.digests), 1, 255)
    if any(len(digest) != HASH_BYTES for digest in payload.digests):
        raise WireFormatError("Merkle child hash has the wrong width")
    return _MERKLE_HEADER.pack(
        WIRE_VERSION, len(payload.digests), payload.node_index,
    ) + b"".join(payload.digests)


def decode_merkle_children(data: bytes) -> MerkleChildren:
    if len(data) < MERKLE_CHILDREN_HEADER_BYTES:
        raise WireFormatError("Merkle children are shorter than the header")
    version, child_count, node_index = _MERKLE_HEADER.unpack(
        data[:MERKLE_CHILDREN_HEADER_BYTES]
    )
    if version != WIRE_VERSION or child_count < 1:
        raise WireFormatError("invalid Merkle children header")
    if node_index < 1:
        raise WireFormatError("Merkle node indices start at one")
    expected = MERKLE_CHILDREN_HEADER_BYTES + child_count * HASH_BYTES
    _exact_length("Merkle children", data, expected)
    digests = tuple(
        data[offset:offset + HASH_BYTES]
        for offset in range(MERKLE_CHILDREN_HEADER_BYTES, expected, HASH_BYTES)
    )
    return MerkleChildren(node_index, digests)


def encode_merkle_match(payload: MerkleMatch) -> bytes:
    _bounded("Merkle match node index", payload.node_index, 1, 65_535)
    return _MERKLE_HEADER.pack(WIRE_VERSION, 0, payload.node_index)


def decode_merkle_match(data: bytes) -> MerkleMatch:
    _exact_length("Merkle match", data, MERKLE_MATCH_BYTES)
    version, flags, node_index = _MERKLE_HEADER.unpack(data)
    if version != WIRE_VERSION or flags or node_index < 1:
        raise WireFormatError("invalid Merkle match header")
    return MerkleMatch(node_index)


def encode_iblt_sketch(payload: IBLTSketch) -> bytes:
    _bounded("IBLT hash count", payload.hash_count, 2, 255)
    _bounded("IBLT cell count", len(payload.cells), payload.hash_count, 65_535)
    body = b"".join(
        _IBLT_CELL.pack(cell.count, cell.key_xor, cell.checksum_xor)
        for cell in payload.cells
    )
    encoded = _IBLT_HEADER.pack(
        WIRE_VERSION, payload.hash_count, len(payload.cells), payload.hash_seed,
    ) + body
    assert len(encoded) == IBLT_HEADER_BYTES + IBLT_CELL_BYTES * len(payload.cells)
    return encoded


def decode_iblt_sketch(data: bytes) -> IBLTSketch:
    if len(data) < IBLT_HEADER_BYTES:
        raise WireFormatError("IBLT sketch is shorter than its header")
    version, hash_count, cell_count, hash_seed = _IBLT_HEADER.unpack(data[:IBLT_HEADER_BYTES])
    if version != WIRE_VERSION:
        raise WireFormatError(f"unsupported IBLT wire version: {version}")
    if hash_count < 2 or cell_count < hash_count:
        raise WireFormatError("invalid IBLT dimensions")
    expected = IBLT_HEADER_BYTES + IBLT_CELL_BYTES * cell_count
    _exact_length("IBLT sketch", data, expected)
    cells = []
    for offset in range(IBLT_HEADER_BYTES, expected, IBLT_CELL_BYTES):
        count, key_xor, checksum_xor = _IBLT_CELL.unpack(
            data[offset:offset + IBLT_CELL_BYTES]
        )
        cells.append(IBLTCell(count, key_xor, checksum_xor))
    return IBLTSketch(hash_count, hash_seed, tuple(cells))


def _encode_digest_entry(cell: tuple[int, int], stamp: ReplicaStamp) -> bytes:
    """Pack x6/y6/version8/time16/source6/state2 into 44 of 48 bits."""
    x, y = cell
    version, observed_at, source_id, state = stamp
    _bounded("digest x", x, 0, 63)
    _bounded("digest y", y, 0, 63)
    _bounded("digest version", version, 0, 255)
    _bounded("digest observed_at", observed_at, -1, 65_534)
    _bounded("digest source_id", source_id, -1, 62)
    try:
        state_code = {
            int(CellState.UNKNOWN): 0,
            int(CellState.FREE): 1,
            int(CellState.BLOCKED): 2,
        }[int(state)]
    except KeyError as error:
        raise WireFormatError(f"invalid digest cell state: {state}") from error
    observed_code = observed_at + 1
    source_code = 63 if source_id == -1 else source_id
    value = x
    for bits, item in (
        (6, y), (8, version), (16, observed_code),
        (6, source_code), (2, state_code),
    ):
        value = (value << bits) | item
    return value.to_bytes(DIGEST_ENTRY_BYTES, "big")


def _decode_digest_entry(data: bytes) -> tuple[tuple[int, int], ReplicaStamp]:
    _exact_length("digest entry", data, DIGEST_ENTRY_BYTES)
    value = int.from_bytes(data, "big")
    if value >> 44:
        raise WireFormatError("digest entry reserved bits must be zero")
    state_code = value & 0x3
    value >>= 2
    source_code = value & 0x3F
    value >>= 6
    observed_code = value & 0xFFFF
    value >>= 16
    version = value & 0xFF
    value >>= 8
    y = value & 0x3F
    value >>= 6
    x = value & 0x3F
    try:
        state = {
            0: int(CellState.UNKNOWN),
            1: int(CellState.FREE),
            2: int(CellState.BLOCKED),
        }[state_code]
    except KeyError as error:
        raise WireFormatError(f"invalid packed digest state: {state_code}") from error
    source_id = -1 if source_code == 63 else source_code
    observed_at = observed_code - 1
    return (x, y), (version, observed_at, source_id, state)


def _decode_header(header: int, allowed_flags: int, name: str) -> int:
    version, flags = header >> 4, header & 0x0F
    if version != WIRE_VERSION:
        raise WireFormatError(f"unsupported {name} wire version: {version}")
    if flags & ~allowed_flags:
        raise WireFormatError(f"{name} contains reserved flags: 0x{flags:02x}")
    return flags


def _bounded(name: str, value: int, low: int, high: int) -> None:
    if not low <= int(value) <= high:
        raise WireFormatError(f"{name}={value} is outside [{low}, {high}]")


def _exact_length(name: str, data: bytes, expected: int) -> None:
    if not isinstance(data, bytes):
        raise WireFormatError(f"{name} payload must be bytes")
    if len(data) != expected:
        raise WireFormatError(f"{name} payload has {len(data)} bytes; expected {expected}")
