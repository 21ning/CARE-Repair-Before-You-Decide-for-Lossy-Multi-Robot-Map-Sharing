# Reproducibility

## Environment and statistical contract

Use Python 3.10 for the frozen POGEMA 1.1.1 environment. Its transitive
dependency stack does not install cleanly under Python 3.12.

```bash
python3.10 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

Every runner refuses a non-empty output directory. Controlled methods share a
serialized layout and deterministic link trace; natural instances are generated
and saved before policy execution. Analyzers require all 100 map keys, reject
duplicates, and use 20,000 deterministic map-cluster bootstrap draws. Paired
intervals preserve map/loss-trace matching.
All analyzers use public seed `20260814` and canonical exchangeable-map
ordering to construct one 20,000-draw resampling-index matrix per map count.
Identical map-level vectors therefore produce byte-identical CIs across
studies.

The primary endpoint is `seeker_success_rate`. `completion_success_rate` is an
all-robot diagnostic. New raw rows also contain role IDs, completion masks,
pair success, all-seeker success and censored seeker completion time.
Specifically, `observer_ids`, `seeker_ids`, `critical_pairs` and
`completion_steps` are serialized directly rather than reconstructed by the
analyzer.

Final `certificate_repair` contains only the exact certificate over
deadline-feasible action-conflicting scenario pairs. The two policies in the
route-slack experiment both add an auxiliary route witness and are retained
only as ablations.

## Controlled core matrices

```bash
python scripts/run_psr_suite.py \
  --config configs/care_main_loss_100map.yaml \
  --output-directory /tmp/care-main --workers 32

python scripts/run_psr_suite.py \
  --config configs/care_observation_radius_100map.yaml \
  --output-directory /tmp/care-fov --workers 32

python scripts/run_psr_suite.py \
  --config configs/care_delay_extension_100map.yaml \
  --output-directory /tmp/care-delay --workers 32

python scripts/run_care_extension_matrix.py \
  --output-directory /tmp/care-extensions --workers 32
```

Expected counts are 9,600, 6,000, 3,200 and 12,000. These 100-map suites use
unique background clutter under controlled decision templates. The scale part
of `care-extensions` tiles the fork motif and is a load stress test, not a
non-tiled generalization result.

## Generic and task-aware controls

```bash
python scripts/run_psr_suite.py \
  --config configs/care_external_baselines_fov_100map.yaml \
  --output-directory /tmp/care-external --workers 32

python scripts/run_psr_suite.py \
  --config configs/care_task_aware_baselines_fov_100map.yaml \
  --output-directory /tmp/care-task-aware --workers 32

python scripts/run_psr_suite.py \
  --config configs/care_information_spectrum_fov_100map.yaml \
  --output-directory /tmp/care-spectrum --workers 32

python scripts/run_psr_suite.py \
  --config configs/care_closest_work_baselines_fov_100map.yaml \
  --output-directory /tmp/care-closest --workers 32
```

Expected counts are 21,600, 4,800, 1,800 and 6,000. Scuttlebutt/Merkle/IBLT
and OCBC/PGSC/R-D/VoI methods are codec-matched inspired adaptations under the
binary occupancy-cell contract; commands do not reproduce the source systems'
native state representations.

## Strict route-slack gate ablation

```bash
python scripts/run_psr_suite.py \
  --config configs/care_commitment_gate_ablation_100map.yaml \
  --output-directory /tmp/care-gate --workers 32

python scripts/analyze_care_commitment_gate.py \
  --input-directory /tmp/care-gate \
  --output-directory /tmp/care-gate-analysis

python scripts/make_care_commitment_gate_artifacts.py \
  --analysis-directory /tmp/care-gate-analysis \
  --table-directory paper/tables \
  --figure-directory paper/figures
```

Expected count is 1,600. Delay zero must match on every non-CPU field. The
frozen result fails the preregistered seeker non-inferiority condition at delay
2, so this run is a retained negative result, not evidence for the hard gate.

## Natural external-validity and non-tiled scale matrices

```bash
python scripts/run_psr_suite.py \
  --config configs/care_natural_external_validity_100map.yaml \
  --output-directory /tmp/care-natural-primary --workers 32

python scripts/run_care_natural_scale.py \
  --config configs/care_natural_scale_100map.yaml \
  --output-directory /tmp/care-natural-scale --workers 32

python scripts/analyze_care_natural_validity.py \
  --primary-directory /tmp/care-natural-primary \
  --scale-directory /tmp/care-natural-scale \
  --output-directory /tmp/care-natural-analysis

python scripts/make_care_natural_validity_artifacts.py \
  --analysis-directory /tmp/care-natural-analysis \
  --table-directory paper/tables \
  --figure-directory paper/figures
```

Both matrices are complete, with 1,600 executions each. Each run writes an
`accepted_layout_manifest.json` before worker execution. Analysis verifies 100
unique raw bitmap hashes, layout fingerprints, start/goal signatures and
critical-pair signatures, plus equality of pre/post-selection bitmap SHA-256.
It additionally rehashes every serialized NPZ, regenerates each bitmap
bit-exactly from its raw seed, and cross-checks every result row against the
serialized instance and accepted manifest.

The completed natural result does not detect broad gain: CARE-minus-One-shot
seeker CSR is `+0.0050 [-0.0050, 0.0150]` A* and `-0.0025 [-0.0125,
0.0075]` D* Lite. CARE-minus-No-Communication is `+0.0200 [-0.0050,
0.0450]` and `+0.0175 [-0.0075, 0.0450]`. All eight non-tiled scale intervals
cross zero. These are results for the stated conditioned population, not
unconditioned random MAPF.

## Analysis and artifact commands

```bash
python scripts/analyze_care_loss_baselines.py \
  --input-directory /tmp/care-main --output-directory /tmp/care-main-analysis
python scripts/make_care_loss_baseline_artifacts.py \
  --analysis-directory /tmp/care-main-analysis \
  --table-directory paper/tables --figure-directory paper/figures

python scripts/analyze_care_observation_radius.py \
  --input-directory /tmp/care-fov --output-directory /tmp/care-fov-analysis
python scripts/make_care_observation_radius_artifacts.py \
  --analysis-directory /tmp/care-fov-analysis \
  --table-directory paper/tables --figure-directory paper/figures

python scripts/analyze_care_certificate.py \
  --input-directory /tmp/care-delay --output-directory /tmp/care-delay-analysis
python scripts/make_care_deadline_artifacts.py \
  --analysis-directory /tmp/care-delay-analysis \
  --table-directory paper/tables --figure-directory paper/figures

python scripts/analyze_care_extension_matrix.py \
  --input-directory /tmp/care-extensions \
  --primary-directory /tmp/care-fov \
  --output-directory /tmp/care-extension-analysis
python scripts/make_care_extension_artifacts.py \
  --analysis-directory /tmp/care-extension-analysis \
  --table-directory paper/tables --figure-directory paper/figures

python scripts/analyze_external_reconciliation.py \
  --input-directory /tmp/care-external \
  --output-directory /tmp/care-external-analysis
python scripts/make_external_reconciliation_artifacts.py \
  --analysis-directory /tmp/care-external-analysis \
  --table-directory paper/tables

python scripts/analyze_task_aware_baselines.py \
  --input-directory /tmp/care-task-aware \
  --output-directory /tmp/care-task-aware-analysis
python scripts/make_task_aware_baseline_artifacts.py \
  --analysis-directory /tmp/care-task-aware-analysis \
  --table-directory paper/tables

python scripts/analyze_information_spectrum.py \
  --input-directory /tmp/care-spectrum \
  --output-directory /tmp/care-spectrum-analysis
python scripts/make_information_spectrum_artifacts.py \
  --analysis-directory /tmp/care-spectrum-analysis \
  --table-directory paper/tables

python scripts/analyze_care_closest_work.py \
  --input-directory /tmp/care-closest \
  --output-directory /tmp/care-closest-analysis
python scripts/make_care_closest_work_artifacts.py \
  --analysis-directory /tmp/care-closest-analysis \
  --table-directory paper/tables --figure-directory paper/figures
```

## Cross-study audit

```bash
python scripts/audit_care_cross_study_reproducibility.py \
  --main /tmp/care-main --observation /tmp/care-fov \
  --delay /tmp/care-delay --extensions /tmp/care-extensions \
  --output /tmp/care-cross-study-audit.json
```

## What GitHub contains

Raw episode CSVs, per-step traces and serialized maps live under gitignored
`outputs/`; they are deterministic build products and are not committed.
The repository tracks frozen configs, source/tests, analysis and artifact
generators, all five full accepted-layout manifests under `paper/manifests/`,
audit manifests, and derived tables/figures. All 69,800 protocol executions are
complete. The count includes repeated anchors and is not 69,800 independent
observations.
