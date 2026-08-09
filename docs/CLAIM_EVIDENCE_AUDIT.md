# CARE claim--evidence audit

| Claim | Evidence | Frozen status / boundary |
| --- | --- | --- |
| The query is minimum encoded size in the declared scenario family. | Exact hitting-set enumeration, theorem and unit tests. | Proven for uniform 6-byte entries, q≤2 and the capped candidate set; not an unbounded robust-map theorem. |
| Results use 100 independent physical maps. | Seed-free `layout_fingerprint`; analyzers reject duplicates; topology/density/scale 100-layout tests. | Supported. A seed label alone no longer counts as independence. |
| CARE improves over One-shot in the 5×5 primary task. | A*: +0.0650 [0.0488, 0.0813]; D*: +0.0788 [0.0612, 0.0963]. | Supported with paired maps/traces. |
| CARE is traffic-efficient versus reliable recovery. | Saves 101.20/101.75 KB versus Retry-All at a 0.0225/0.0175 CSR cost. | Supported as a tradeoff, not dominance. |
| CARE retains PSR-UT/CARE-Lite reliability with less traffic. | Paired CSR CIs include zero; savings are about 9.5/3.8 KB. | Supported at 30% loss and zero delay. |
| Benefits persist across sensing ranges. | CARE gain is 0.0000, +0.0650, +0.0975 at 3×3/5×5/7×7 with A*. | Supported only for 5×5 and 7×7. **Rejected at 3×3**, where map context is the bottleneck. |
| The decision window explains delay behavior. | Signed window 2/0/-2/-6 at delays 0/1/2/4; gains disappear when non-positive. | Supported in the controlled fork geometry. |
| cap=8 is a useful bounded middle point. | cap=4 loses 0.0213 CSR; cap=12 adds no detected CSR and costs ~1.48 s more. | Supported as an empirical/theoretical tradeoff, not a universal optimum. |
| CARE generalizes across topology. | Positive gains on all three topologies, but +0.1537 on T and only +0.0112/+0.0213 on the other two. | Qualitative support with strong topology dependence. |
| CARE helps arbitrary random maps. | Three of four random-control CIs include zero. | **Rejected.** The contribution is decision-critical repair, not generic exploration. |
| CARE passes the old 3× compute gate. | Exact/CARE-Lite episode CPU ratios are 3.99× A* and 3.09× D*. | **Rejected.** Bounded and measured, not negligible. |
| CARE dominates all baselines. | Retry-All/Periodic often obtain higher CSR at much higher traffic. | **Rejected.** CARE is a low-traffic operating point. |
| CARE outperforms DCC/SCRIMP/PPO. | No representation-matched reproduction exists. | Not claimed; they solve different learned-policy tasks. |

## Freeze checklist

- 30,800/30,800 planned episodes complete;
- 100 seed-free physical layout fingerprints in every condition;
- A*/D* Lite, six loss rates, delay, FOV, density, topology and scale retained;
- every ablation paired with full CARE on the same 100 layouts/traces;
- mean, sample SD, 20,000-draw cluster CI and paired effect size retained;
- cap-hit rate and conditional-event coverage retained;
- 3×3, non-positive deadline, random-map and compute negative boundaries retained;
- independent overlapping reruns agree on every non-CPU field;
- tests, README, method document, manuscript and generated tables use the same numbers.
