# Reproducibility

Install the compact environment and run the deterministic test suite:

```bash
pip install -r requirements.txt -r requirements-dev.txt
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q
```

Each policy-condition uses 100 independent maps. Policies share the same map
and deterministic loss trace within each map. All confidence intervals are
deterministic 20,000-draw bootstraps over maps; standard deviations use all
100 trial-level observations. Runners reject nonempty output directories.

## Formal matrix and scale extension

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_100map_matrix.py \
  --workers 32 --output-directory /tmp/psr-ut-formal
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_100map_matrix.py \
  --input-directory /tmp/psr-ut-formal --output-directory /tmp/psr-ut-formal-analysis

PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_scale_100map.py \
  --workers 32 --output-directory /tmp/psr-ut-scale
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_100map_matrix.py \
  --input-directory /tmp/psr-ut-scale --output-directory /tmp/psr-ut-scale-analysis
```

## Paired ablations and topology extensions

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_suite.py \
  --config configs/psr_action_triggered_100map.yaml \
  --output-directory /tmp/psr-ut-action --workers 32
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_action_triggered_baseline.py \
  --input-directory /tmp/psr-ut-action --output-directory /tmp/psr-ut-action-analysis

PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_suite.py \
  --config configs/psr_topology_t_junction_100map.yaml \
  --output-directory /tmp/psr-ut-t-junction --workers 32
PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_suite.py \
  --config configs/psr_topology_asymmetric_fork_100map.yaml \
  --output-directory /tmp/psr-ut-asymmetric --workers 32
PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_suite.py \
  --config configs/psr_topology_narrow_bypass_100map.yaml \
  --output-directory /tmp/psr-ut-bypass --workers 32
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_topology_variants.py \
  --t-junction /tmp/psr-ut-t-junction --asymmetric-fork /tmp/psr-ut-asymmetric \
  --narrow-bypass /tmp/psr-ut-bypass --output-directory /tmp/psr-ut-topologies
```

Run the full-method ablation analysis against explicit rerun roots:

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_full_method_ablations.py \
  --formal-directory /tmp/psr-ut-formal --action-directory /tmp/psr-ut-action \
  --output-directory /tmp/psr-ut-ablations
```

Generate paper assets from the new formal summary using
`scripts/make_psr_ut_paper_artifacts.py`.

## Periodic Full Anti-Entropy baseline

This supplementary primary control uses K=4. It transmits ordinary deltas on
non-sync steps and a fair, budget-bounded full-replica chunk on each sync step;
there is no path, mismatch, or decision-sensitive trigger.

```bash
PYTHONDONTWRITEBYTECODE=1 python scripts/run_psr_suite.py \
  --config configs/psr_periodic_full_primary_100map.yaml \
  --output-directory /tmp/psr-ut-periodic-full --workers 32
PYTHONDONTWRITEBYTECODE=1 python scripts/analyze_psr_external_baselines.py \
  --input-directory /tmp/psr-ut-formal/loss_sweep \
  --input-directory /tmp/psr-ut-periodic-full \
  --output-directory /tmp/psr-ut-primary-baseline-analysis
PYTHONDONTWRITEBYTECODE=1 python scripts/make_psr_ut_paper_artifacts.py \
  --formal-summary /tmp/psr-ut-formal-analysis/summary_mean_std_ci.csv \
  --periodic-summary /tmp/psr-ut-primary-baseline-analysis/summary.csv \
  --table-directory /tmp/psr-ut-tables --figure-directory /tmp/psr-ut-figures
```

The raw outputs used for the submitted results were cleared during final
repository curation; they are intentionally not a hidden input to the code.
