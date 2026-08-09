# CARE cross-planner primary result

100 independent maps; 30% loss; zero link delay. CIs bootstrap independent maps.

| Planner | Method | CSR mean ± SD [95% CI] | Attempted KB mean ± SD | Planning CPU ms |
|---|---|---:|---:|---:|
| astar | One-shot | 0.6713 ± 0.1031 [0.6512, 0.6913] | 47.62 ± 1.63 | 39.82 |
| astar | PSR-UT | 0.7350 ± 0.0978 [0.7163, 0.7538] | 62.71 ± 1.27 | 42.27 |
| astar | CARE-Lite | 0.7400 ± 0.0883 [0.7225, 0.7575] | 57.00 ± 1.40 | 42.95 |
| astar | CARE | 0.7362 ± 0.0938 [0.7175, 0.7538] | 53.25 ± 1.26 | 829.54 |
| dstar_lite | One-shot | 0.6900 ± 0.1073 [0.6687, 0.7113] | 47.78 ± 1.56 | 150.69 |
| dstar_lite | PSR-UT | 0.7638 ± 0.0904 [0.7462, 0.7812] | 62.74 ± 1.16 | 155.07 |
| dstar_lite | CARE-Lite | 0.7712 ± 0.0871 [0.7538, 0.7887] | 57.06 ± 1.35 | 152.87 |
| dstar_lite | CARE | 0.7688 ± 0.0963 [0.7500, 0.7875] | 53.25 ± 1.22 | 929.86 |
