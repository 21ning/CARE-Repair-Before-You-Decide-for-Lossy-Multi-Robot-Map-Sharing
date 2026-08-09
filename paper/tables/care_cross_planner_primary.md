# CARE cross-planner primary result

100 independent maps; 30% loss; zero link delay. CIs bootstrap independent maps.

| Planner | Method | CSR mean ± SD [95% CI] | Attempted KB mean ± SD | Planning CPU ms |
|---|---|---:|---:|---:|
| astar | One-shot | 0.8400 ± 0.1067 [0.8187, 0.8600] | 65.35 ± 1.24 | 37.78 |
| astar | PSR-UT | 0.9325 ± 0.0803 [0.9163, 0.9475] | 75.77 ± 1.36 | 41.74 |
| astar | CARE-Lite | 0.9375 ± 0.0843 [0.9213, 0.9537] | 68.63 ± 1.27 | 42.14 |
| dstar_lite | One-shot | 0.8462 ± 0.1079 [0.8250, 0.8675] | 65.30 ± 1.08 | 142.77 |
| dstar_lite | PSR-UT | 0.9313 ± 0.0821 [0.9150, 0.9463] | 75.64 ± 1.40 | 156.07 |
| dstar_lite | CARE-Lite | 0.9400 ± 0.0842 [0.9225, 0.9563] | 68.62 ± 1.11 | 156.02 |
