# CARE final statistical audit

## Frozen evidence

All planned runs are complete: 59,000 episodes. Every policy-condition uses
100 physically distinct layouts, not merely 100 different seed labels. The
same layout and deterministic packet-loss trace are shared by paired methods.
Means and sample SDs use the 100 map-level observations; confidence intervals
are deterministic 20,000-draw map-cluster bootstraps. Paired intervals subtract
methods within a layout/loss trace before resampling.

| Study | Episodes | Scope |
| --- | ---: | --- |
| Main loss/baseline | 9,600 | 6 loss rates × 8 methods × A*/D* Lite |
| Observation range | 6,000 | 3×3/5×5/7×7 × 10 methods × A*/D* Lite |
| Link delay | 3,200 | delays 0/1/2/4 × 4 methods × A*/D* Lite |
| Ablation and extension | 12,000 | density, random negative controls, q/cap/cadence, topology, scale |
| Published reconciliation/FOV | 21,600 | 3 sensing ranges × 6 losses × 6 methods × A*/D* Lite |
| Task-aware repair ladder | 4,800 | 3 sensing ranges × 8 methods × A*/D* Lite |
| Information-sharing spectrum | 1,800 | No Communication/CARE/Continuous Full Sync × 3 sensing ranges × A*/D* Lite |

Independent reruns of the overlapping 5×5 conditions agree on every
non-timing output field (`care_cross_study_reproducibility.json`).

## Primary 5×5 result at 30% loss

| Planner | Method | CSR mean ± SD [95% CI] | Attempted KB |
| --- | --- | ---: | ---: |
| A* | One-shot | 0.6713 ± 0.1031 [0.6512, 0.6913] | 47.62 |
| A* | Retry-All ARQ | 0.7588 ± 0.0910 [0.7412, 0.7762] | 154.45 |
| A* | Periodic Full | 0.7488 ± 0.0879 [0.7312, 0.7662] | 296.60 |
| A* | PSR-UT | 0.7350 ± 0.0978 [0.7163, 0.7538] | 62.71 |
| A* | CARE-Lite | 0.7400 ± 0.0883 [0.7225, 0.7575] | 57.00 |
| A* | CARE | 0.7362 ± 0.0938 [0.7175, 0.7550] | 53.25 |
| D* Lite | One-shot | 0.6900 ± 0.1073 [0.6700, 0.7113] | 47.78 |
| D* Lite | Retry-All ARQ | 0.7863 ± 0.0839 [0.7700, 0.8025] | 155.00 |
| D* Lite | CARE | 0.7688 ± 0.0963 [0.7488, 0.7875] | 53.25 |

Paired CARE minus One-shot is +0.0650 CSR [0.0488, 0.0813] with A* and
+0.0788 [0.0612, 0.0963] with D* Lite, for +5.63/+5.47 KB. CARE gives up
0.0225/0.0175 CSR to Retry-All but saves 101.20/101.75 KB. Relative to PSR-UT,
CSR is statistically indistinguishable while CARE saves about 9.5 KB. CARE is
therefore a low-traffic reliability point, not the absolute-CSR winner.

### Published external reconciliation baselines

A separate matrix adds Scuttlebutt-Depth, Dynamo-style 16-ary Merkle
anti-entropy, and 16-partition IBLT reconciliation across all three sensing
ranges and both planners. At the primary point, A* CARE versus
Scuttlebutt/Merkle/IBLT is respectively +0.0238 `[0.0088, 0.0387]`, +0.0650
`[0.0500, 0.0813]`, and +0.0550 `[0.0387, 0.0712]` CSR, while saving
26.90/19.93/99.55 KB. D* Lite gives the same ordering. Merkle averages 23.51
leaf repairs and IBLT decodes 87.51% of received sketches, so their weaker CSR
is not caused by an inactive implementation.

### Closest task-aware repair baselines

The final 4,800-episode matrix adds Path-Aware Top-K and Single-Cell Decision
Sensitivity under the exact CARE query--patch contract. All three methods use
the same eight-cell/64-byte maximum query; the heuristics receive no realized
CARE query length and perform no joint scenario enumeration.

At 5×5, Path-Aware reaches 0.7275/0.7612 CSR with A*/D* Lite at 54.37/54.39
KB; Single-Cell reaches 0.7325/0.7625 at 52.11/52.23 KB. CARE reaches
0.7362/0.7688 at 53.25 KB. CARE minus Path-Aware is +0.0088
`[0.0013, 0.0175]` and +0.0075 `[0.0000, 0.0150]` CSR while saving about
1.1 KB. CARE minus Single-Cell is only +0.0037 `[-0.0037, 0.0125]` and
+0.0063 `[-0.0013, 0.0150]`, while CARE sends about 1.1/1.0 KB more.

This rejects the broad claim that exact certification materially improves
primary-condition reliability over every task-aware heuristic. Path awareness
explains most of the gain. CARE contributes a bounded joint-scenario guarantee
and compresses broad path/deadline queries; Single-Cell is the stronger
lightweight empirical alternative. Full evidence is in
`TASK_AWARE_BASELINES.md` and `paper/tables/care_task_aware_*`.

### Information-sharing spectrum and mean EL

The endpoint study compares true zero-byte No Communication, CARE and
Continuous Full Sync (`K=1`) under the same lossy link and byte cap. At 5×5,
A* CSR/mean EL/traffic are respectively `0.5000/25.00/0.00 KB`,
`0.7362/25.00/53.25 KB` and `0.7250/25.00/891.80 KB`. D* Lite gives
`0.5000/25.00/0.00`, `0.7688/25.00/53.25` and
`0.7550/25.00/891.80`.

Continuous Full Sync minus CARE is -0.0112 `[-0.0262, 0.0037]` A* CSR and
-0.0138 `[-0.0300, 0.0025]` D* Lite CSR, so no primary reliability advantage
is detected despite about 838.55 KB more traffic. At 7×7, full sync gains
+0.0437 `[0.0275, 0.0612]` A* CSR and shortens mean EL by 0.29 steps, but
costs about 793.33 KB more.

Mean EL, sample SD and CI are now retained in every new task-aware and spectrum
table. At 5×5 all policies hit the 25-step all-robots-complete horizon, so EL
has a ceiling effect and cannot support a speed claim. Full evidence is in
`INFORMATION_SPECTRUM.md` and `paper/tables/care_information_spectrum*`.

## Packet loss and delay

Across loss 0.0--0.5, A* CARE CSR is 0.7600, 0.7563, 0.7525, 0.7362,
0.7063 and 0.6863. Its gain over One-shot grows when loss creates
decision-relevant replica divergence, while reliable ARQ remains the
higher-traffic reliability endpoint.

At 30% loss, A* CARE CSR at one-way delays 0/1/2/4 is
0.7362/0.6913/0.6475/0.6525. The corresponding signed usable communication
window is 2/0/-2/-6 steps. At delay 2 and 4, deadline-aware repair no longer
beats One-shot. This is the predicted deadline boundary rather than a hidden
failure condition.

## Observation range and causal diagnostics

| FOV | A* One-shot | A* CARE | CARE gain | CARE cap-hit rate |
| --- | ---: | ---: | ---: | ---: |
| 3×3 | 0.5000 | 0.5000 | 0.0000 | 0.4778 |
| 5×5 | 0.6713 | 0.7362 | +0.0650 | 0.3662 |
| 7×7 | 0.8400 | 0.9375 | +0.0975 | 0.1437 |

The remote observer first sees the critical obstacle at step 0 and the
declared branch commitment occurs at step 2, so the zero-delay communication
window is intentionally 2 steps at all three FOVs. FOV changes the available
map context and candidate pressure, not that controlled geometry. Under 3×3,
all methods remain at 0.5 CSR: the limiting factor is insufficient local map
support for optimistic A*, which replica repair cannot invent. CARE's benefit
is therefore sustained at 5×5 and 7×7, not at 3×3.

Conditional self-observation means are reported with coverage: CARE observes
the critical obstacle locally in 3.3%, 59.8% and 95.8% of critical pairs for
3×3/5×5/7×7. Missing events are never converted to zero.

## Full-method ablations

All rows compare full CARE directly with its matched ablation, never with an
unrelated One-shot anchor.

- Cadence K=4 loses 0.0362 A* CSR [0.0238, 0.0488].
- q=1 is statistically close to q=2 and is about 0.60 s faster, but queries
  1.13 KB less and covers a strictly smaller uncertainty family.
- cap=4 loses 0.0213 CSR [0.0125, 0.0312].
- cap=12 changes CSR by only +0.0050 (full-minus-cap12 = -0.0050,
  [-0.0125, 0.0025]) but costs another 0.93 KB and about 1.48 s.
- Full CARE is indistinguishable from CARE-Lite/PSR-UT in CSR while using
  3.74/9.46 KB less traffic.

The default q=2, cap=8, K=1 is the declared middle point between robustness,
traffic and bounded exact computation.

## Density, topology, scale, and negative controls

CARE's paired A* gain over One-shot remains positive across structured-map
densities 0.10/0.20/0.30/0.40: +0.0950/+0.0650/+0.0537/+0.0175.
Topology matters: gains are +0.1537 on T-junctions, +0.0112 on asymmetric
forks and +0.0213 on narrow bypasses. Each topology condition contains 100
physically different background layouts while preserving its decision graph.

At 4/8/16/32 agents, A* CARE gains +0.0350/+0.0125/+0.0219/+0.0091 over
One-shot. On generic random-map negative controls, three of four density CIs
include zero; this supports the narrower claim that CARE helps when lost map
state changes an imminent decision, not arbitrary replica disagreement.

## Computation boundary

At the primary point, exact CARE takes about 1.04 s/episode with A* and
1.14 s with D* Lite, versus 0.26/0.37 s for CARE-Lite. The 3.99×/3.09× ratios
fail the old 3× promotion gate. Absolute runtime remains bounded and practical
for these experiments, but “negligible overhead” and “passes the 3× gate” are
rejected claims. q=1 and cap=4 reduce cost but respectively weaken the declared
scenario family or significantly reduce reliability.

## Frozen claim

> In decision-critical lossy map sharing with sufficient local map context,
> a deadline-constrained minimum scenario certificate improves completion over
> one-shot sharing with a small codec-measured traffic increment, and exposes
> interpretable sensor, deadline, topology and compute boundaries.

CARE does not claim to maximize reliability, work under arbitrary uncertainty,
improve 3×3 optimistic-A* exploration, or outperform end-to-end learned MAPF.
