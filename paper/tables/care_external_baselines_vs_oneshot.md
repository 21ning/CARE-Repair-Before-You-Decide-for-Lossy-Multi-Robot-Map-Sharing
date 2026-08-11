# Published reconciliation baselines paired against One-shot

All comparisons use 30% loss and 100 matched maps. Positive ΔCSR favors the external method; positive ΔKB means extra traffic.

| FOV | Planner | Comparison | ΔCSR [95% CI] | paired d_z | ΔEL [95% CI] | ΔKB [95% CI] |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 3x3 | A* | Scuttlebutt-Depth - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +23.02 [+22.13, +23.87] |
| 3x3 | A* | Dynamo-style Merkle AE - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +26.78 [+26.52, +27.03] |
| 3x3 | A* | Partitioned IBLT - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +103.09 [+102.99, +103.20] |
| 3x3 | D* Lite | Scuttlebutt-Depth - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +23.02 [+22.14, +23.87] |
| 3x3 | D* Lite | Dynamo-style Merkle AE - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +26.78 [+26.52, +27.02] |
| 3x3 | D* Lite | Partitioned IBLT - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +103.09 [+102.99, +103.20] |
| 5x5 | A* | Scuttlebutt-Depth - One-shot | +0.0413 [+0.0187, +0.0625] | +0.372 | +0.00 [+0.00, +0.00] | +32.53 [+31.03, +34.06] |
| 5x5 | A* | Dynamo-style Merkle AE - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +25.56 [+25.31, +25.82] |
| 5x5 | A* | Partitioned IBLT - One-shot | +0.0100 [+0.0037, +0.0175] | +0.293 | +0.00 [+0.00, +0.00] | +105.18 [+104.99, +105.38] |
| 5x5 | D* Lite | Scuttlebutt-Depth - One-shot | +0.0387 [+0.0175, +0.0600] | +0.351 | +0.00 [+0.00, +0.00] | +33.01 [+31.45, +34.63] |
| 5x5 | D* Lite | Dynamo-style Merkle AE - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +25.77 [+25.49, +26.06] |
| 5x5 | D* Lite | Partitioned IBLT - One-shot | +0.0063 [+0.0013, +0.0125] | +0.228 | +0.00 [+0.00, +0.00] | +105.09 [+104.91, +105.26] |
| 7x7 | A* | Scuttlebutt-Depth - One-shot | +0.0312 [+0.0025, +0.0587] | +0.219 | -0.10 [-0.21, +0.00] | +39.87 [+37.96, +41.78] |
| 7x7 | A* | Dynamo-style Merkle AE - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +25.22 [+24.91, +25.54] |
| 7x7 | A* | Partitioned IBLT - One-shot | +0.0163 [+0.0075, +0.0250] | +0.355 | -0.07 [-0.12, -0.02] | +102.83 [+102.45, +103.19] |
| 7x7 | D* Lite | Scuttlebutt-Depth - One-shot | +0.0250 [-0.0037, +0.0525] | +0.175 | -0.08 [-0.19, +0.03] | +40.13 [+38.24, +42.05] |
| 7x7 | D* Lite | Dynamo-style Merkle AE - One-shot | +0.0000 [+0.0000, +0.0000] | +0.000 | +0.00 [+0.00, +0.00] | +25.26 [+24.93, +25.59] |
| 7x7 | D* Lite | Partitioned IBLT - One-shot | +0.0175 [+0.0100, +0.0262] | +0.401 | -0.07 [-0.12, -0.02] | +102.80 [+102.41, +103.17] |
