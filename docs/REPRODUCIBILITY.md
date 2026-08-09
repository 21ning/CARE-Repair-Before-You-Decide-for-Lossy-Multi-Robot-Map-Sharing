# Reproducibility

Install Python 3.10 dependencies and run the deterministic test suite:

```bash
pip install -r requirements.txt -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

Every runner refuses a non-empty output directory. Every analyzer requires all
100 `(layout_seed, network_seed)` keys per condition and rejects duplicate
physical `layout_fingerprint` values. CIs use 20,000 deterministic map-cluster
bootstrap draws; paired intervals preserve map and loss-trace matching.

## Run all frozen experiments

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

python scripts/run_psr_suite.py \
  --config configs/care_external_baselines_fov_100map.yaml \
  --output-directory /tmp/care-external --workers 32
```

Expected episode counts are respectively 9,600, 6,000, 3,200, 12,000 and
21,600.

## Analyze and generate paper assets

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
  --input-directory /tmp/care-extensions --primary-directory /tmp/care-fov \
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
```

Audit overlapping independent reruns:

```bash
python scripts/audit_care_cross_study_reproducibility.py \
  --main /tmp/care-main --observation /tmp/care-fov \
  --delay /tmp/care-delay --extensions /tmp/care-extensions \
  --output /tmp/care-cross-study-audit.json
```

The raw CSV and serialized maps are intentionally not committed. They are
regenerated from these frozen configurations; the repository retains derived
tables, figures, manifests and code.
