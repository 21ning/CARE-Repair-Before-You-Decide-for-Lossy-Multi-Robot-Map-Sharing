# Published reconciliation baselines

CARE is compared with three algorithms originating outside this project. The
goal is a controlled algorithmic comparison, not a claim that the repository
reproduces the original storage systems or their deployment environments.
Every adaptation retains the paper's reconciliation primitive while replacing
the original application state with the same versioned occupancy cells used by
CARE.

## Common experimental contract

All methods run inside `PSRClosedLoopRunner` with the same:

- per-robot `BeliefMap`, local observations, starts and goals;
- A* or incremental D* Lite planner;
- directed packet-loss trace and delay;
- 13-byte versioned cell record and canonical patch codec;
- 4,459-byte data and 512-byte control caps per sender per step;
- 100 physically distinct maps paired by layout and network seed.

No baseline reads the truth map, another robot's memory, or CARE's path
certificate. All summaries charge attempted encoded bytes, including packets
lost by the channel.

## Scuttlebutt-Depth

The implementation follows van Renesse et al.'s per-participant maximum-version
digest and depth scheduling. A holder archives the current mapping for every
`(origin, cell)` key. A push--pull exchange sends mappings newer than the
requester's per-origin maximum, serving origins with the deepest backlog first
and versions within an origin from oldest to newest. This ordering is required:
an MTU-truncated message must not expose a later version while omitting an
earlier current mapping from the same origin.

The existing observation step and row-major cell index form a unique,
strictly increasing per-origin sequence number, avoiding extra uncharged wire
fields. Scuttlebutt replaces ordinary one-shot dissemination rather than being
layered on top of it, because unordered one-shot delivery would violate its
maximum-version invariant.

## Dynamo-style Merkle anti-entropy

Each explicit replica is hashed into a complete 16-ary Merkle tree over all map
cells. Peers compare the root, descend only through mismatching child hashes,
and send a canonical one-cell patch at a mismatching leaf. A child response is
260 bytes under the 512-byte cap. Mismatching siblings are retained across
ticks and traversed depth-first; explicit match acknowledgements and retained
outstanding nodes make the traversal retryable after loss. A peer session lasts
four ticks before deterministic rotation.

This is Dynamo-style hierarchical difference localization, not a reproduction
of the complete Dynamo key-value service. Normal cell updates remain one-shot;
Merkle exchange is the repair layer.

## Partitioned IBLT reconciliation

Each record is the exact 13-byte canonical cell delta. Peers subtract fixed-size
IBLT sketches and peel positive and negative set differences using three hash
functions and checksum validation. A 21-cell sketch occupies 491 bytes and
fits the common control cap.

A single 491-byte table cannot decode the initially large difference between
32×32 partial maps. The map is therefore split into sixteen deterministic
modulo-index partitions, one rotated per repair tick. This preserves the
published signed subtract-and-peel primitive while ensuring small enough set
differences without increasing the link budget. A peer is held for a complete
16-partition cycle before rotation, rather than receiving unrelated shards.
Normal deltas remain one-shot, and successful decodes return only local-positive
records.

## Optimization and freeze rule

Optimization was limited to protocol mechanics observable in the original
reconciliation problem. The binary Merkle smoke test repeatedly exhausted or
lost long root-to-leaf exchanges, so fanout, acknowledgements, persistent
branches and peer-session length were introduced. The unpartitioned IBLT could
not peel the initial map difference under a 512-byte MTU, so the frozen
partition count was chosen to place about 64 map cells in each shard. Small
pilot runs selected settings using leaf-repair and sketch-decode activity, not
CARE-relative CSR. No variant was allowed to access robot paths, goals,
commitment time, certificate cells or truth state. The 16-ary/16-partition
settings were then frozen before the 21,600-episode three-FOV matrix.

## Audited result

The frozen matrix contains 21,600 complete episodes: 100 independent maps,
3×3/5×5/7×7 sensing, six loss rates, A*/D* Lite, the three external methods,
One-shot, Retry-All, and CARE. At 30% packet loss in the primary 5×5 condition:

| Planner | Method | CSR | Attempted KB |
| --- | --- | ---: | ---: |
| A* | Scuttlebutt-Depth | 0.7125 | 80.15 |
| A* | Dynamo-style Merkle AE | 0.6713 | 73.18 |
| A* | Partitioned IBLT | 0.6813 | 152.80 |
| A* | CARE | 0.7362 | 53.25 |
| D* Lite | Scuttlebutt-Depth | 0.7288 | 80.80 |
| D* Lite | Dynamo-style Merkle AE | 0.6900 | 73.56 |
| D* Lite | Partitioned IBLT | 0.6963 | 152.87 |
| D* Lite | CARE | 0.7688 | 53.25 |

Scuttlebutt is the strongest external method: versus One-shot, its paired CSR
gain is +0.0413 `[0.0187, 0.0625]` with A* and +0.0387
`[0.0175, 0.0600]` with D* Lite. CARE still improves over Scuttlebutt by
+0.0238 `[0.0088, 0.0387]` and +0.0400 `[0.0225, 0.0575]`, while sending
26.90/27.54 KB less.

The optimized Merkle implementation reaches and transmits 23.51/22.26
mismatching leaves per 5×5 episode. Partitioned IBLT successfully decodes
87.51%/87.22% of received sketches and sends 371.04/369.77 patch records. Their
weaker task outcomes are therefore not no-op implementation failures: generic
difference localization/recovery often does not finish early enough, or does
not prioritize the cells that change the imminent route decision.

The sensing sweep reinforces that boundary. At 3×3 every method remains at
0.5000 CSR because communication cannot invent unobserved context. At 7×7 with
A*, CARE reaches 0.9375 versus 0.8712 Scuttlebutt, 0.8562 IBLT and 0.8400
Merkle. CARE's paired gains over those methods are respectively +0.0663
`[0.0413, 0.0925]`, +0.0813 `[0.0625, 0.1000]`, and +0.0975
`[0.0788, 0.1163]`. Full mean/SD/CIs and paired effects are retained in
`paper/tables/care_external_baselines_*.{csv,md}`. In particular,
`care_external_baselines_fov_paired` reports CARE-minus-external effects for
every sensing range and planner, while `care_external_baselines_vs_oneshot`
shows how much each generic reconciliation method adds over unrepaired
one-shot dissemination.

## References

- R. van Renesse et al., [“Efficient Reconciliation and Flow Control for
  Anti-Entropy Protocols”](https://doi.org/10.1145/1529974.1529983), LADIS,
  2008.
- G. DeCandia et al., [“Dynamo: Amazon's Highly Available Key-value
  Store”](https://doi.org/10.1145/1294261.1294281), SOSP, 2007.
- M. T. Goodrich and M. Mitzenmacher, [“Invertible Bloom Lookup
  Tables”](https://doi.org/10.1109/ALLERTON.2011.6120248), Allerton, 2011.
