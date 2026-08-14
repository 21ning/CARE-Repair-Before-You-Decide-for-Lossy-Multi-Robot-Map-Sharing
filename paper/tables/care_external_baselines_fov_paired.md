# CARE paired against published reconciliation baselines across sensing ranges

All comparisons use 30% loss and 100 matched maps. Positive Δ derived seeker CSR favors CARE; negative ΔKB means CARE sends less traffic.

| FOV | Planner | Comparison | Δ derived seeker CSR [95% CI] | paired d_z | ΔEL [95% CI] | ΔKB [95% CI] |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 3x3 | A* | CARE - Scuttlebutt-Depth | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | -17.68 [-18.54, -16.81] |
| 3x3 | A* | CARE - Dynamo-style Merkle AE | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | -21.44 [-21.73, -21.15] |
| 3x3 | A* | CARE - Partitioned IBLT | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | -97.76 [-97.91, -97.61] |
| 3x3 | D* Lite | CARE - Scuttlebutt-Depth | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | -17.68 [-18.54, -16.81] |
| 3x3 | D* Lite | CARE - Dynamo-style Merkle AE | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | -21.44 [-21.73, -21.15] |
| 3x3 | D* Lite | CARE - Partitioned IBLT | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | -97.76 [-97.91, -97.61] |
| 5x5 | A* | CARE - Scuttlebutt-Depth | +0.0475 [+0.0175, +0.0800] | +0.301 | +0.00 [+0.00, +0.00] | -26.90 [-28.44, -25.36] |
| 5x5 | A* | CARE - Dynamo-style Merkle AE | +0.1300 [+0.1000, +0.1625] | +0.789 | +0.00 [+0.00, +0.00] | -19.93 [-20.29, -19.57] |
| 5x5 | A* | CARE - Partitioned IBLT | +0.1100 [+0.0775, +0.1425] | +0.670 | +0.00 [+0.00, +0.00] | -99.55 [-99.85, -99.24] |
| 5x5 | D* Lite | CARE - Scuttlebutt-Depth | +0.0800 [+0.0475, +0.1150] | +0.461 | +0.00 [+0.00, +0.00] | -27.54 [-29.17, -25.95] |
| 5x5 | D* Lite | CARE - Dynamo-style Merkle AE | +0.1575 [+0.1225, +0.1925] | +0.875 | +0.00 [+0.00, +0.00] | -20.30 [-20.67, -19.94] |
| 5x5 | D* Lite | CARE - Partitioned IBLT | +0.1450 [+0.1100, +0.1800] | +0.813 | +0.00 [+0.00, +0.00] | -99.62 [-99.89, -99.34] |
| 7x7 | A* | CARE - Scuttlebutt-Depth | +0.1325 [+0.0825, +0.1825] | +0.515 | -0.29 [-0.41, -0.17] | -37.42 [-39.32, -35.52] |
| 7x7 | A* | CARE - Dynamo-style Merkle AE | +0.1950 [+0.1600, +0.2325] | +1.027 | -0.39 [-0.49, -0.29] | -22.78 [-23.12, -22.43] |
| 7x7 | A* | CARE - Partitioned IBLT | +0.1625 [+0.1250, +0.2000] | +0.844 | -0.32 [-0.42, -0.23] | -100.38 [-100.79, -99.97] |
| 7x7 | D* Lite | CARE - Scuttlebutt-Depth | +0.1400 [+0.0900, +0.1900] | +0.540 | -0.32 [-0.44, -0.20] | -37.75 [-39.64, -35.86] |
| 7x7 | D* Lite | CARE - Dynamo-style Merkle AE | +0.1900 [+0.1550, +0.2275] | +1.027 | -0.40 [-0.50, -0.30] | -22.88 [-23.22, -22.54] |
| 7x7 | D* Lite | CARE - Partitioned IBLT | +0.1550 [+0.1200, +0.1925] | +0.843 | -0.33 [-0.42, -0.24] | -100.42 [-100.81, -100.02] |
