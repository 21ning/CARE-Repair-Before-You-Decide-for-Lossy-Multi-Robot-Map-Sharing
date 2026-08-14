# Paired 5x5 CARE comparisons

Differences are CARE minus the matched method on the same map and loss trace; reliability rows use derived seeker CSR.

| Planner | Comparator | Metric | Difference [95% CI] | paired d_z |
| --- | --- | --- | ---: | ---: |
| A* | One-shot | Derived seeker CSR | +0.1300 [+0.1000, +0.1625] | +0.789 |
| A* | One-shot | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | One-shot | Attempted KB | +5.6340 [+5.3893, +5.8834] | +4.440 |
| A* | Retry-All ARQ | Derived seeker CSR | -0.0450 [-0.0675, -0.0250] | -0.413 |
| A* | Retry-All ARQ | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | Retry-All ARQ | Attempted KB | -101.2005 [-101.9050, -100.4532] | -27.326 |
| A* | Path-weighted ARQ | Derived seeker CSR | -0.0450 [-0.0675, -0.0250] | -0.413 |
| A* | Path-weighted ARQ | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | Path-weighted ARQ | Attempted KB | -101.2504 [-101.9728, -100.4947] | -26.708 |
| A* | Periodic Full | Derived seeker CSR | -0.0250 [-0.0475, -0.0025] | -0.217 |
| A* | Periodic Full | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | Periodic Full | Attempted KB | -243.3447 [-243.5698, -243.1162] | -208.924 |
| A* | Mismatch Full | Derived seeker CSR | +0.0075 [-0.0175, +0.0325] | +0.058 |
| A* | Mismatch Full | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | Mismatch Full | Attempted KB | -434.3872 [-439.5528, -429.1298] | -16.310 |
| A* | Action-triggered | Derived seeker CSR | +0.1300 [+0.1000, +0.1625] | +0.789 |
| A* | Action-triggered | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | Action-triggered | Attempted KB | +3.3931 [+3.1508, +3.6398] | +2.706 |
| A* | Full-replica scope | Derived seeker CSR | +0.1250 [+0.0925, +0.1576] | +0.742 |
| A* | Full-replica scope | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | Full-replica scope | Attempted KB | -102.1100 [-102.4818, -101.7395] | -53.656 |
| A* | PSR-UT | Derived seeker CSR | +0.0025 [-0.0150, +0.0225] | +0.026 |
| A* | PSR-UT | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | PSR-UT | Attempted KB | -9.4614 [-9.6572, -9.2733] | -9.636 |
| A* | CARE-Lite | Derived seeker CSR | -0.0075 [-0.0275, +0.0125] | -0.077 |
| A* | CARE-Lite | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| A* | CARE-Lite | Attempted KB | -3.7430 [-3.9556, -3.5385] | -3.523 |
| D* Lite | One-shot | Derived seeker CSR | +0.1575 [+0.1225, +0.1925] | +0.875 |
| D* Lite | One-shot | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | One-shot | Attempted KB | +5.4699 [+5.2577, +5.6863] | +4.985 |
| D* Lite | Retry-All ARQ | Derived seeker CSR | -0.0350 [-0.0550, -0.0175] | -0.348 |
| D* Lite | Retry-All ARQ | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | Retry-All ARQ | Attempted KB | -101.7502 [-102.4356, -101.0253] | -28.347 |
| D* Lite | Path-weighted ARQ | Derived seeker CSR | -0.0350 [-0.0550, -0.0175] | -0.348 |
| D* Lite | Path-weighted ARQ | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | Path-weighted ARQ | Attempted KB | -101.8334 [-102.4780, -101.1601] | -30.131 |
| D* Lite | Periodic Full | Derived seeker CSR | -0.0100 [-0.0350, +0.0125] | -0.082 |
| D* Lite | Periodic Full | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | Periodic Full | Attempted KB | -243.5152 [-243.7458, -243.2823] | -205.970 |
| D* Lite | Mismatch Full | Derived seeker CSR | +0.0375 [+0.0100, +0.0675] | +0.253 |
| D* Lite | Mismatch Full | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | Mismatch Full | Attempted KB | -434.5375 [-438.8248, -430.2107] | -19.637 |
| D* Lite | Action-triggered | Derived seeker CSR | +0.1575 [+0.1225, +0.1925] | +0.875 |
| D* Lite | Action-triggered | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | Action-triggered | Attempted KB | +3.2345 [+3.0250, +3.4476] | +2.990 |
| D* Lite | Full-replica scope | Derived seeker CSR | +0.1575 [+0.1225, +0.1925] | +0.875 |
| D* Lite | Full-replica scope | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | Full-replica scope | Attempted KB | -102.1987 [-102.5130, -101.8828] | -63.527 |
| D* Lite | PSR-UT | Derived seeker CSR | +0.0100 [-0.0125, +0.0325] | +0.089 |
| D* Lite | PSR-UT | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | PSR-UT | Attempted KB | -9.4856 [-9.6948, -9.2875] | -9.146 |
| D* Lite | CARE-Lite | Derived seeker CSR | -0.0050 [-0.0250, +0.0150] | -0.050 |
| D* Lite | CARE-Lite | EL | +0.0000 [+0.0000, +0.0000] | +0.000 |
| D* Lite | CARE-Lite | Attempted KB | -3.8074 [-4.0100, -3.6092] | -3.720 |
