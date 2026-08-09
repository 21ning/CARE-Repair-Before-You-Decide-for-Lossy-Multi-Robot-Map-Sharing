# CARE binary wire format

CARE charges the exact length of canonical application payloads. The lossy
network therefore carries `bytes`, never Python protocol objects, and rejects a
message when `len(payload) != byte_size`. Directed-link addressing, delivery
time, and the loss-event key are transport metadata shared by every policy and
are not duplicated inside the application payload.

All multi-byte integers use network byte order (big endian). The current wire
version is `1`.

## Cell Delta: 13 bytes

| Offset | Width | Field |
| ---: | ---: | --- |
| 0 | 1 B | version (high 4 bits), ACK-request and repair flags (low bits) |
| 1 | 1 B | observation-source robot ID |
| 2 | 1 B | row `x` |
| 3 | 1 B | column `y` |
| 4 | 1 B | occupancy state (`FREE=0`, `BLOCKED=1`) |
| 5 | 2 B | cell version |
| 7 | 4 B | observation step |
| 11 | 2 B | CRC16-CCITT over bytes 0--10 |

`sender_id` is cell provenance, not necessarily the immediate relay in the
directed network envelope. The 256-bit `update_id` is reconstructed from the
decoded canonical fields and is not transmitted. An ACK-requested Delta also
reconstructs its delivery-task key from that ID and the link receiver.

## Digest Query: `16 + 6N` bytes

The 16-byte header contains one-byte version and flags, a two-byte entry count,
and 12 zero reserved bytes. Each queried cell and requester stamp occupies six
bytes. The 48-bit entry has four reserved high bits followed by:

```text
x:6 | y:6 | version:8 | observed_at+1:16 | source:6 | state:2
```

The all-zero time code represents `observed_at=-1`; source code 63 represents
an unknown source. State codes are `UNKNOWN=0`, `FREE=1`, and `BLOCKED=2`.
This format covers every frozen experiment: maps up to 64x64, at most 63
robots, and at most 65,535 episode steps. The runner validates these bounds
before starting an episode.

## Patch: `4 + 13M` bytes

A Patch has a one-byte version, one reserved flag byte, a two-byte update
count, and `M` canonical Cell Deltas. Every embedded Delta retains its own
CRC16 and observation-source stamp.

## ACK and replica digest

| Payload | Width | Encoding |
| --- | ---: | --- |
| ACK | 8 B | first 64 bits of SHA-256 over the canonical update digest and receiver ID |
| Replica digest | 16 B | first 128 bits of the canonical SHA-256 replica digest |

The sender matches an ACK token against active delivery tasks and rejects an
in-memory collision instead of removing an ambiguous task.

## Decode and merge

On delivery, the receiver selects a decoder from the network message kind,
checks the exact length, version, reserved bits, field bounds, and Delta CRC,
then reconstructs typed protocol state. A decoded cell is applied only if its
stamp

```text
(version, observed_at, source_id, cell_state)
```

lexicographically dominates the receiver's current stamp. Duplicate and
out-of-order messages are therefore idempotent. A decoded Digest Query is
answered only with cells whose local stamps dominate the requester stamps.

`attempted_bytes` is the sum of encoded payload lengths for all admitted send
attempts, including packets subsequently lost by the channel. Data, control,
and repair bytes are also recorded separately.

Codec and transport invariants are covered by `tests/test_wire_codec.py` and
`tests/test_unreliable_network.py`.
