# CARE: Repair Before You Decide

CARE is a compact research implementation for reliable occupancy-map sharing
between multiple robots over lossy links. Its main protocol, **Path-Scoped
Utility-Triggered repair (PSR-UT)**, keeps an explicit versioned map replica at
each robot and repairs missing cells only when they can affect an imminent
planning decision.

![CARE running in POGEMA](assets/pogema_demo.gif)

The animation shows **Robot 1's evolving local map replica**, not the complete
ground-truth map. It starts fully unknown and is updated by local sensing and
lossy messages received from peers.

| Visual element | Meaning |
| --- | --- |
| Gray cell | Unknown to Robot 1 |
| White cell | Observed locally by Robot 1 |
| Blue cell | Map information received from another robot |
| Dark cell | Known obstacle |
| Colored circle / square | Current robot position / assigned goal |

Robot positions and goals are drawn as a global motion overlay so the paths
remain easy to follow; they are not part of Robot 1's occupancy-map knowledge.
The episode uses eight agents, 30% packet loss, and start-to-goal distances of
14--48 cells, so no robot begins at or immediately beside its goal.

The environment and robot motion are provided by
[POGEMA](https://github.com/AIRI-Institute/pogema). All methods use the same
fixed A* planner, map representation, packet-loss trace, delay model, and byte
accounting. There are no learned policies or model checkpoints in this
repository.

## How it works

At every environment step:

1. each robot converts its local observation into version-stamped sparse map
   updates;
2. updates are sent through a deterministic directed loss/delay channel;
3. each receiver plans on its own local map replica;
4. PSR-UT compares the receiver's optimistic and pessimistic next actions;
5. if those actions disagree, the receiver queries a short corridor around its
   imminent route and receives only newer cells from a peer;
6. POGEMA executes the selected actions and the process repeats.

The implementation separates mapping, communication, planning, and environment
execution so that the protocol can be inspected or replaced independently.

## Repository layout

```text
cmvr/
  mapping/          Versioned occupancy maps and sparse update encoding
  communication/    Lossy transport, byte budgets, digests, and repair policies
  planning/         Deterministic A* and belief-map adapters
  env/              POGEMA instances and the closed-loop protocol runner
configs/            Reproducible experiment configurations
scripts/            Experiment, analysis, and visualization entry points
tests/              Unit and integration tests
docs/               Architecture and reproducibility notes
paper/              Manuscript source and generated paper assets
assets/             README media
```

The main execution path is:

```text
EpisodeInstance
    -> PSRClosedLoopRunner
       -> BeliefMap + DeltaEncoder
       -> UnreliableNetwork + ReplicaPolicy
       -> PlanningMapAdapter + AStarPlanner
    -> PSRResult
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the responsibility and
data flow of every component.

## Installation

Python 3.10 is recommended.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Validate the installation:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

## Run an experiment

Run any YAML configuration with `run_psr_suite.py`. The output directory must
be empty so results from separate runs cannot be mixed accidentally.

```bash
python scripts/run_psr_suite.py \
  --config configs/psr_periodic_full_primary_100map.yaml \
  --output-directory /tmp/care-demo \
  --workers 8
```

The runner writes:

```text
/tmp/care-demo/
  instances/        Serialized maps and episode metadata
  results.csv       One row per policy episode
  traces.csv        Per-step replica and repair measurements
  summary.json      Configuration and run metadata
```

To run and analyze the complete configured matrix:

```bash
python scripts/run_psr_100map_matrix.py \
  --workers 32 --output-directory /tmp/care-formal
python scripts/analyze_psr_100map_matrix.py \
  --input-directory /tmp/care-formal \
  --output-directory /tmp/care-analysis
```

Additional commands for topology, scale, delay, and ablation configurations
are documented in [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Generate the POGEMA demo

The README animation runs one deterministic PSR-UT episode and replays its
recorded actions in POGEMA using the visualization semantics described above.

```bash
python scripts/make_pogema_demo.py --output assets/pogema_demo.gif
```

The generator is deterministic: the map, link trace, protocol, and action
sequence are fixed by the seeds in the script.
