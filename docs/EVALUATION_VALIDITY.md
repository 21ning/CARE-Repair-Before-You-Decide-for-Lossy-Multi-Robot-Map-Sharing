# Evaluation validity and endpoint contract

This repository separates three claims that were easy to conflate in early
experiments: physical-map diversity, decision-structure diversity, and
decision-critical robot success.

## Primary endpoints

Every serialized result now directly retains `observer_ids`, `seeker_ids`,
`critical_pairs`, `completion_steps`, the agent completion mask, and reports:

- `observer_success_rate`: completion among annotated remote observers;
- `seeker_success_rate`: completion among annotated decision-critical seekers;
- `critical_pair_success_rate`: fraction of observer--seeker pairs in which
  both robots finish;
- `all_seekers_success`: map-level all-seeker completion;
- `completion_success_rate`: completion across all robots, retained as a
  diagnostic for backward compatibility;
- `mean_seeker_completion_step_censored`: mean seeker arrival time with
  non-completion censored at the episode horizon.

The hand-controlled `multifork_cluttered` suite has four one-step observers and
four seekers. All audited observers complete, so its old overall CSR obeys
`overall CSR = (1 + seeker CSR)/2` and has a structural 0.5 floor. The paper's
primary endpoint is therefore seeker CSR, with pair success as a co-reported
role-aware endpoint. Old overall CSR is never relabeled as seeker CSR.

All uncertainty intervals use 20,000 map-cluster bootstrap draws with one fixed
public resampling index after canonical exchangeable-map ordering. A paired
comparison first subtracts policies on the same layout and deterministic link
trace and then resamples whole maps; individual robots or pairs are not treated
as independent observations.

## Two map populations

The controlled fork family keeps the causal obstacle, route and commitment
geometry fixed while changing background clutter. It isolates mechanism but
does not establish broad structural generality. Its older 4--32-agent scale
study tiles the same fork motif and is now labelled a controlled stress test.

The independent `natural_critical_random` family instead:

1. samples a complete i.i.d. Bernoulli occupancy bitmap;
2. never modifies that bitmap;
3. deterministically searches only for naturally present blocked-cell action
   conflicts satisfying a frozen geometry predicate;
4. assigns non-trivial observer goals (truth distance 8--16) and seeker goals
   (truth distance 12--40);
5. freezes an accepted-layout manifest before any communication policy runs.

Selection may inspect the map geometry and counterfactual A* paths, but cannot
inspect a policy, packet-loss trace or episode outcome. Metadata records the raw
seed, pre/post bitmap SHA-256, attempt count, rejection counts, starts/goals,
critical pairs, path lengths and commitment windows. The target population is
therefore stated precisely: random Bernoulli maps conditioned on the frozen
action-conflict, visibility, path-length, communication-window, and
disjointness predicate bundle. It is not an unconditioned random-MAPF
claim.

## Completed natural-map audit and result

All 3,200 natural executions are complete: 1,600 primary episodes and 1,600
non-tiled scale episodes. The repository tracks five full manifests:

- `paper/manifests/natural_primary_accepted_layouts.json`;
- `paper/manifests/natural_scale_4_accepted_layouts.json`;
- `paper/manifests/natural_scale_8_accepted_layouts.json`;
- `paper/manifests/natural_scale_16_accepted_layouts.json`;
- `paper/manifests/natural_scale_32_accepted_layouts.json`.

For every 100-map population, the analyzer verifies unique layout, raw-bitmap,
start/goal and critical-pair signatures. It rehashes every serialized NPZ,
regenerates the Bernoulli bitmap bit-exactly from the recorded raw seed, checks
pre/post-selection immutability, and cross-checks result rows, instances and
the accepted manifest. In total it cross-checks 1,600 primary rows and 400 rows
at each of four scales.

The result is a negative external-validity boundary. CARE-minus-One-shot seeker
CSR is `+0.0050 [-0.0050, 0.0150]` with A* and `-0.0025 [-0.0125, 0.0075]`
with D* Lite. CARE-minus-No-Communication is `+0.0200 [-0.0050, 0.0450]`
and `+0.0175 [-0.0075, 0.0450]`. All eight 4/8/16/32-robot non-tiled
CARE-minus-One-shot intervals cross zero. Under D* Lite, CARE is below Periodic
Full by `-0.0125 [-0.0275, -0.0025]` seeker CSR while using about 361 KB less.

| Robots | A* CARE − One-shot [95% CI] | D* Lite CARE − One-shot [95% CI] |
| ---: | ---: | ---: |
| 4 | +0.0000 [-0.0350, +0.0400] | +0.0050 [-0.0300, +0.0450] |
| 8 | -0.0050 [-0.0225, +0.0100] | -0.0025 [-0.0250, +0.0175] |
| 16 | -0.0050 [-0.0150, +0.0037] | -0.0050 [-0.0175, +0.0063] |
| 32 | -0.0019 [-0.0106, +0.0069] | +0.0019 [-0.0081, +0.0119] |

Consequently the natural suite does not support a broad/general CARE gain. The
positive claim remains about the controlled multifork mechanism, and the
natural finding applies only to the declared conditioned Bernoulli population.

## Reproduce

```bash
python scripts/run_psr_suite.py \
  --config configs/care_natural_external_validity_100map.yaml \
  --workers 32

python scripts/run_care_natural_scale.py \
  --config configs/care_natural_scale_100map.yaml \
  --workers 32

python scripts/analyze_care_natural_validity.py \
  --primary-directory outputs/care_natural_external_validity_100map \
  --scale-directory outputs/care_natural_scale_100map \
  --output-directory /tmp/care-natural-analysis
```
