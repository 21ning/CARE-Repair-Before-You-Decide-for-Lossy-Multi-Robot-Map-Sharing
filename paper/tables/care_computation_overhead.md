# CARE computation overhead (frozen 5x5 anchor)

All values are per-episode process CPU or episode-total mechanism counts over 100 paired maps at 30% loss and zero delay. Brackets are 95% CIs from the shared 20,000-draw map-cluster bootstrap.

`CARE / method` is the ratio of paired-map CPU sums (equivalently, the ratio of means here), not the mean of per-map ratios. Its paired bootstrap preserves each map's numerator/denominator pair. This avoids inflation from small individual denominators.

## A*

| Method | Episode CPU ms, mean ± SD [95% CI] | Instrumented planning-block CPU ms, mean ± SD [95% CI] | Certificate CPU ms, mean ± SD [95% CI] | Extra plans / cert. scenario plans | Candidate / query cells | CARE−method episode CPU ms [95% CI] | CARE / method [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| One-shot | 305.2 ± 70.0 [292.7, 319.9] | 52.8 ± 14.1 [50.3, 55.8] | 0.0 ± 0.0 [0.0, 0.0] | 0.0 ± 0.0 [0.0, 0.0] / 0.0 ± 0.0 [0.0, 0.0] | n/r / 0.0 ± 0.0 [0.0, 0.0] | +1045.6 [+997.3, +1102.3] | 4.43 [4.22, 4.64] |
| Path Top-K | 324.4 ± 76.1 [310.8, 340.5] | 50.3 ± 14.1 [47.7, 53.3] | 0.0 ± 0.0 [0.0, 0.0] | 0.0 ± 0.0 [0.0, 0.0] / 0.0 ± 0.0 [0.0, 0.0] | 1151.6 ± 50.6 [1141.7, 1161.6] / 683.0 ± 25.8 [678.0, 688.1] | +1026.4 [+971.8, +1088.9] | 4.16 [3.91, 4.43] |
| Single-Cell | 487.0 ± 105.0 [468.7, 509.3] | 224.6 ± 54.8 [215.0, 236.1] | 0.0 ± 0.0 [0.0, 0.0] | 685.0 ± 25.7 [680.0, 690.1] / 0.0 ± 0.0 [0.0, 0.0] | 1154.6 ± 50.5 [1144.7, 1164.6] / 297.0 ± 12.1 [294.6, 299.4] | +863.8 [+806.1, +929.0] | 2.77 [2.61, 2.94] |
| CARE-Lite | 344.9 ± 88.4 [328.7, 363.1] | 59.1 ± 19.5 [55.6, 63.1] | 0.0 ± 0.0 [0.0, 0.0] | 200.0 ± 0.0 [200.0, 200.0] / 0.0 ± 0.0 [0.0, 0.0] | n/r / 1130.3 ± 55.7 [1119.4, 1141.2] | +1005.9 [+951.4, +1067.8] | 3.92 [3.68, 4.17] |
| CARE | 1350.8 ± 289.0 [1298.9, 1411.3] | 1077.0 ± 240.4 [1033.8, 1127.4] | 1026.0 ± 228.6 [984.9, 1073.8] | 2985.4 ± 122.4 [2961.7, 3009.4] / 2985.4 ± 122.4 [2961.7, 3009.4] | 683.8 ± 25.8 [678.8, 688.9] / 482.2 ± 25.4 [477.2, 487.1] | +0.0 [+0.0, +0.0] | 1.00 [1.00, 1.00] |

## D* Lite

| Method | Episode CPU ms, mean ± SD [95% CI] | Instrumented planning-block CPU ms, mean ± SD [95% CI] | Certificate CPU ms, mean ± SD [95% CI] | Extra plans / cert. scenario plans | Candidate / query cells | CARE−method episode CPU ms [95% CI] | CARE / method [95% CI] |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| One-shot | 478.4 ± 128.3 [454.9, 504.8] | 214.6 ± 65.7 [202.6, 228.1] | 0.0 ± 0.0 [0.0, 0.0] | 0.0 ± 0.0 [0.0, 0.0] / 0.0 ± 0.0 [0.0, 0.0] | n/r / 0.0 ± 0.0 [0.0, 0.0] | +1083.2 [+993.8, +1182.7] | 3.26 [3.03, 3.52] |
| Path Top-K | 510.8 ± 153.9 [482.1, 542.0] | 215.7 ± 75.3 [201.7, 230.9] | 0.0 ± 0.0 [0.0, 0.0] | 0.0 ± 0.0 [0.0, 0.0] / 0.0 ± 0.0 [0.0, 0.0] | 1147.6 ± 52.1 [1137.4, 1157.9] / 675.8 ± 25.1 [670.9, 680.8] | +1050.8 [+957.0, +1154.3] | 3.06 [2.81, 3.33] |
| Single-Cell | 663.8 ± 178.9 [631.5, 701.2] | 389.2 ± 118.5 [367.8, 414.0] | 0.0 ± 0.0 [0.0, 0.0] | 678.2 ± 24.9 [673.4, 683.1] / 0.0 ± 0.0 [0.0, 0.0] | 1150.2 ± 49.8 [1140.5, 1160.0] / 297.9 ± 13.3 [295.3, 300.5] | +897.8 [+802.1, +1003.1] | 2.35 [2.17, 2.55] |
| CARE-Lite | 512.1 ± 144.2 [485.9, 541.5] | 219.7 ± 71.2 [206.7, 234.3] | 0.0 ± 0.0 [0.0, 0.0] | 200.0 ± 0.0 [200.0, 200.0] / 0.0 ± 0.0 [0.0, 0.0] | n/r / 1128.6 ± 56.5 [1117.5, 1139.6] | +1049.5 [+954.4, +1154.0] | 3.05 [2.81, 3.31] |
| CARE | 1561.6 ± 480.8 [1473.7, 1659.6] | 1276.6 ± 408.9 [1201.9, 1359.9] | 1064.8 ± 335.8 [1003.4, 1133.3] | 2947.3 ± 122.4 [2923.7, 2971.4] / 2947.3 ± 122.4 [2923.7, 2971.4] | 675.9 ± 25.7 [670.9, 680.9] / 475.3 ± 26.1 [470.2, 480.4] | +0.0 [+0.0, +0.0] | 1.00 [1.00, 1.00] |

`n/r` means not recorded as a distinct pool: One-shot has no repair selector, while CARE-Lite records only its selected influence/query cells. Extra plans exclude the 400 optimistic operational replans shared by all five methods; they are Single-Cell blocked replans, CARE-Lite pessimistic replans, or CARE scenario replans as applicable.

The planning-block timer is instrumentation-specific and is not the cross-method primary runtime: it surrounds the full selector for CARE and Single-Cell, only the pessimistic plan for CARE-Lite, and excludes the Path Top-K selector. Use total episode CPU for method comparisons. Candidate totals are also differently scoped: Path/Single report their uncapped proposal pools, whereas CARE reports post-cap scenario candidates; they are mechanism diagnostics, not like-for-like sizes.

Timing uses `time.process_time()` in the frozen 32-worker batch. The workers parallelized independent episodes; CARE itself was not a 32-core algorithm within an episode. The intervals quantify between-map variation in that run, not machine-to-machine or repeated-run timing uncertainty; process CPU is not parallel wall-clock latency. Accordingly, these results support a material exact-certificate compute-cost claim, not a real-time latency guarantee.

CARE, Path Top-K and Single-Cell use the additional 8-cell/64-byte algorithmic query cap. CARE-Lite uses the same codec and 512-byte control channel but may query up to 82 cells (508 encoded bytes); its CPU ratio is therefore an implementation comparison, not a query-cap-matched one.
