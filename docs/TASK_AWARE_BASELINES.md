# Task-aware and closest-work repair ladder

This ladder tests whether the measured gain comes from using the receiver's
path, independent action sensitivity, a literature-inspired utility objective,
or CARE's joint-scenario separation certificate. All methods operate on the
same receiver-local versioned replica and exact-cell query--patch codec.

## Native task-aware controls

### Path-Aware Top-K

Collect UNKNOWN cells on or one action-graph hop from the next `H=8`
optimistic path vertices. Rank by earliest path index, graph distance and
canonical coordinate; query the first eight. It performs no counterfactual
planning or truth/peer-memory lookup.

### Single-Cell Decision Sensitivity

For each of the same first eight candidates, compare the current optimistic
path with one replan in which only that cell is blocked. Rank immediate
next-action changes before later divergence and reject divergences before the
query--patch round trip. Cells are evaluated independently: there is no joint
scenario pair or hitting set.

### CARE-Lite

Compare optimistic and pessimistic paths and query a hand-built influence set
between their split and reconvergence. It is a lightweight rule-based method,
not an exact certificate.

### CARE

Enumerate the declared `q=2` sparse scenario family, identify action-conflicting
pairs in scope, and solve the exact minimum uniform-byte hitting set that
distinguishes every pair. This is the only ladder method with the bounded
joint-scenario separation guarantee. Final CARE includes only pairs whose first
action divergence is no earlier than the query--patch round trip and appends no
auxiliary route witness.

## Literature-inspired controls

The new closest-work matrix adds:

- `OCBC-FS`: receiver-local Bernoulli world sampling and finite-horizon
  safe-progress arms;
- `PGSC`: greedy path-weighted spatial coverage over a bounded proposal pool;
- `Bernoulli R-D`: path-weighted `q(1-q)` distortion reduction at the common
  exact-cell rate;
- `VoI/byte`: independent blocked-cell progress gain divided by actual marginal
  query plus patch bytes.

These are **codec-matched inspired adaptations**, not exact reproductions of
OCBC, path-guided multiresolution compression, continuous rate--distortion
coding or a complete VoI middleware. Their native representations and
optimizers do not match binary exact-cell repair. The fidelity boundary is
spelled out in [`CLOSEST_WORK_ADAPTATIONS.md`](CLOSEST_WORK_ADAPTATIONS.md).

## Fair communication contract

All ladder policies share:

- the receiver's explicit local replica, goal and planner interface;
- at most eight query cells (`16 + 6×8 = 64` encoded query bytes);
- one-peer schedule, cadence, version stamps and query/patch codecs;
- 4,459-byte data and 512-byte control caps;
- the same layout, directed packet-loss trace, delay and attempted-byte
  accounting.

The common constraint is the maximum query budget, not CARE's realized query
length. Giving another method that length would leak certificate computation.
Actual patch/traffic totals are therefore reported, not normalized away.
Algorithmic Monte Carlo seeds are separate from link seeds.

## Controlled 100-map result

The role-aware closest-work run contains 6,000 executions across three FOVs,
two planners and ten policies. The primary endpoint is seeker CSR; overall CSR
is a diagnostic because the fixed multifork observers all complete.

At 5×5 and 30% loss:

| Planner | Method | Seeker CSR mean ± SD [95% CI] | Attempted KB | CPU ms |
| --- | --- | ---: | ---: | ---: |
| A* | One-shot | 0.3425 ± 0.2061 [0.3025, 0.3825] | 47.62 | 305.2 |
| A* | Path-Aware Top-K | 0.4550 ± 0.1859 [0.4200, 0.4900] | 54.37 | 324.4 |
| A* | Single-Cell | 0.4650 ± 0.1813 [0.4300, 0.5000] | 52.11 | 487.0 |
| A* | CARE-Lite | 0.4800 ± 0.1765 [0.4450, 0.5150] | 57.00 | 344.9 |
| A* | OCBC-FS (adapt.) | 0.4725 ± 0.1808 [0.4375, 0.5075] | 52.57 | 801.4 |
| A* | PGSC (adapt.) | 0.4800 ± 0.1869 [0.4425, 0.5150] | 62.79 | 1434.2 |
| A* | Bernoulli R-D (adapt.) | 0.4800 ± 0.1801 [0.4450, 0.5150] | 62.74 | 4649.7 |
| A* | VoI/byte (adapt.) | 0.4600 ± 0.1837 [0.4250, 0.4950] | 52.49 | 607.1 |
| A* | CARE | 0.4725 ± 0.1877 [0.4350, 0.5075] | 53.25 | 1350.8 |
| D* Lite | One-shot | 0.3800 ± 0.2146 [0.3375, 0.4225] | 47.78 | 478.4 |
| D* Lite | Path-Aware Top-K | 0.5225 ± 0.1883 [0.4850, 0.5600] | 54.39 | 510.8 |
| D* Lite | Single-Cell | 0.5250 ± 0.1829 [0.4900, 0.5600] | 52.23 | 663.8 |
| D* Lite | CARE-Lite | 0.5425 ± 0.1743 [0.5075, 0.5775] | 57.06 | 512.1 |
| D* Lite | OCBC-FS (adapt.) | 0.5350 ± 0.1742 [0.5000, 0.5700] | 52.54 | 984.8 |
| D* Lite | PGSC (adapt.) | 0.5350 ± 0.1914 [0.4975, 0.5725] | 62.87 | 1693.6 |
| D* Lite | Bernoulli R-D (adapt.) | 0.5350 ± 0.1847 [0.4975, 0.5700] | 62.88 | 4975.9 |
| D* Lite | VoI/byte (adapt.) | 0.5325 ± 0.1835 [0.4975, 0.5675] | 52.56 | 791.1 |
| D* Lite | CARE | 0.5375 ± 0.1926 [0.5000, 0.5750] | 53.25 | 1561.6 |

Key paired CARE effects at 5×5:

| Comparator | A* Δ seeker CSR [95% CI] | D* Lite Δ seeker CSR [95% CI] | A*/D* ΔKB |
| --- | ---: | ---: | ---: |
| Path-Aware | +0.0175 [+0.0025, +0.0325] | +0.0150 [+0.0000, +0.0300] | -1.12/-1.13 |
| Single-Cell | +0.0075 [-0.0075, +0.0250] | +0.0125 [-0.0025, +0.0300] | +1.14/+1.03 |
| CARE-Lite | -0.0075 [-0.0275, +0.0125] | -0.0050 [-0.0250, +0.0150] | -3.74/-3.81 |
| OCBC-FS (adapt.) | 0.0000 [-0.0175, +0.0175] | +0.0025 [-0.0125, +0.0175] | +0.69/+0.72 |
| PGSC (adapt.) | -0.0075 [-0.0275, +0.0150] | +0.0025 [-0.0200, +0.0250] | -9.54/-9.61 |
| Bernoulli R-D (adapt.) | -0.0075 [-0.0250, +0.0100] | +0.0025 [-0.0150, +0.0200] | -9.49/-9.63 |
| VoI/byte (adapt.) | +0.0125 [-0.0025, +0.0275] | +0.0050 [-0.0150, +0.0225] | +0.76/+0.69 |

The evidence does not support the claim that exact certification materially
raises reliability above every task-aware/closest-work control. CARE's supported
distinction is a bounded joint-scenario guarantee and lower traffic than broad
PGSC/R-D queries. Single-Cell is the stronger lightweight compute alternative.

At 3×3 every ladder method has zero seeker completion; communication cannot
invent map context. Most 7×7 CARE-versus-control intervals include zero. These
negative/ambiguous cells remain part of the claim boundary.

Full means, SDs, paired map-cluster CIs, effect sizes and mechanism counts are
in `paper/tables/care_closest_work_*`.
