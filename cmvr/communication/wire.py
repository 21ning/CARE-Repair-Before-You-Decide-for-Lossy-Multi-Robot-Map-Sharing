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
