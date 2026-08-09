# PSR-UT: Decision-Critical Replica Repair for Lossy Multi-Robot Map Sharing

Anonymous ICASSP submission code for **Path-Scoped Utility-Triggered Replica
Repair (PSR-UT)**. The project studies a narrow systems question: when a robot
misses a remote map update, should it repair every replica mismatch, or only
the mismatches that can change an imminent route decision?

The repository is deliberately a compact, reproducible paper artifact. It
contains the final explicit-state implementation, frozen 100-map experiment
configurations, analyses, tests, anonymous paper source, and final paper
figures/tables. It does not contain learned policies, model weights, generated
maps, raw episodes, or superseded CMVR/Oracle/EPOM code.

## Motivation

One-shot map sharing fails when a packet containing a blocked route cell is
lost shortly before a receiver reaches a fork. Conventional anti-entropy can
repair the mismatch, but spending full-replica traffic on every mismatch is
often unnecessary. A missing update matters only when it is both:

1. **spatially relevant**: it lies near the receiver's imminent planned path;
2. **decision-critical**: uncertainty about it changes the receiver's next
   fixed-A* action.

PSR-UT makes precisely this bounded claim. It is neither a universal
communication policy nor a replacement for reliable ARQ.

## Method

Each robot holds an independent, versioned explicit occupancy-map replica.
All policies use the same map representation, fixed A*, directed lossy link,
loss trace, delay, and per-sender byte cap.

1. Robots observe locally and emit version-stamped sparse cell deltas.
2. The receiver computes an optimistic A* path and a pessimistic A* path that
   treats unknown cells as blocked.
3. PSR-UT repairs only if the next actions from these paths differ.
4. The receiver sends a digest for a dilated imminent-path corridor to a peer.
5. The peer returns only cells whose stamps dominate the receiver's copy;
   patches, digests, ACKs, and deltas all consume the same lossy transport
   budget.

This produces a two-gate protocol: **where** a repair may matter (the path
corridor) and **when** it is worth sending (next-action disagreement).

### Matched policies

| Strategy | When it repairs | Repair scope |
| --- | --- | --- |
| One-shot delta | Never | None |
| Retry-All / Path-Weighted ARQ | Retransmission scheduling | Missing deltas |
| Periodic Full Anti-Entropy (K=4) | Every four steps | Fairly rotated full-replica chunks |
| Mismatch Full Repair | Replica-digest mismatch | Full replica chunks |
| PSR-UT | Local optimistic/pessimistic actions differ | Imminent path corridor |

Periodic Full is the conventional anti-entropy baseline: non-sync steps send
ordinary deltas; sync steps replace them with a budget-bounded full-replica
chunk. It has no decision, path, or mismatch trigger.

## Submitted evidence

Every reported condition uses 100 independent maps. Within each map, policies
are exactly matched on layout, starts/goals, and deterministic loss trace. We
report trial-level mean and sample SD; confidence intervals are deterministic
20,000-draw map-level bootstraps.

Primary condition: eight agents, decision-critical fork geometry, 30% packet
loss, zero delivery delay.

| Method | Completion success rate | Attempted traffic / episode |
| --- | ---: | ---: |
| One-shot | 0.8400 | 65.4 KB |
| PSR-UT | 0.9325 | 75.8 KB |
| Periodic Full (K=4) | 0.9575 | 285.8 KB |
| Retry-All ARQ | 0.9762 | 263.9 KB |
| Path-Weighted ARQ | 0.9775 | 263.9 KB |
| Mismatch Full Repair | 0.9150 | 578.9 KB |

PSR-UT improves on One-shot by **+0.0925 CSR** (paired 95% CI
[+0.0750, +0.1100]) for 10.4 KB additional traffic. Periodic Full is more
reliable in this primary condition, but PSR-UT sends 210.0 KB fewer bytes per
episode (paired 95% CI [−213.2, −206.9] KB). Thus PSR-UT is a lower-traffic
reliability operating point, not the highest-reliability endpoint.

The method's boundary is explicit: its benefit diminishes when a repair cannot
arrive before the decision deadline (two or more delivery steps), and is small
on the tiled random-scale extension. It remains materially positive on three
independent decision-critical topologies. See
[docs/PSR_UT_EVIDENCE.md](docs/PSR_UT_EVIDENCE.md) for all retained claims.

## Repository layout

```text
cmvr/       Protocol, map replicas, lossy transport, fixed A*, and POGEMA runner
configs/    Frozen 100-independent-map study configurations
scripts/    Runners, paired analyses, and paper-asset generation
tests/      Deterministic unit and integration tests
docs/       Evidence, reproducibility, and architecture documentation
paper/      Anonymous ICASSP LaTeX source plus final tables and figures
```

For component ownership and the end-to-end execution/data flow, read
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Installation and validation

Python 3.10 is recommended.

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

## Run the code

Runners always require an explicit configuration and reject nonempty output
directories; this prevents accidentally mixing evidence from separate runs.
Use `/tmp` (or another empty directory) for regenerated raw output.

### Reproduce the formal matrix

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_100map_matrix.py \
  --workers 32 --output-directory /tmp/psr-ut-formal
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_100map_matrix.py \
  --input-directory /tmp/psr-ut-formal \
  --output-directory /tmp/psr-ut-formal-analysis
```

### Reproduce the Periodic Full baseline and primary comparison

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_suite.py \
  --config configs/psr_periodic_full_primary_100map.yaml \
  --output-directory /tmp/psr-ut-periodic-full --workers 32
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_external_baselines.py \
  --input-directory /tmp/psr-ut-formal/loss_sweep \
  --input-directory /tmp/psr-ut-periodic-full \
  --output-directory /tmp/psr-ut-primary-analysis
```

### Regenerate paper assets

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/make_psr_ut_paper_artifacts.py \
  --formal-summary /tmp/psr-ut-formal-analysis/summary_mean_std_ci.csv \
  --periodic-summary /tmp/psr-ut-primary-analysis/summary.csv \
  --table-directory /tmp/psr-ut-tables --figure-directory /tmp/psr-ut-figures
```

`run_psr_suite.py` can also run any frozen YAML in `configs/`; it writes
`instances/`, `results.csv`, `traces.csv`, and `summary.json`. The analysis
scripts reject incomplete 100-map matrices or broken map/loss-trace pairing.

See [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) for action-trigger,
scale, topology, and full-method ablation commands. The anonymous paper source
is [paper/psr_icassp_draft.tex](paper/psr_icassp_draft.tex).
