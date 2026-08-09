# CARE paired full-method ablations

Every difference is full CARE (q=2, cap=8, K=1) minus the named matched ablation on the same 100 maps and loss traces.

| Planner | Ablation | ΔCSR [95% CI] | Δ attempted KB [95% CI] | Δ episode CPU ms [95% CI] |
| --- | --- | ---: | ---: | ---: |
| A* | Certificate trigger -> immediate-action trigger | +0.0650 [+0.0500, +0.0813] | +3.39 [+3.15, +3.64] | +768.41 [+758.20, +778.67] |
| A* | Certificate scope -> full-replica scope | +0.0625 [+0.0462, +0.0788] | -102.11 [-102.48, -101.74] | +623.47 [+613.23, +633.80] |
| A* | Exact certificate -> PSR-UT heuristic | +0.0013 [-0.0088, +0.0112] | -9.46 [-9.66, -9.28] | +748.10 [+738.07, +758.25] |
| A* | Exact certificate -> CARE-Lite heuristic | -0.0037 [-0.0138, +0.0063] | -3.74 [-3.95, -3.54] | +751.93 [+741.85, +762.23] |
| A* | Cadence K=1 -> K=4 | +0.0362 [+0.0238, +0.0488] | +4.20 [+3.97, +4.45] | +558.34 [+549.24, +567.75] |
| A* | Uncertainty order q=2 -> q=1 | +0.0050 [-0.0037, +0.0138] | +1.13 [+0.97, +1.30] | +604.93 [+595.24, +614.50] |
| A* | Candidate cap 8 -> 4 | +0.0213 [+0.0125, +0.0312] | +1.73 [+1.54, +1.92] | +552.48 [+543.23, +561.94] |
| A* | Candidate cap 8 -> 12 | -0.0050 [-0.0125, +0.0025] | -0.93 [-1.06, -0.81] | -1475.57 [-1501.65, -1448.90] |
| D* Lite | Certificate trigger -> immediate-action trigger | +0.0788 [+0.0612, +0.0963] | +3.23 [+3.02, +3.45] | +754.49 [+744.30, +765.13] |
| D* Lite | Certificate scope -> full-replica scope | +0.0788 [+0.0612, +0.0963] | -102.20 [-102.51, -101.89] | +603.71 [+593.33, +614.30] |
| D* Lite | Exact certificate -> PSR-UT heuristic | +0.0050 [-0.0063, +0.0163] | -9.49 [-9.69, -9.29] | +734.30 [+724.47, +744.47] |
| D* Lite | Exact certificate -> CARE-Lite heuristic | -0.0025 [-0.0125, +0.0075] | -3.81 [-4.01, -3.61] | +739.71 [+729.38, +750.40] |
| D* Lite | Cadence K=1 -> K=4 | +0.0437 [+0.0300, +0.0575] | +4.04 [+3.84, +4.24] | +545.31 [+535.20, +555.92] |
| D* Lite | Uncertainty order q=2 -> q=1 | +0.0063 [-0.0013, +0.0138] | +1.01 [+0.86, +1.17] | +594.43 [+584.86, +604.37] |
| D* Lite | Candidate cap 8 -> 4 | +0.0213 [+0.0125, +0.0312] | +1.66 [+1.50, +1.83] | +542.10 [+531.96, +552.47] |
| D* Lite | Candidate cap 8 -> 12 | -0.0063 [-0.0150, +0.0025] | -0.96 [-1.08, -0.84] | -1483.20 [-1509.17, -1456.96] |
