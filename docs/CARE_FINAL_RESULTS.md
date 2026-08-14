# CARE statistical audit

## Evidence inventory and population labels

The frozen protocol inventory contains **69,800 complete episode executions**.
This is a compute/accounting total, not an independent-sample count: several
matrices repeat anchor policies on the same controlled layouts.

| Study | Executions | Population / purpose | Status |
| --- | ---: | --- | --- |
| Main loss/baseline | 9,600 | controlled multifork, six loss rates | complete |
| Observation range | 6,000 | controlled multifork, 3×3/5×5/7×7 | complete |
| Link delay | 3,200 | controlled multifork, delays 0/1/2/4 | complete |
| Ablation and extension | 12,000 | controlled density/topology/tiled scale plus random negative controls | complete |
| Generic reconciliation/FOV | 21,600 | controlled multifork, three external-inspired controls | complete |
| Task-aware repair ladder | 4,800 | controlled multifork | complete |
| Information-sharing spectrum | 1,800 | controlled multifork | complete |
| Closest-work adaptations/FOV | 6,000 | controlled multifork, OCBC/PGSC/R-D/VoI controls | complete |
| Route-slack gate ablation | 1,600 | controlled multifork, paired delays/planners | complete |
| Natural external validity | 1,600 | immutable conditioned Bernoulli maps | complete |
| Natural non-tiled scale | 1,600 | 4/8/16/32 robots on independently sampled maps | complete |

The controlled 100-map conditions contain 100 unique background-clutter
realizations under a fixed causal multifork structure. They are excellent for
paired mechanism tests, but do not constitute 100 independent decision
structures. The legacy scale study tiles the same motif and is only a load
stress test. The natural suites address that limitation using immutable random
bitmaps selected before any policy execution. Their selection contract is in
[`EVALUATION_VALIDITY.md`](EVALUATION_VALIDITY.md).

Within every condition, methods share the serialized layout and deterministic
packet-loss trace. Means and sample SDs use 100 map-level observations;
confidence intervals use deterministic 20,000-draw map-cluster bootstraps.
Paired intervals subtract methods within a map/loss trace before resampling.

## Primary endpoint

The primary endpoint is **decision-critical seeker CSR**. Controlled eight-
robot maps contain four one-step observers and four seekers. Every audited
observer completes, hence old all-robot CSR has a structural 0.5 floor and
obeys `(1 + seeker CSR)/2`. Overall CSR is retained only as a diagnostic.
Direct result rows now also serialize `observer_ids`, `seeker_ids`,
`critical_pairs`, `completion_steps`, completion masks, pair success and
censored seeker completion time.

## Controlled primary result: 5×5, 30% loss, zero delay

| Planner | Method | Seeker CSR mean ± SD [95% CI] | Overall CSR (diagnostic) | Attempted KB |
| --- | --- | ---: | ---: | ---: |
| A* | One-shot | 0.3425 ± 0.2061 [0.3025, 0.3825] | 0.6713 | 47.62 |
| A* | Retry-All ARQ | 0.5175 ± 0.1821 [0.4825, 0.5525] | 0.7588 | 154.45 |
| A* | Periodic Full | 0.4975 ± 0.1759 [0.4625, 0.5325] | 0.7488 | 296.60 |
| A* | Mismatch Full | 0.4650 ± 0.1947 [0.4275, 0.5025] | 0.7325 | 487.64 |
| A* | PSR-UT | 0.4700 ± 0.1955 [0.4325, 0.5075] | 0.7350 | 62.71 |
| A* | CARE-Lite | 0.4800 ± 0.1765 [0.4450, 0.5150] | 0.7400 | 57.00 |
| A* | CARE | 0.4725 ± 0.1877 [0.4350, 0.5075] | 0.7362 | 53.25 |
| D* Lite | One-shot | 0.3800 ± 0.2146 [0.3375, 0.4225] | 0.6900 | 47.78 |
| D* Lite | Retry-All ARQ | 0.5725 ± 0.1678 [0.5400, 0.6050] | 0.7863 | 155.00 |
| D* Lite | Periodic Full | 0.5475 ± 0.1730 [0.5125, 0.5825] | 0.7738 | 296.77 |
| D* Lite | Mismatch Full | 0.5000 ± 0.1946 [0.4625, 0.5375] | 0.7500 | 487.79 |
| D* Lite | PSR-UT | 0.5275 ± 0.1808 [0.4925, 0.5625] | 0.7638 | 62.74 |
| D* Lite | CARE-Lite | 0.5425 ± 0.1743 [0.5075, 0.5775] | 0.7712 | 57.06 |
| D* Lite | CARE | 0.5375 ± 0.1926 [0.5000, 0.5750] | 0.7688 | 53.25 |

Paired CARE minus One-shot is `+0.1300 [0.1000, 0.1625]` seeker CSR
(`d_z=0.789`) with A* and `+0.1575 [0.1225, 0.1925]` (`d_z=0.875`) with
D* Lite, for +5.63/+5.47 KB. CARE is not the reliability maximum: compared
with Retry-All it loses `0.0450 [0.0250, 0.0675]` and `0.0350 [0.0175,
0.0550]` seeker CSR while saving 101.20/101.75 KB. Compared with CARE-Lite,
paired seeker differences include zero while CARE saves 3.74/3.81 KB.

Mean episode length is 25.00 for every primary row because the episode ends
only after all robots finish and incomplete trials hit the 25-step horizon.
It is reported but cannot support a speed claim. Censored seeker completion
time is the role-aware timing endpoint in newly serialized results.

## Closest-work controls

The 6,000-execution matrix adds four **codec-matched inspired adaptations**:
OCBC forward simulation, path-guided spatial compression (PGSC), Bernoulli
rate--distortion allocation, and VoI per encoded byte. They share the receiver's
local binary replica, operational A*/D* path, query--patch codec, loss trace,
delay and caps. Blocked counterfactuals use the same canonical A* graph
evaluator as CARE's scenario certificate.
They do not reproduce the original papers' richer belief states or codecs.

At 5×5 with A*, seeker CSR is 0.4725 CARE, 0.4725 OCBC-FS, 0.4800 PGSC,
0.4800 Bernoulli R-D and 0.4600 VoI/byte. CARE-minus-control paired effects are
respectively `0.0000 [-0.0175, 0.0175]`, `-0.0075 [-0.0275, 0.0150]`,
`-0.0075 [-0.0250, 0.0100]`, and `+0.0125 [-0.0025, 0.0275]`. CARE sends
about 9.5 KB less than PGSC/R-D, but about 0.7 KB more than OCBC-FS/VoI.

With D* Lite, CARE is 0.5375 versus 0.5350/0.5350/0.5350/0.5325; every
primary paired reliability interval includes zero. Path-Aware Top-K reaches
0.4550/0.5225 and Single-Cell Sensitivity 0.4650/0.5250 with A*/D* Lite.
CARE's differences over Path-Aware are `+0.0175 [0.0025, 0.0325]` and
`+0.0150 [0.0000, 0.0300]`; over Single-Cell they are `+0.0075 [-0.0075,
0.0250]` and `+0.0125 [-0.0025, 0.0300]`.

These results reject universal empirical dominance. The supported novelty is
the bounded joint-scenario separation objective and an interpretable
communication/compute tradeoff; path awareness explains much of the gain.

## Natural conditioned-map external-validity result

The natural primary matrix contains 100 untouched i.i.d. Bernoulli maps
conditioned on the frozen action-conflict, visibility, path-length,
communication-window, and disjointness predicate bundle.
The audit finds 100 unique layouts, start/goal signatures, critical signatures
and raw bitmap hashes. It rehashes all 100 serialized NPZ instances, reproduces
all raw-seed bitmaps bit-exactly, and cross-checks all 1,600 result rows against
the instances and accepted manifest. The primary manifest and four scale
manifests are tracked in full under `paper/manifests/`.

Natural seeker CSR is high even without repair: with A*, No Communication,
One-shot and CARE reach 0.9300, 0.9450 and 0.9500; with D* Lite they reach
0.9325, 0.9525 and 0.9500. Paired CARE effects are:

| Planner | Comparison | Δ seeker CSR [95% CI] | Δ attempted KB [95% CI] |
| --- | --- | ---: | ---: |
| A* | CARE − No Communication | +0.0200 [-0.0050, +0.0450] | +70.35 [+68.57, +72.13] |
| A* | CARE − One-shot | +0.0050 [-0.0050, +0.0150] | +4.89 [+4.35, +5.52] |
| D* Lite | CARE − No Communication | +0.0175 [-0.0075, +0.0450] | +70.39 [+68.57, +72.22] |
| D* Lite | CARE − One-shot | -0.0025 [-0.0125, +0.0075] | +4.55 [+4.06, +5.05] |
| D* Lite | CARE − Periodic Full | -0.0125 [-0.0275, -0.0025] | -361.19 [-383.29, -339.56] |

Neither planner detects a CARE gain over One-shot or No Communication. Under
D* Lite, Periodic Full is significantly higher in seeker CSR, at far greater
traffic. In the independently sampled, non-tiled 4/8/16/32-robot matrix, every
CARE-minus-One-shot seeker interval crosses zero: A* differences are
0.0000/−0.0050/−0.0050/−0.0019, and D* Lite differences are
+0.0050/−0.0025/−0.0050/+0.0019.

This completed external-validity test does not support a broad or general CARE
gain. It narrows the positive evidence to the controlled multifork mechanism.
The natural conclusion applies to the precisely declared conditioned
population, not unconditioned random MAPF.

## Route-slack hard gate: rejected increment

Final CARE contains only the exact certificate over deadline-feasible
action-conflicting scenario pairs. It appends no auxiliary route witness. The
strict historical ablation compares two auxiliary route-witness variants: a
route-slack-gated witness and an ungated witness. Candidate set, scenario
enumeration, hitting set, scenario-pair deadline filter, codec and budgets are
otherwise identical. Delay zero matches exactly on all 200 planner/map pairs
and every non-CPU field.

At delay 2, the gated auxiliary variant minus the ungated auxiliary variant changes seeker
success by `-0.0525 [-0.0725, -0.0325]` with A* and `-0.0575 [-0.0800,
-0.0375]` with D* Lite while saving about 6.1 KB. At delay 4 it saves about
12.64 KB with no success difference. Because the preregistered -0.02
non-inferiority margin fails at delay 2, the data do **not** support incremental
value for the original route-slack gate. The scenario-pair deadline filter is
a separate component and is unchanged in this ablation. Neither auxiliary
route-witness variant defines final CARE.

## External reconciliation and information endpoints

Scuttlebutt-, Dynamo/Merkle- and IBLT-inspired controls are application-level
adaptations to exact occupancy cells, not full reproductions of their source
systems. On controlled maps their older result files precede direct role fields;
seeker values can be derived exactly from the audited observer invariant and
are explicitly labelled derived. At 5×5 A*, derived seeker CSR is 0.4250 for
Scuttlebutt, 0.3425 for Merkle, 0.3625 for IBLT and 0.4725 for CARE. The
corresponding CARE-minus-control effects are +0.0475, +0.1300 and +0.1100.

The information spectrum uses the same link: No Communication sends zero
bytes; CARE selectively repairs; Continuous Full Sync rotates all known replica
state every step. Derived 5×5 A* seeker CSR is 0.0000/0.4725/0.4500 at
0/53.25/891.80 KB. Full synchronization is lossy and capped, not a perfect
information oracle.

## Controlled extensions and limits

- In the FOV sweep, direct/derivable A* seeker CSR for One-shot versus CARE is
  0.0000/0.0000 at 3×3, 0.3425/0.4725 at 5×5, and 0.6800/0.8750 at 7×7.
  Communication cannot invent context missing from every replica.
- The old topology experiments preserve a family-specific decision graph and
  vary background clutter. They demonstrate mechanism sensitivity, not broad
  topological generalization.
- The old 4/8/16/32 scale maps tile a fork motif. They demonstrate bounded
  execution under replicated load, not non-tiled scale generalization.
- Generic random-map negative controls usually show no detected benefit,
  supporting the narrower decision-conflict claim.
- Exact CARE has materially higher planning cost than CARE-Lite; “negligible
  overhead” and the old 3× promotion gate are rejected claims.

## Frozen controlled-population claim

> On controlled decision-critical multifork maps with sufficient local map
> context, a bounded minimum scenario certificate improves seeker completion
> over one-shot sharing with a small codec-measured traffic increment. It does
> not maximize reliability, dominate all task-aware controls, or validate the
> original route-slack hard gate.

The natural conditioned-map and non-tiled scale results do not detect a general
gain, so the frozen claim remains explicitly restricted to the controlled
multifork mechanism.
