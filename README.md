# CARE: Repair Before You Decide

CARE is a compact research implementation for reliable occupancy-map sharing
between multiple robots over lossy links. Its main protocol,
**Commitment-Aware Replica rEpair (CARE)**, keeps an explicit versioned map replica at
each robot and minimizes encoded repair traffic subject to a locally derived
route-commitment deadline. The earlier fixed-corridor PSR-UT remains as a
matched ablation.

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

The motivation is simple: a stale map cell is harmful only if it can change a
decision, and a repair is useful only if it arrives before the robot commits.
CARE turns those two observations into an executable communication objective
rather than a fixed retry schedule. The environment and robot motion are provided by
[POGEMA](https://github.com/AIRI-Institute/pogema). All methods use the same
map representation, packet-loss trace, delay model, and byte accounting within
each matched condition. The formal planner-independence check repeats the
matrix with A* and incremental D* Lite. There are no learned policies or model
checkpoints in this repository.

## How it works

At every environment step:

1. each robot converts its local observation into version-stamped sparse map
   updates;
2. updates are sent through a deterministic directed loss/delay channel;
3. each receiver plans on its own local map replica;
4. CARE compares optimistic and pessimistic receiver-local paths to detect a
   decision ambiguity;
5. the first unknown cell on the operational path gives the latest safe repair
   time, which is checked against the query--patch round trip;
6. CARE queries only unknown cells in the one-hop action-graph influence set
   between path divergence and reconvergence;
7. the peer returns only newer stamped cells, after which POGEMA executes the
   selected actions.

With 100 independent maps, 30% loss, and zero delay, CARE reaches 0.9375 CSR
with A* and 0.9400 with D* Lite, versus 0.8400/0.8462 for One-shot. It uses
about 68.6 KB per episode, roughly 7 KB less than fixed-corridor PSR-UT at
statistically equivalent reliability. See
[docs/CARE_GATE_RESULT.md](docs/CARE_GATE_RESULT.md) for the paired confidence
intervals and deadline diagnostics.

The implementation separates mapping, communication, planning, and environment
execution so that the protocol can be inspected or replaced independently.

## Wire format and traffic accounting

The simulated link carries real fixed-width binary payloads. Traffic is the
sum of encoded payload lengths for every attempted transmission, including
packets later lost by the channel.

| Payload | Encoded size |
| --- | ---: |
| Cell Delta | 13 bytes |
| Digest Query | `16 + 6N` bytes for N stamped cells |
| Patch | `4 + 13M` bytes for M returned cells |
| ACK | 8 bytes |
| Replica digest | 16 bytes |

Receivers validate lengths, versions, reserved bits, bounds, and Delta CRCs,
then apply only updates whose version stamp dominates the local copy. Update
IDs are reconstructed and are not transmitted. See
[docs/WIRE_FORMAT.md](docs/WIRE_FORMAT.md) for the bit layout and decoder
contract.

## Repository layout

```text
cmvr/
  mapping/          Versioned occupancy maps and sparse update encoding
  communication/    Lossy transport, byte budgets, digests, and repair policies
  planning/         Deterministic A*, incremental D* Lite, and planner contract
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
       -> PlanningMapAdapter + selected Planner
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
  --config configs/care_deadline_cross_planner_100map.yaml \
  --output-directory /tmp/care-demo \
  --workers 32
```

The runner writes:

```text
/tmp/care-demo/
  instances/        Serialized maps and episode metadata
  results.csv       One row per policy episode
  traces.csv        Per-step replica and repair measurements
  summary.json      Configuration and run metadata
```

To analyze the CARE cross-planner matrix:

```bash
python scripts/analyze_care_deadline_cross_planner.py \
  --input-directory /tmp/care-demo \
  --output-directory /tmp/care-analysis
```

Additional commands for topology, scale, delay, and ablation configurations
are documented in [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Generate the POGEMA demo

The README animation runs one deterministic deadline-aware CARE episode and replays its
recorded actions in POGEMA using the visualization semantics described above.

```bash
python scripts/make_pogema_demo.py --output assets/pogema_demo.gif
```

The generator is deterministic: the map, link trace, protocol, and action
sequence are fixed by the seeds in the script.
