# Closest-work communication controls

CARE's native state is a binary occupancy replica and its native wire action is
an exact-cell query followed by a versioned exact-cell patch. Several closest
papers use richer belief models or fundamentally different codecs. Calling a
binary-cell port an exact reproduction would therefore be misleading. The
following controls are explicitly **codec-matched inspired adaptations**:

| Code policy | Paper idea isolated | Adaptation under the shared contract |
| --- | --- | --- |
| `ocbc_forward_simulation` | OCBC forward task simulation and bandwidth-bounded observation choice | OCBC-FS samples frozen receiver-local Bernoulli worlds, measures finite-horizon safe-progress gain and selects positive exact-cell arms. It does not claim OCBC's teammate particles or CSAR solver. |
| `path_guided_compression` | path-guided map compression | PGSC greedily maximizes a path-weighted spatial-coverage objective over an explicitly bounded proposal pool. It sends exact cells; it does not claim multiresolution reconstruction. |
| `rate_distortion_compression` | path-weighted rate--distortion allocation | BRD estimates a local Bernoulli probability from known receiver cells and a frozen prior, then buys the largest `path weight × q(1-q)` distortion reductions at the common exact-cell rate. It does not claim Gaussian transform coding or quantization. |
| `voi_repair` | utility/VoI-aware information distribution | VoI-per-Byte ranks independent blocked-cell counterfactual progress gain divided by the actual marginal 6-byte query plus 13-byte patch record cost. It does not claim a full belief-space middleware or cross-receiver optimizer. |

The relevant source ideas are OCBC (Marcotte *et al.*, Autonomous Robots
2020), Communication-Aware Map Compression (Psomiadis *et al.*, 2023), its
rate--distortion formulation (Psomiadis *et al.*, 2025), and utility-aware
information distribution (Barciś *et al.*, Frontiers in Robotics and AI 2021).
The manuscript cites each source and preserves this fidelity boundary.

All controls receive exactly the receiver's explicit local replica, goal and
current operational A*/D* path. Blocked counterfactuals use the same canonical
A* unit-cost graph evaluator as CARE's scenario certificate. None receives the
truth map or a peer's in-memory replica. All use
the same normal one-shot deltas, 64-byte maximum query, query--patch codec,
sender caps, peer schedule, packet-loss trace, delay and attempted-byte
accounting. `algorithm_seed` is independent of the link seed, so changing loss
does not silently change OCBC-FS Monte-Carlo worlds.

Run the frozen 100-map, three-FOV, two-planner matrix with:

```bash
python scripts/run_psr_suite.py \
  --config configs/care_closest_work_baselines_fov_100map.yaml \
  --workers 32
```

The completed matrix has 6,000 executions on controlled multifork layouts:
100 independent background-clutter realizations under the same decision
template per condition. Its primary endpoint is directly serialized seeker
CSR; overall robot CSR is diagnostic only. At 5×5, most CARE-versus-adaptation
paired seeker intervals contain zero. CARE sends about 9.5 KB less than PGSC
and Bernoulli R-D, but does not establish universal reliability dominance.
Full values are in `paper/tables/care_closest_work_*` and
[`TASK_AWARE_BASELINES.md`](TASK_AWARE_BASELINES.md).
