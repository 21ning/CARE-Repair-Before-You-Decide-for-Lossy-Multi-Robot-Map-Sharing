# CARE method gate and cross-planner evidence

The final gate uses 100 complete independent `multifork_cluttered` maps. Every
policy/planner/delay cell uses the same 100 layouts and matched deterministic
packet-loss traces. The matrix contains 3,200 complete episodes:

- planners: A* and incremental D* Lite;
- one-way delays: 0, 1, 2, and 4 steps;
- policies: One-shot, Action-triggered, PSR-UT, and deadline-aware CARE;
- loss probability: 0.30;
- workers: 32.

## Primary result (zero delay)

| Planner | Method | CSR mean ± SD [95% CI] | Attempted KB mean ± SD | Planning CPU ms |
|---|---|---:|---:|---:|
| A* | One-shot | 0.8400 ± 0.1067 [0.8187, 0.8600] | 65.35 ± 1.24 | 37.78 |
| A* | PSR-UT | 0.9325 ± 0.0803 [0.9163, 0.9475] | 75.77 ± 1.36 | 41.74 |
| A* | CARE | 0.9375 ± 0.0843 [0.9213, 0.9537] | 68.63 ± 1.27 | 42.14 |
| D* Lite | One-shot | 0.8462 ± 0.1079 [0.8250, 0.8675] | 65.30 ± 1.08 | 142.77 |
| D* Lite | PSR-UT | 0.9313 ± 0.0821 [0.9150, 0.9463] | 75.64 ± 1.40 | 156.07 |
| D* Lite | CARE | 0.9400 ± 0.0842 [0.9225, 0.9563] | 68.62 ± 1.11 | 156.02 |

Paired CARE differences at zero delay:

| Planner | Comparator | CSR difference [95% CI] | Byte difference [95% CI] |
|---|---|---:|---:|
| A* | One-shot | +0.0975 [+0.0800, +0.1163] | +3.28 KB [+3.04, +3.50] |
| A* | PSR-UT | +0.0050 [-0.0125, +0.0225] | -7.15 KB [-7.39, -6.91] |
| D* Lite | One-shot | +0.0938 [+0.0762, +0.1125] | +3.32 KB [+3.13, +3.50] |
| D* Lite | PSR-UT | +0.0088 [-0.0088, +0.0262] | -7.03 KB [-7.25, -6.80] |

The preregistered implementation gate required (a) a paired 95% CI above a
-0.02 CSR non-inferiority margin versus PSR-UT, (b) a traffic CI entirely at
or below zero versus PSR-UT, and (c) a positive CSR CI versus One-shot. CARE
passes all three conditions under both planners.

## Deadline evidence

The mean receiver-local slack is approximately 4.1 steps. At delay 2
(`L_rtt=4`), roughly half of candidate repairs remain feasible; CARE and PSR-UT
both reach 0.8550 A* CSR, but CARE saves 11.78 KB. At delay 4 (`L_rtt=8`), no
repair can arrive before the derived deadline. CARE therefore sends no repair,
matches One-shot and PSR-UT at 0.7388 CSR, and saves 17.35 KB versus PSR-UT.
This is the intended behavior of the deadline constraint: it removes traffic
whose information cannot affect the decision in time.

## Planner sensitivity and overhead

For CARE at zero delay, D* Lite minus A* is +0.0025 CSR with 95% CI
[-0.0025, +0.0075], and -9.8 attempted bytes with CI [-143.5, +121.3]. The
communication operating point is therefore insensitive to planner choice.

The Python D* Lite reference is slower on these small maps: CARE planning takes
156.02 ms per episode versus 42.14 ms with A*. Within planner, CARE adds 4.36
ms over A* One-shot and 13.25 ms over D* Lite One-shot. D* Lite is included as
a planner-independence check, not as a speed claim.

The exact reproducible command and result schema are documented in
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md). The method definition is in
[`CARE_ALGORITHM.md`](CARE_ALGORITHM.md).
