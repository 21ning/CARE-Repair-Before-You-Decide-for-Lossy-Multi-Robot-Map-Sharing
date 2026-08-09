# CARE final statistical audit

## Frozen design

The final loss/baseline matrix is complete: 9,600 episodes, with no missing or
duplicate trials.

- 100 independently generated maps per condition;
- eight robots and 25 environment steps per episode;
- A* and incremental D* Lite operational planners;
- packet-loss probabilities 0.0, 0.1, 0.2, 0.3, 0.4 and 0.5;
- One-shot, Retry-All ARQ, Path-Weighted ARQ, Periodic Full Sync (`K=4`),
  Mismatch Full Repair, PSR-UT, CARE-Lite and final CARE;
- identical map, link trace, codec, delay and byte budgets inside every paired
  comparison.

The map is the experimental unit. Means and sample standard deviations use all
100 maps. Confidence intervals are deterministic 20,000-draw map-cluster
bootstraps. Paired intervals subtract methods on the same map and loss trace
before resampling.

## Final CARE loss sweep

Values are mean ± sample SD with map-cluster 95% CI, followed by attempted
traffic in KB.

| Planner | Loss | CSR | Attempted KB |
| --- | ---: | ---: | ---: |
| A* | 0.0 | 0.9925 ± 0.0347 [0.9850, 0.9988] | 59.37 ± 0.83 [59.21, 59.54] |
| A* | 0.1 | 0.9888 ± 0.0401 [0.9800, 0.9962] | 62.06 ± 0.94 [61.87, 62.24] |
| A* | 0.2 | 0.9788 ± 0.0535 [0.9675, 0.9888] | 64.77 ± 1.08 [64.56, 64.98] |
| A* | 0.3 | 0.9375 ± 0.0804 [0.9213, 0.9525] | 67.79 ± 1.20 [67.56, 68.03] |
| A* | 0.4 | 0.9012 ± 0.0978 [0.8812, 0.9200] | 70.52 ± 1.16 [70.30, 70.75] |
| A* | 0.5 | 0.8263 ± 0.1050 [0.8063, 0.8462] | 73.85 ± 1.43 [73.57, 74.13] |
| D* Lite | 0.0 | 0.9925 ± 0.0347 [0.9850, 0.9988] | 59.38 ± 0.84 [59.22, 59.55] |
| D* Lite | 0.1 | 0.9888 ± 0.0401 [0.9800, 0.9962] | 62.05 ± 0.93 [61.87, 62.23] |
| D* Lite | 0.2 | 0.9788 ± 0.0535 [0.9675, 0.9888] | 64.76 ± 1.07 [64.55, 64.97] |
| D* Lite | 0.3 | 0.9413 ± 0.0804 [0.9250, 0.9563] | 67.67 ± 1.06 [67.47, 67.89] |
| D* Lite | 0.4 | 0.9000 ± 0.0989 [0.8800, 0.9187] | 70.46 ± 1.12 [70.25, 70.69] |
| D* Lite | 0.5 | 0.8325 ± 0.1008 [0.8125, 0.8512] | 73.73 ± 1.18 [73.50, 73.96] |

## Matched primary comparison at 30% loss

The complete mean/SD/CI table for all eight methods is retained in
`paper/tables/care_loss_baselines_primary.md`.

For A*, final CARE versus:

- One-shot: +0.0975 CSR [0.0788, 0.1163], +2.44 KB [2.20, 2.68];
- Retry-All ARQ: -0.0387 CSR [-0.0563, -0.0213], -196.10 KB
  [-196.86, -195.35];
- Path-Weighted ARQ: -0.0400 CSR [-0.0575, -0.0238], -196.13 KB;
- Periodic Full: -0.0200 CSR [-0.0375, -0.0025], -217.98 KB;
- Mismatch Full: +0.0225 CSR [0.0063, 0.0387], -511.10 KB;
- PSR-UT: +0.0050 CSR [-0.0125, 0.0225], -7.98 KB [-8.20, -7.76];
- CARE-Lite: +0.0000 CSR [-0.0138, 0.0138], -0.83 KB [-1.00, -0.66].

For D* Lite, final CARE versus One-shot is +0.0950 CSR
[0.0775, 0.1125] for +2.37 KB; versus PSR-UT it is +0.0100 CSR
[-0.0063, 0.0262] while saving 7.97 KB; versus CARE-Lite it is +0.0013 CSR
[-0.0125, 0.0150] while saving 0.94 KB.

## Scientific interpretation

CARE is a low-traffic Pareto operating point, not a universal winner.

- At 30% loss it recovers roughly 70% of the One-shot reliability gap to the
  reliable ARQ endpoint while using about one quarter of ARQ traffic.
- CARE is statistically indistinguishable in CSR from CARE-Lite and PSR-UT at
  the primary point, but its traffic reduction versus both has a confidence
  interval entirely below zero.
- At 50% loss, A* CARE trades -0.0200 CSR versus CARE-Lite for 1.23 KB less
  traffic. This high-loss boundary is reported rather than hidden.
- At zero loss every method reaches 0.9925 CSR; One-shot dominates because no
  repair is needed. CARE becomes useful only when loss creates decision-relevant
  replica divergence.
- A* and D* Lite give the same qualitative ordering, supporting a
  planner-independent communication claim.

## Computation overhead

At the primary 30% loss point, final CARE uses 0.767 s mean episode CPU with A*
and 0.867 s with D* Lite for a 25-step, eight-agent episode. These are 2.52x
and 2.09x the corresponding CARE-Lite costs. The bounded online solver uses at
most 37 scenarios and 256 query subsets per certificate check; the Python
reference implementation is feasible but not claimed to be computation-free.

## Frozen claim

The supported claim is:

> Under decision-critical explicit map loss, a deadline-constrained minimum
> scenario certificate recovers substantial completion reliability with a
> small, codec-measured traffic increment, and yields a stable low-traffic
> Pareto point across two planners and six packet-loss rates.

The evidence does not support a claim that CARE maximizes reliability, applies
to arbitrary map uncertainty, or replaces end-to-end learned MAPF policies.
