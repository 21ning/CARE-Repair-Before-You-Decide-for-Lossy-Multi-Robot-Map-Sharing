# Wire codec integration audit

This audit verifies that replacing object-level payload transport with the
canonical binary codec did not change the frozen protocol behavior or charged
traffic totals.

## Invariants checked

- `UnreliableNetwork` accepts only `bytes` and requires
  `len(payload) == byte_size`.
- Delta, Digest Query, Patch, ACK, and Replica Digest round-trip through their
  decoders at exactly 13 B, `16+6N` B, `4+13M` B, 8 B, and 16 B.
- Invalid lengths, reserved bits, out-of-range fields, and corrupted Delta CRCs
  are rejected.
- Decoded duplicate and relayed updates retain the existing deterministic
  stamp-merge behavior.
- The codec bounds cover every frozen configuration (up to 64x64 maps, 32
  agents, and 64 steps).

## Deterministic episode check

For layout/network seed 0 in the primary 8-agent, 30%-loss condition, the
pre-codec and post-codec PSR-UT executions are identical:

| Field | Before | After |
| --- | ---: | ---: |
| Episode length | 25 | 25 |
| Completed agents | 6/8 | 6/8 |
| Attempted messages | 4,979 | 4,979 |
| Attempted bytes | 77,151 | 77,151 |
| Data / control / repair bytes | 63,336 / 12,918 / 897 | 63,336 / 12,918 / 897 |
| Lost / delivered bytes | 23,422 / 53,729 | 23,422 / 53,729 |
| Utility-triggered receivers | 81 | 81 |

The complete action trace also matches exactly.

## 100-map paired rerun

The frozen action-trigger configuration was rerun with 32 workers after codec
integration (`configs/psr_action_triggered_100map.yaml`). It completed 200
episodes over 100 paired maps:

| Policy | CSR | Mean attempted bytes |
| --- | ---: | ---: |
| Action-triggered repair | 0.8400 | 67,501.62 |
| PSR-UT | 0.9325 | 75,773.51 |

These values reproduce the retained rounded evidence (67,502 B and 75,774 B)
exactly. Raw audit episodes were written only to a temporary directory and are
not part of the curated repository.

The final repository test command and result are recorded at release time in
the corresponding Git commit and cover the codec, transport, runner, analyses,
and deterministic parallel execution.
