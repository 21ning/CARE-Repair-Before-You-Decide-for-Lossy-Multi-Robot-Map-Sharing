# CARE: Repair Before You Decide

CARE is a research implementation for selective occupancy-map replica repair
between robots communicating over a lossy, delayed link. Every robot maintains
its own initially unknown map, incorporates local observations, sends
version-stamped sparse updates, and plans on its local replica. CARE queries a
small set of uncertain cells only when the remaining occupancy hypotheses can
change an imminent action.

The implementation deliberately uses deterministic A* and incremental D* Lite,
not a learned policy. Its contribution is the communication decision: a bounded
scenario family is replanned, action-conflicting scenario pairs are identified,
and an exact minimum encoded-query-byte hitting set is produced. The response is a
versioned exact-cell patch sent through the same lossy link and byte caps as all
baselines.

![CARE running in POGEMA](assets/pogema_demo.gif)

The animation shows Robot 1's evolving local replica. Gray cells are unknown,
white cells were locally observed, blue cells came from peer messages, and dark
cells are known obstacles. Robot/goal markers are a global motion overlay for
readability; they are not knowledge available to Robot 1. No robot starts at or
immediately beside its goal in this demonstration.

## Evaluation contract

The primary endpoint is **decision-critical seeker completion rate (seeker
CSR)**. The controlled eight-robot multifork maps contain four remote observers
and four seekers. The observers are one step from their goals and complete in
every audited run, so all-robot CSR has a structural 0.5 floor:

```text
overall robot CSR = (1 + seeker CSR) / 2
```

Overall CSR remains in result files only as a diagnostic. Pair success,
observer/seeker completion masks, and censored seeker completion time are also
serialized. Confidence intervals resample whole maps using one fixed public
cluster-resampling index; paired intervals subtract methods on the same map
and deterministic loss trace before resampling.

The 100 controlled maps are independent **background-clutter realizations under
one fixed multifork decision template**. They isolate the repair mechanism but
are not 100 independent decision structures. The older 4--32 robot scale sweep
tiles that motif and is reported only as a controlled load stress test. A
completed `natural_critical_random` suite samples immutable Bernoulli maps and
conditions on a frozen action-conflict, visibility, path-length,
communication-window, and disjointness predicate bundle; its accepted-layout
manifest is frozen before any policy runs. Five complete accepted-layout
manifests are tracked under `paper/manifests/`. See
[evaluation validity](docs/EVALUATION_VALIDITY.md).

At the controlled primary point (5×5 sensing, 30% loss, zero delay), direct
role-aware measurements are:

| Planner | Method | Seeker CSR [95% CI] | Attempted KB |
| --- | --- | ---: | ---: |
| A* | One-shot | 0.3425 [0.3025, 0.3825] | 47.62 |
| A* | CARE | 0.4725 [0.4350, 0.5075] | 53.25 |
| D* Lite | One-shot | 0.3800 [0.3375, 0.4225] | 47.78 |
| D* Lite | CARE | 0.5375 [0.5000, 0.5750] | 53.25 |

Paired CARE-minus-One-shot seeker gains are `+0.1300 [0.1000, 0.1625]`
with A* and `+0.1575 [0.1225, 0.1925]` with D* Lite. CARE is a low-traffic
operating point, not the absolute-success winner: Retry-All reaches
0.5175/0.5725 seeker CSR but costs about 154--155 KB.

The closest-work ladder includes Path-Aware Top-K, Single-Cell Sensitivity and
four **codec-matched inspired adaptations** of OCBC forward simulation,
path-guided compression, rate--distortion allocation and VoI-per-byte routing.
These controls preserve the source idea while using CARE's binary exact-cell
query--patch contract; they are not claimed as exact reproductions of the
original systems. At 5×5, paired intervals detect no reliability difference
between CARE and several of these controls. Its strongest supported distinction
is the explicit bounded joint-scenario certificate, not universal empirical
dominance. See
[closest-work adaptations](docs/CLOSEST_WORK_ADAPTATIONS.md).

The natural-map test is an important negative boundary. CARE-minus-One-shot
seeker CSR is `+0.0050 [-0.0050, 0.0150]` with A* and `-0.0025 [-0.0125,
0.0075]` with D* Lite. Against No Communication it is `+0.0200 [-0.0050,
0.0450]` and `+0.0175 [-0.0075, 0.0450]`; neither interval excludes zero.
Every 4/8/16/32-robot non-tiled CARE-minus-One-shot interval also crosses zero.
Thus the evidence supports the controlled multifork mechanism, not a broad
gain over the conditioned random-map population.

Final CARE contains only the exact deadline-feasible scenario certificate; it
does not append an optimistic/pessimistic route witness. Two earlier auxiliary
route-witness variants remain as ablations: one applies the route-slack hard
gate and one retains the witness without that gate. At delay 2, the hard-gated
variant saves about 6.1 KB but reduces seeker success by `0.0525 [0.0325,
0.0725]` with A* and `0.0575 [0.0375, 0.0800]` with D* Lite relative to the
ungated auxiliary variant. Neither route-witness variant is part of final CARE.
See [commitment-gate ablation](docs/COMMITMENT_GATE_ABLATION.md).

## How one step works

1. Each robot writes its local observation into its own `BeliefMap` and encodes
   newer cells as fixed-width deltas.
2. Deltas traverse a deterministic directed loss/delay channel.
3. Each receiver plans independently on its current replica.
4. CARE enumerates up to 37 sparse scenarios from at most eight path-near cells
   (`q≤2`) and replans them on the shared action graph.
5. An exact hitting set selects the smallest uniform-cost query separating all
   in-scope action-conflicting scenario pairs.
6. The chosen peer returns only newer stamped cells; POGEMA then executes the
   selected actions.

The exact certificate scope, complexity and guarantee boundary are in
[CARE_ALGORITHM.md](docs/CARE_ALGORITHM.md). Wire fields and decoder checks are
in [WIRE_FORMAT.md](docs/WIRE_FORMAT.md).

## Repository layout

```text
cmvr/
  mapping/          Versioned occupancy replicas and sparse updates
  communication/    Lossy transport, codecs, repair and baseline policies
  planning/         Deterministic A* and incremental D* Lite
  env/              POGEMA instances, natural selector and closed-loop runner
configs/            Frozen experiment configurations
scripts/            Run, audit, analyze and artifact-generation entry points
tests/              Unit and integration tests
docs/               Method, architecture and reproducibility documentation
paper/              Manuscript source plus tracked derived tables/figures
assets/             README media
```

Raw `outputs/` are intentionally gitignored. GitHub tracks the code, frozen
configs, analysis scripts, five complete accepted-layout manifests, analysis
manifests, and submission-facing derived tables/figures. The natural audit
rehashes every serialized NPZ, reproduces each raw-seed bitmap bit-exactly and
cross-checks instances, result rows and accepted manifests. Regenerating raw
episode files is documented in
[REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

All 69,800 registered protocol executions are complete. This inventory includes
anchor policies repeated across matrices and is not an independent-sample
count.

## Install and test

Use Python 3.10 for the frozen POGEMA 1.1.1 environment. Its transitive
dependency stack does not install cleanly under Python 3.12.

```bash
python3.10 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

## Run the controlled primary matrix

Every runner refuses a non-empty output directory so separate experiments
cannot be mixed silently.

```bash
python scripts/run_psr_suite.py \
  --config configs/care_main_loss_100map.yaml \
  --output-directory /tmp/care-main \
  --workers 32

python scripts/analyze_care_loss_baselines.py \
  --input-directory /tmp/care-main \
  --output-directory /tmp/care-main-analysis

python scripts/make_care_loss_baseline_artifacts.py \
  --analysis-directory /tmp/care-main-analysis \
  --table-directory paper/tables \
  --figure-directory paper/figures
```

The runner emits serialized instances, one episode row per method, step traces,
an accepted-layout manifest for natural suites, and run metadata. Commands for
the closest-work, gate, natural-validity, scale, delay, FOV and extension
matrices are collected in [REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Generate the POGEMA demo

```bash
python scripts/make_pogema_demo.py --output assets/pogema_demo.gif
```

The map, protocol, loss trace and recorded actions are deterministic.
