# Generic reconciliation controls

This study adapts three published reconciliation ideas to CARE's versioned
binary occupancy cells. It is a controlled primitive comparison, **not** an
exact reproduction of the original storage systems or deployment settings.
The paper and tables must call them Scuttlebutt-, Dynamo/Merkle- and
IBLT-inspired occupancy-map adaptations.

## Shared communication contract

Every control runs in `PSRClosedLoopRunner` with the same:

- per-robot local `BeliefMap`, observations, starts and goals;
- A* or incremental D* Lite motion planner;
- directed packet-loss trace and delay;
- 13-byte versioned cell record and canonical patch codec;
- 4,459-byte data and 512-byte control caps per sender/step;
- attempted-byte accounting, including dropped packets;
- paired controlled layout and network seed.

No control reads truth, another robot's in-memory replica, a goal-conditioned
CARE certificate or CARE's realized query length.

The 100 layouts per controlled condition are unique background-clutter
realizations under a fixed multifork decision structure. This supports paired
mechanism inference but not broad decision-graph generalization.

## Scuttlebutt-Depth adaptation

The implementation uses a per-origin maximum-version digest and backlog-depth
scheduling. A holder archives the current `(origin, cell)` mappings, sends
records newer than the requester's maximum, prioritizes origins by backlog, and
orders versions oldest-first. Observation step plus row-major cell index gives
a strictly increasing local sequence without uncharged wire fields.

Scuttlebutt replaces ordinary one-shot dissemination because unordered
one-shot delivery would violate the maximum-version summary. This preserves the
reconciliation idea, not the complete original flow-control system.

## Dynamo/Merkle adaptation

Each explicit occupancy replica is hashed into a complete 16-ary tree. Peers
compare roots, descend through mismatching child hashes, and patch mismatching
leaves. Outstanding branches persist across loss, explicit match ACKs prevent
restart, and a peer session lasts four ticks before deterministic rotation.
Normal deltas remain one-shot; Merkle exchange is only the repair layer.

This is hierarchical difference localization inspired by Dynamo. It is not a
reproduction of the Dynamo key-value service, consistency model or workload.

## Partitioned IBLT adaptation

Each key/value record is the canonical 13-byte cell delta. Peers subtract
fixed-size IBLT sketches and peel signed set differences with three hashes and
checksum validation. A 21-cell sketch occupies 491 bytes. Because one such
table cannot peel an initially large 32×32 partial-map difference, the map is
split into 16 deterministic partitions, one per repair tick, and a peer remains
selected for a complete cycle. Successful decodes return local-positive cells.

This preserves subtract-and-peel reconciliation while adapting sharding and
the record representation to the common control MTU.

## Freeze and activity checks

Protocol tuning used only mechanical activity: Merkle leaf repairs and IBLT
decode success. It did not inspect CARE-relative completion. The frozen matrix
has 21,600 executions: three FOVs, six losses, two planners, three adapted
controls plus One-shot/Retry-All/CARE, and 100 paired controlled maps.

Merkle performs about 23 leaf repairs per primary episode. IBLT decodes about
87% of received sketches and sends roughly 370 patch records. Their outcomes
therefore are not inactive/no-op failures.

## Role-aware interpretation

This matrix was produced before direct role columns were added. On the audited
controlled maps every observer completes, so seeker CSR is derived exactly as
`2 × overall CSR - 1`; values below are explicitly **derived**, while overall
CSR remains a diagnostic.

| Planner | Method | Derived seeker CSR | Overall CSR (diagnostic) | Attempted KB |
| --- | --- | ---: | ---: | ---: |
| A* | Scuttlebutt-Depth (adapt.) | 0.4250 | 0.7125 | 80.15 |
| A* | Dynamo/Merkle (adapt.) | 0.3425 | 0.6713 | 73.18 |
| A* | Partitioned IBLT (adapt.) | 0.3625 | 0.6813 | 152.80 |
| A* | CARE | 0.4725 | 0.7362 | 53.25 |
| D* Lite | Scuttlebutt-Depth (adapt.) | 0.4575 | 0.7288 | 80.80 |
| D* Lite | Dynamo/Merkle (adapt.) | 0.3800 | 0.6900 | 73.56 |
| D* Lite | Partitioned IBLT (adapt.) | 0.3925 | 0.6963 | 152.87 |
| D* Lite | CARE | 0.5375 | 0.7688 | 53.25 |

At A*, CARE-minus-adaptation derived seeker effects are +0.0475 for
Scuttlebutt, +0.1300 for Merkle and +0.1100 for IBLT; their seeker confidence
intervals are obtained by the same exact affine transformation of each paired
map difference, not by treating robots as independent samples. D* Lite keeps
the same ordering. CARE also uses less traffic in all three comparisons.

The defensible conclusion is narrow: in this controlled occupancy-cell
contract, generic state reconciliation often repairs cells too late or in the
wrong order for the protected imminent decision. It is not evidence that CARE
dominates the original published systems in their native tasks.

Generated tables live in `paper/tables/care_external_baselines_*`. They retain
the original overall diagnostic for traceability; submission text must use the
derived role endpoint or regenerate the matrix with direct role fields.

## References

- R. van Renesse et al., [“Efficient Reconciliation and Flow Control for
  Anti-Entropy Protocols”](https://doi.org/10.1145/1529974.1529983), 2008.
- G. DeCandia et al., [“Dynamo: Amazon's Highly Available Key-value
  Store”](https://doi.org/10.1145/1294261.1294281), 2007.
- M. T. Goodrich and M. Mitzenmacher, [“Invertible Bloom Lookup
  Tables”](https://doi.org/10.1109/ALLERTON.2011.6120248), 2011.
