"""Published replica-reconciliation primitives adapted to versioned map cells.

The module contains no planner or ground-truth access.  Scuttlebutt follows the
per-origin maximum-version invariant and depth ordering of van Renesse et al.
The Merkle tree follows Dynamo's hierarchical difference localization.  The
IBLT is the signed subtract-and-peel construction of Goodrich and Mitzenmacher.
Wire encoding and lossy protocol orchestration live in adjacent modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from cmvr.mapping import BeliefMap, MapUpdate


HASH_BYTES = 16
IBLT_KEY_BYTES = 13
IBLT_CHECKSUM_BYTES = 8


@dataclass(frozen=True)
class ScuttleDigest:
    """Per-origin maximum versions exchanged by Scuttlebutt gossip."""

    max_versions: tuple[int, ...]
    reply_requested: bool = True


@dataclass(frozen=True)
class MerkleProbe:
    """Request comparison of one heap-indexed Merkle node."""

    node_index: int
    digest: bytes


@dataclass(frozen=True)
class MerkleChildren:
    """The child hashes of one mismatching high-fanout Merkle node."""

    node_index: int
    digests: tuple[bytes, ...]

    def __post_init__(self) -> None:
        if not self.digests or any(len(digest) != HASH_BYTES for digest in self.digests):
            raise ValueError("Merkle child hashes have the wrong width")


@dataclass(frozen=True)
class MerkleMatch:
    """Acknowledgement that one probed Merkle node matches."""

    node_index: int


@dataclass(frozen=True)
class IBLTCell:
    """One signed IBLT cell."""

    count: int
    key_xor: bytes
    checksum_xor: bytes

    def __post_init__(self) -> None:
        if len(self.key_xor) != IBLT_KEY_BYTES:
            raise ValueError("IBLT key XOR has the wrong width")
        if len(self.checksum_xor) != IBLT_CHECKSUM_BYTES:
            raise ValueError("IBLT checksum XOR has the wrong width")
        if not -32_768 <= self.count <= 32_767:
            raise ValueError("IBLT count does not fit signed 16 bits")


@dataclass(frozen=True)
class IBLTSketch:
    """Fixed-size IBLT sketch with reproducible hash parameters."""

    hash_count: int
    hash_seed: int
    cells: tuple[IBLTCell, ...]

    def __post_init__(self) -> None:
        if self.hash_count < 2:
            raise ValueError("IBLT requires at least two hash functions")
        if len(self.cells) < self.hash_count:
            raise ValueError("IBLT needs at least one distinct cell per hash")
        if not 0 <= self.hash_seed <= 2**32 - 1:
            raise ValueError("IBLT hash seed must fit 32 bits")


def scuttle_version(update: MapUpdate, map_width: int) -> int:
    """Derive a unique per-origin version from existing transmitted fields.

    Local observations are emitted in row-major order.  Combining their step
    and coordinate therefore yields the strictly increasing per-origin version
    required by Scuttlebutt without adding hidden bytes to the cell record.
    """
    if map_width < 1 or not (0 <= update.x < map_width and 0 <= update.y < map_width):
        raise ValueError("update coordinate is outside the Scuttlebutt map")
    return update.observed_at * map_width * map_width + update.x * map_width + update.y + 1


def record_scuttle_update(
    archive: dict[int, dict[tuple[int, int], MapUpdate]],
    update: MapUpdate,
    *,
    map_width: int,
) -> bool:
    """Keep the newest current mapping for one origin and key."""
    by_key = archive.setdefault(update.sender_id, {})
    cell = update.x, update.y
    current = by_key.get(cell)
    if current is not None and (
        scuttle_version(update, map_width), update.version, int(update.cell_state)
    ) <= (
        scuttle_version(current, map_width), current.version, int(current.cell_state)
    ):
        return False
    by_key[cell] = update
    return True


def scuttle_max_versions(
    archive: dict[int, dict[tuple[int, int], MapUpdate]],
    *,
    source_count: int,
    map_width: int,
) -> tuple[int, ...]:
    """Return the digest ``max(mu_holder(source))`` for every source."""
    maxima = []
    for source in range(source_count):
        updates = archive.get(source, {}).values()
        maxima.append(max((scuttle_version(item, map_width) for item in updates), default=0))
    return tuple(maxima)


def scuttle_depth_updates(
    archive: dict[int, dict[tuple[int, int], MapUpdate]],
    requester_max_versions: tuple[int, ...],
    *,
    map_width: int,
    tie_seed: str,
) -> tuple[MapUpdate, ...]:
    """Order missing mappings using the paper's Scuttlebutt-depth policy.

    Origins with the largest number of available deltas are served first.
    Ties use a deterministic exchange-specific pseudo-random order; versions
    within an origin are oldest first so an MTU truncation preserves the
    Scuttlebutt invariant.
    """
    candidates: dict[int, list[MapUpdate]] = {}
    for source, maximum in enumerate(requester_max_versions):
        available = [
            update for update in archive.get(source, {}).values()
            if scuttle_version(update, map_width) > maximum
        ]
        if available:
            candidates[source] = sorted(
                available,
                key=lambda update: (
                    scuttle_version(update, map_width), update.x, update.y,
                ),
            )
    source_order = sorted(
        candidates,
        key=lambda source: (
            -len(candidates[source]),
            sha256(f"{tie_seed}|{source}".encode("utf-8")).digest(),
        ),
    )
    return tuple(update for source in source_order for update in candidates[source])


class MerkleTree:
    """Deterministic complete high-fanout hash tree over one explicit replica."""

    def __init__(self, belief: BeliefMap, *, fanout: int = 16) -> None:
        if fanout < 2:
            raise ValueError("Merkle fanout must be at least two")
        self.shape = belief.shape
        self.fanout = fanout
        self.item_count = belief.shape[0] * belief.shape[1]
        self.leaf_count = 1
        while self.leaf_count < self.item_count:
            self.leaf_count *= fanout
        self.leaf_base = (self.leaf_count - 1) // (fanout - 1) + 1
        hashes = [bytes(HASH_BYTES) for _ in range(self.leaf_base + self.leaf_count)]
        for offset in range(self.leaf_count):
            if offset < self.item_count:
                x, y = divmod(offset, belief.shape[1])
                payload = b"".join((
                    b"leaf", offset.to_bytes(4, "big"),
                    int(belief.versions[x, y]).to_bytes(8, "big", signed=False),
                    int(belief.last_observed_step[x, y]).to_bytes(8, "big", signed=True),
                    int(belief.source_ids[x, y]).to_bytes(4, "big", signed=True),
                    int(belief.occupancy[x, y]).to_bytes(1, "big", signed=True),
                ))
            else:
                payload = b"pad" + offset.to_bytes(4, "big")
            hashes[self.leaf_base + offset] = sha256(payload).digest()[:HASH_BYTES]
        for index in range(self.leaf_base - 1, 0, -1):
            first = self.fanout * (index - 1) + 2
            children = range(first, first + self.fanout)
            hashes[index] = sha256(
                b"node" + b"".join(hashes[child] for child in children)
            ).digest()[:HASH_BYTES]
        self._hashes = tuple(hashes)

    def digest(self, node_index: int) -> bytes:
        self._validate_node(node_index)
        return self._hashes[node_index]

    def is_leaf(self, node_index: int) -> bool:
        self._validate_node(node_index)
        return node_index >= self.leaf_base

    def children(self, node_index: int) -> tuple[int, ...]:
        if self.is_leaf(node_index):
            raise ValueError("Merkle leaves have no children")
        first = self.fanout * (node_index - 1) + 2
        return tuple(range(first, first + self.fanout))

    def cell(self, node_index: int) -> tuple[int, int] | None:
        if not self.is_leaf(node_index):
            raise ValueError("only a Merkle leaf maps to a cell")
        offset = node_index - self.leaf_base
        return None if offset >= self.item_count else divmod(offset, self.shape[1])

    def leaf_node(self, cell: tuple[int, int]) -> int:
        x, y = cell
        if not (0 <= x < self.shape[0] and 0 <= y < self.shape[1]):
            raise ValueError("cell is outside the Merkle map")
        return self.leaf_base + x * self.shape[1] + y

    def _validate_node(self, node_index: int) -> None:
        if not 1 <= node_index < len(self._hashes):
            raise ValueError(f"invalid Merkle node index: {node_index}")


def build_iblt(
    items: tuple[bytes, ...],
    *,
    cell_count: int,
    hash_count: int,
    hash_seed: int,
) -> IBLTSketch:
    """Insert a set of fixed-width records into an IBLT."""
    mutable = [
        [0, bytearray(IBLT_KEY_BYTES), bytearray(IBLT_CHECKSUM_BYTES)]
        for _ in range(cell_count)
    ]
    for item in items:
        _validate_iblt_item(item)
        checksum = _iblt_checksum(item, hash_seed)
        for index in _iblt_indices(item, cell_count, hash_count, hash_seed):
            mutable[index][0] += 1
            _xor_into(mutable[index][1], item)
            _xor_into(mutable[index][2], checksum)
    return IBLTSketch(
        hash_count,
        hash_seed,
        tuple(IBLTCell(count, bytes(key), bytes(checksum)) for count, key, checksum in mutable),
    )


def subtract_iblt(left: IBLTSketch, right: IBLTSketch) -> IBLTSketch:
    """Return the signed table ``left - right``."""
    if (
        left.hash_count != right.hash_count
        or left.hash_seed != right.hash_seed
        or len(left.cells) != len(right.cells)
    ):
        raise ValueError("IBLT parameters do not match")
    cells = []
    for first, second in zip(left.cells, right.cells):
        cells.append(IBLTCell(
            first.count - second.count,
            _xor_bytes(first.key_xor, second.key_xor),
            _xor_bytes(first.checksum_xor, second.checksum_xor),
        ))
    return IBLTSketch(left.hash_count, left.hash_seed, tuple(cells))


def peel_iblt(sketch: IBLTSketch) -> tuple[bool, tuple[bytes, ...], tuple[bytes, ...]]:
    """List positive/negative set differences, reporting peel failure."""
    mutable = [
        [cell.count, bytearray(cell.key_xor), bytearray(cell.checksum_xor)]
        for cell in sketch.cells
    ]
    queue = list(range(len(mutable)))
    positive: list[bytes] = []
    negative: list[bytes] = []
    while queue:
        index = queue.pop()
        count, key_buffer, checksum_buffer = mutable[index]
        if abs(count) != 1:
            continue
        item = bytes(key_buffer)
        if bytes(checksum_buffer) != _iblt_checksum(item, sketch.hash_seed):
            continue
        (positive if count == 1 else negative).append(item)
        checksum = _iblt_checksum(item, sketch.hash_seed)
        for affected in _iblt_indices(
            item, len(mutable), sketch.hash_count, sketch.hash_seed,
        ):
            mutable[affected][0] -= count
            _xor_into(mutable[affected][1], item)
            _xor_into(mutable[affected][2], checksum)
            queue.append(affected)
    empty_key = bytes(IBLT_KEY_BYTES)
    empty_checksum = bytes(IBLT_CHECKSUM_BYTES)
    success = all(
        count == 0 and bytes(key) == empty_key and bytes(checksum) == empty_checksum
        for count, key, checksum in mutable
    )
    return success, tuple(positive), tuple(negative)


def _iblt_indices(
    item: bytes, cell_count: int, hash_count: int, hash_seed: int,
) -> tuple[int, ...]:
    if cell_count < hash_count:
        raise ValueError("IBLT hash functions need distinct table cells")
    seed = hash_seed.to_bytes(4, "big")
    indices: list[int] = []
    counter = 0
    while len(indices) < hash_count:
        digest = sha256(b"iblt-index" + seed + counter.to_bytes(2, "big") + item).digest()
        index = int.from_bytes(digest[:8], "big") % cell_count
        if index not in indices:
            indices.append(index)
        counter += 1
    return tuple(indices)


def _iblt_checksum(item: bytes, hash_seed: int) -> bytes:
    return sha256(
        b"iblt-check" + hash_seed.to_bytes(4, "big") + item
    ).digest()[:IBLT_CHECKSUM_BYTES]


def _validate_iblt_item(item: bytes) -> None:
    if not isinstance(item, bytes) or len(item) != IBLT_KEY_BYTES:
        raise ValueError(f"IBLT items must be {IBLT_KEY_BYTES}-byte records")


def _xor_into(target: bytearray, value: bytes) -> None:
    if len(target) != len(value):
        raise ValueError("cannot XOR fields of unequal width")
    for index, byte in enumerate(value):
        target[index] ^= byte


def _xor_bytes(first: bytes, second: bytes) -> bytes:
    if len(first) != len(second):
        raise ValueError("cannot XOR fields of unequal width")
    return bytes(left ^ right for left, right in zip(first, second))
