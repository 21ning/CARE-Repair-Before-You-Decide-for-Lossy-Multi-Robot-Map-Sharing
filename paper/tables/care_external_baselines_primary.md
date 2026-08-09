# Published reconciliation baselines at 30% packet loss

100 independent matched maps; mean ± sample SD and 20,000-draw map-cluster 95% CI.

| Planner | Method | CSR mean ± SD [95% CI] | Attempted KB mean ± SD | Path-truth error |
| --- | --- | ---: | ---: | ---: |
| A* | One-shot | 0.6713 ± 0.1031 [0.6512, 0.6913] | 47.62 ± 1.63 | 0.2357 |
| A* | Retry-All ARQ | 0.7588 ± 0.0910 [0.7400, 0.7762] | 154.45 ± 4.16 | 0.2337 |
| A* | Scuttlebutt-Depth | 0.7125 ± 0.1013 [0.6925, 0.7325] | 80.15 ± 7.91 | 0.2512 |
| A* | Dynamo-style Merkle AE | 0.6713 ± 0.1031 [0.6512, 0.6913] | 73.18 ± 2.16 | 0.2357 |
| A* | Partitioned IBLT | 0.6813 ± 0.1042 [0.6613, 0.7025] | 152.80 ± 1.89 | 0.2353 |
| A* | CARE | 0.7362 ± 0.0938 [0.7175, 0.7550] | 53.25 ± 1.26 | 0.2372 |
| D* Lite | One-shot | 0.6900 ± 0.1073 [0.6687, 0.7113] | 47.78 ± 1.56 | 0.2351 |
| D* Lite | Retry-All ARQ | 0.7863 ± 0.0839 [0.7700, 0.8025] | 155.00 ± 4.01 | 0.2340 |
| D* Lite | Scuttlebutt-Depth | 0.7288 ± 0.0990 [0.7087, 0.7475] | 80.80 ± 8.37 | 0.2515 |
| D* Lite | Dynamo-style Merkle AE | 0.6900 ± 0.1073 [0.6687, 0.7113] | 73.56 ± 2.28 | 0.2351 |
| D* Lite | Partitioned IBLT | 0.6963 ± 0.1084 [0.6750, 0.7175] | 152.87 ± 1.83 | 0.2354 |
| D* Lite | CARE | 0.7688 ± 0.0963 [0.7500, 0.7875] | 53.25 ± 1.22 | 0.2363 |
