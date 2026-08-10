# Task-aware mechanism diagnostics

| FOV | Planner | Method | Query cells/check | Query cells/episode | Counterfactual plans/episode | Method CPU ms |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 3x3 | A* | Path-Aware Top-K | 3.969 | 793.70 | 0.00 | 6.2 |
| 3x3 | A* | Single-Cell Sensitivity | 1.900 | 380.00 | 794.61 | 140.1 |
| 3x3 | A* | CARE | 3.014 | 602.72 | 3539.60 | 841.5 |
| 3x3 | D* Lite | Path-Aware Top-K | 3.969 | 793.70 | 0.00 | 6.2 |
| 3x3 | D* Lite | Single-Cell Sensitivity | 1.900 | 380.00 | 794.61 | 140.5 |
| 3x3 | D* Lite | CARE | 3.014 | 602.72 | 3539.60 | 832.5 |
| 5x5 | A* | Path-Aware Top-K | 3.415 | 683.02 | 0.00 | 4.9 |
| 5x5 | A* | Single-Cell Sensitivity | 1.485 | 296.99 | 685.05 | 118.1 |
| 5x5 | A* | CARE | 2.411 | 482.19 | 2985.41 | 693.8 |
| 5x5 | D* Lite | Path-Aware Top-K | 3.379 | 675.83 | 0.00 | 4.9 |
| 5x5 | D* Lite | Single-Cell Sensitivity | 1.489 | 297.88 | 678.22 | 117.2 |
| 5x5 | D* Lite | CARE | 2.376 | 475.28 | 2947.33 | 683.3 |
| 7x7 | A* | Path-Aware Top-K | 2.364 | 461.69 | 0.00 | 4.2 |
| 7x7 | A* | Single-Cell Sensitivity | 1.123 | 219.70 | 478.55 | 89.3 |
| 7x7 | A* | CARE | 1.533 | 299.62 | 1848.93 | 421.7 |
| 7x7 | D* Lite | Path-Aware Top-K | 2.362 | 460.94 | 0.00 | 4.2 |
| 7x7 | D* Lite | Single-Cell Sensitivity | 1.129 | 220.77 | 477.81 | 89.2 |
| 7x7 | D* Lite | CARE | 1.536 | 299.90 | 1848.11 | 421.8 |
