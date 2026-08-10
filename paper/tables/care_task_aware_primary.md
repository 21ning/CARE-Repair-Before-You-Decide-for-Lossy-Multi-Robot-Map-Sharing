# Task-aware baseline ladder at 5x5 sensing and 30% packet loss

100 independent matched maps; mean ± sample SD and map-cluster 95% CI.

| Planner | Method | CSR mean ± SD [95% CI] | Attempted KB | Episode CPU ms |
| --- | --- | ---: | ---: | ---: |
| A* | One-shot | 0.6713 ± 0.1031 [0.6512, 0.6913] | 47.62 | 206.6 |
| A* | Retry-All ARQ | 0.7588 ± 0.0910 [0.7412, 0.7762] | 154.45 | 742.3 |
| A* | Path-Weighted ARQ | 0.7588 ± 0.0910 [0.7412, 0.7762] | 154.50 | 764.9 |
| A* | PSR-UT | 0.7350 ± 0.0978 [0.7163, 0.7538] | 62.71 | 234.1 |
| A* | CARE-Lite | 0.7400 ± 0.0883 [0.7225, 0.7575] | 57.00 | 227.2 |
| A* | Path-Aware Top-K | 0.7275 ± 0.0930 [0.7100, 0.7462] | 54.37 | 219.7 |
| A* | Single-Cell Sensitivity | 0.7325 ± 0.0906 [0.7150, 0.7500] | 52.11 | 332.7 |
| A* | CARE | 0.7362 ± 0.0938 [0.7175, 0.7538] | 53.25 | 909.7 |
| D* Lite | One-shot | 0.6900 ± 0.1073 [0.6687, 0.7113] | 47.78 | 305.9 |
| D* Lite | Retry-All ARQ | 0.7863 ± 0.0839 [0.7700, 0.8025] | 155.00 | 845.0 |
| D* Lite | Path-Weighted ARQ | 0.7863 ± 0.0839 [0.7700, 0.8025] | 155.09 | 866.3 |
| D* Lite | PSR-UT | 0.7638 ± 0.0904 [0.7462, 0.7812] | 62.74 | 330.6 |
| D* Lite | CARE-Lite | 0.7712 ± 0.0871 [0.7538, 0.7887] | 57.06 | 325.0 |
| D* Lite | Path-Aware Top-K | 0.7612 ± 0.0942 [0.7425, 0.7788] | 54.39 | 314.6 |
| D* Lite | Single-Cell Sensitivity | 0.7625 ± 0.0915 [0.7450, 0.7800] | 52.23 | 427.9 |
| D* Lite | CARE | 0.7688 ± 0.0963 [0.7500, 0.7875] | 53.25 | 994.1 |
