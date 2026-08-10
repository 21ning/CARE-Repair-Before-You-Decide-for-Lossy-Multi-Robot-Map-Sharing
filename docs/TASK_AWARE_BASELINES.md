# Task-aware repair baseline ladder

This study isolates whether CARE's measured benefit comes from knowing the
receiver path, testing individual decision sensitivity, or separating joint
uncertainty scenarios. It uses the same `PSRClosedLoopRunner`, versioned
replicas and binary query--patch exchange for every repair method.

## Methods

### Path-Aware Top-K Repair

The receiver collects UNKNOWN cells on or one action-graph hop from the next
`H=8` optimistic path vertices. In this static-map benchmark, a lost first
observation leaves a cell UNKNOWN, so this set covers the relevant missed
updates without pretending to know which peer cells are stale. Candidates are
ordered by:

1. earliest future path index they can influence;
2. graph distance from that path vertex;
3. canonical coordinate order.

The first eight candidates are queried. The method does no counterfactual
planning, scenario enumeration, truth-map lookup or peer-memory lookup.

### Single-Cell Decision Sensitivity

For each of the same first eight candidates, the receiver compares its current
optimistic path (the candidate-free case) with one canonical A* replan in which
only that candidate is blocked. Reusing the already computed optimistic path
avoids a redundant free-case replan. Immediate next-action changes rank first,
then later changes by earliest path divergence. A cell whose divergence occurs
before the query--patch round trip is excluded.

Each candidate is evaluated independently. The method never constructs a
two-cell scenario, compares scenario pairs or solves a hitting set.

### CARE

CARE uses the same capped candidates but enumerates the declared `q=2` sparse
scenario family. Its minimum hitting set separates every action-conflicting
scenario pair that can still be repaired in time. This is the only ladder
method with a joint-scenario certificate.

## Fair communication contract

Path-Aware, Single-Cell and CARE share:

- at most eight query cells, hence at most `16 + 6×8 = 64` encoded query bytes;
- the same one-peer schedule and repair cadence;
- the same version stamps, query and patch codecs;
- the same 4,459-byte data and 512-byte control caps;
- the same directed packet-loss trace, delay and attempted-byte accounting;
- the same local map, planner interface, starts and goals.

The comparison matches the maximum query budget, not CARE's realized query
length. Giving a heuristic CARE's realized per-step length would leak the
certificate computation into the baseline. Actual query and patch bytes are
therefore allowed to differ and are reported rather than normalized away.

The 180-episode pilot checked protocol activity and compute only. The settings
were frozen before inspecting the complete 4,800-episode result matrix.

## Audited 100-map result

At 5×5 sensing and 30% loss:

| Planner | Method | CSR | Attempted KB | Episode CPU ms |
| --- | --- | ---: | ---: | ---: |
| A* | One-shot | 0.6713 | 47.62 | 206.6 |
| A* | Path-Aware Top-K | 0.7275 | 54.37 | 219.7 |
| A* | Single-Cell Sensitivity | 0.7325 | 52.11 | 332.7 |
| A* | CARE-Lite | 0.7400 | 57.00 | 227.2 |
| A* | CARE | 0.7362 | 53.25 | 909.7 |
| D* Lite | One-shot | 0.6900 | 47.78 | 305.9 |
| D* Lite | Path-Aware Top-K | 0.7612 | 54.39 | 314.6 |
| D* Lite | Single-Cell Sensitivity | 0.7625 | 52.23 | 427.9 |
| D* Lite | CARE-Lite | 0.7712 | 57.06 | 325.0 |
| D* Lite | CARE | 0.7688 | 53.25 | 994.1 |

Path awareness explains most of the improvement over One-shot. Path-Aware
gains `+0.0563 [0.0425, 0.0712]` CSR with A* and
`+0.0712 [0.0550, 0.0875]` with D* Lite. Single-Cell gains
`+0.0612 [0.0462, 0.0775]` and `+0.0725 [0.0563, 0.0887]` while sending
about 2.2 KB less than Path-Aware.

CARE minus Path-Aware is `+0.0088 [0.0013, 0.0175]` CSR and `-1.12 KB` with
A*, and `+0.0075 [0.0000, 0.0150]` and `-1.13 KB` with D* Lite. Against the
stronger Single-Cell baseline, however, CARE's primary CSR differences are
only `+0.0037 [-0.0037, 0.0125]` and `+0.0063 [-0.0013, 0.0150]`, while CARE
sends 1.14/1.03 KB more. The data therefore do not support a claim that exact
joint certification materially improves primary-condition reliability over
all task-aware heuristics.

Mechanistically, at 5×5 A* Path-Aware queries 683 cells per episode with no
counterfactual plans; Single-Cell queries 297 cells using 685 independent
replans; CARE queries 482 cells using 2,985 joint-scenario replans. CARE's
distinguishing contribution is its bounded joint-scenario guarantee and its
compression relative to broad path/deadline heuristics, not universal
empirical dominance. Single-Cell is the lightweight empirical alternative.

At 3×3 all ladder methods remain at 0.5000 CSR. At 7×7 A*, Path-Aware and CARE
both reach 0.9375, while Single-Cell reaches 0.9237; all paired CARE-versus-
heuristic CIs still include zero. Full FOV means, paired effects and mechanism
counts are in `paper/tables/care_task_aware_*.{csv,md}`.
