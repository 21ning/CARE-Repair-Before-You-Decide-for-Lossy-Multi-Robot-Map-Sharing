# CARE claim--evidence audit

The primary outcome is decision-critical seeker CSR. Overall robot CSR is a
diagnostic because the controlled multifork observers always complete and
create a structural 0.5 floor. “Controlled maps” below means independent
background clutter under a fixed decision template, not independent decision
structures.

| Claim | Evidence | Status / boundary |
| --- | --- | --- |
| The CARE query has minimum encoded size within the declared scenario family. | Exact uniform-cost hitting-set enumeration plus theorem/tests. | Proven only for the capped candidate set, `q≤2`, and uniform 6-byte query entries; not an unbounded robust-map theorem. |
| CARE improves seeker completion over One-shot at the controlled 5×5 primary point. | A*: +0.1300 [0.1000, 0.1625]; D*: +0.1575 [0.1225, 0.1925]. | Supported by 100 paired clutter realizations/loss traces. |
| CARE is a traffic-efficient alternative to reliable recovery. | Versus Retry-All, CARE saves 101.20/101.75 KB but loses 0.0450/0.0350 seeker CSR. | Supported as a tradeoff, not dominance. |
| CARE improves materially over every closest task-aware method. | No difference is detected versus OCBC-FS, and paired CIs versus PGSC, R-D, Single-Cell and most D* controls include zero. | **Rejected.** Path/task awareness explains much of the empirical gain. |
| CARE improves over Path-Aware Top-K. | +0.0175 [0.0025, 0.0325] A*; +0.0150 [0.0000, 0.0300] D*. CARE saves about 1.1 KB. | Small controlled-population support; D* CI touches zero and most 7×7 intervals include zero. |
| Exact joint certification materially improves reliability over Single-Cell. | +0.0075 [-0.0075, 0.0250] A*; +0.0125 [-0.0025, 0.0300] D*. | **Not detected.** The formal bounded joint-scenario guarantee remains distinct from empirical superiority. |
| CARE outperforms OCBC, path-guided compression, R-D and VoI as published algorithms. | Repository implements binary-cell, codec-matched inspired controls rather than their native belief/codec systems. | **Not claimed.** Only the explicitly documented adaptations are compared. |
| CARE improves over generic reconciliation controls. | Controlled 5×5 derived seeker differences versus Scuttlebutt/Merkle/IBLT are positive. | Supported only for the repository's occupancy-cell adaptations; not full-system reproductions. |
| Final CARE uses only the exact deadline-feasible scenario certificate. | Final `certificate_repair` appends neither auxiliary route witness; both witness policies have explicit ablation-only names. | Supported by implementation/tests and method audit. |
| The auxiliary route-slack hard gate has incremental value. | At delay 2, gated-minus-ungated auxiliary-witness seeker effect is -0.0525 [-0.0725, -0.0325] A* and -0.0575 [-0.0800, -0.0375] D*. | **Rejected.** It saves traffic but fails the preregistered -0.02 non-inferiority criterion. Neither auxiliary witness is final CARE. |
| Delay zero gate ablation is implementation-equivalent. | 200 planner/map pairs, zero non-CPU differences. | Supported negative control. |
| CARE works at every sensing range. | A* seeker gain is 0.0000/0.1300/0.1950 at 3×3/5×5/7×7. | Supported only at 5×5 and 7×7; **rejected at 3×3**. |
| The controlled 100 maps establish broad structural generalization. | All share the protected multifork causal structure while clutter changes. | **Rejected.** They establish replication across clutter, not decision-graph diversity. |
| The legacy 4--32 robot scale study establishes non-tiled generalization. | It tiles the same fork motif. | **Rejected.** Retained only as controlled computational/load stress. |
| CARE helps arbitrary random MAPF maps. | Most generic random-control CIs include zero. | **Rejected.** The target claim is decision-critical repair, not generic exploration. |
| CARE improves over One-shot on the natural conditioned population. | A*: +0.0050 [-0.0050, 0.0150]; D*: -0.0025 [-0.0125, 0.0075]. | **Not supported.** Both intervals cross zero. |
| CARE improves over No Communication on the natural conditioned population. | A*: +0.0200 [-0.0050, 0.0450]; D*: +0.0175 [-0.0075, 0.0450]. | **Not supported.** The target population is conditioned Bernoulli maps, not unconditioned random MAPF. |
| CARE generalizes across non-tiled 4/8/16/32-robot natural scale. | All eight CARE-minus-One-shot seeker CIs cross zero. | **Not supported.** The completed suite establishes an external-validity boundary, not broad gain. |
| CARE has negligible overhead or passes the old 3× gate. | Exact/CARE-Lite episode CPU ratios exceed the old threshold. | **Rejected.** Compute is bounded and measured, not negligible. |
| CARE dominates every baseline. | Retry-All and Periodic Full often obtain higher seeker CSR at much greater traffic. | **Rejected.** CARE is a selective low-traffic operating point. |
| CARE outperforms DCC/SCRIMP/PPO. | No representation- and task-matched reproduction exists. | Not claimed; these learned-policy systems solve a different action/communication task. |

## Statistical and artifact checklist

- `observer_ids`, `seeker_ids`, `critical_pairs`, `completion_steps`, completion
  masks, seeker CSR, pair success and censored seeker completion time are
  serialized directly in new result rows.
- Old controlled matrices may derive seeker CSR only through the audited exact
  identity `(2 × overall CSR) - 1`; such values must be labelled derived.
- Mean, sample SD and 20,000-draw map-cluster CI are reported; all analyzers
  share one fixed public cluster-resampling index, and paired effects preserve
  map and deterministic loss-trace matching.
- The controlled 100-map population is described as fixed-structure,
  independently cluttered multifork maps.
- The legacy scale sweep is labelled tiled-motif stress.
- External and closest-work controls are labelled codec-matched inspired
  adaptations, never exact paper reproductions.
- The negative 3×3, route-gate, random-map and compute boundaries remain
  visible.
- Raw outputs are gitignored; configs, code, five complete accepted-layout
  manifests and derived paper tables/figures are tracked.
- The natural analyzer rehashes serialized NPZs, bit-exactly regenerates raw
  bitmaps from seeds, and cross-checks results, instances and manifests.
- Completed protocol accounting is 69,800 executions including repeated anchors;
  this count is never presented as 69,800 independent samples.
