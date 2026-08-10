# CARE experiment registry

All frozen studies use 100 physically distinct layouts per condition, matched
loss traces, the binary codec and 32 workers. Raw episode files are excluded
from the compact submission repository; audited tables, figures, configs and
regeneration code are retained.

| ID | Design | Episodes | Status | Retained evidence |
| --- | --- | ---: | --- | --- |
| CARE-main-5x5 | 6 losses × 8 policies × A*/D* | 9,600 | complete | `care_loss_baselines_*`, loss figure |
| CARE-FOV | 3×3/5×5/7×7 × 10 policies × A*/D* | 6,000 | complete | `care_fov_*`, FOV figure |
| CARE-delay | delays 0/1/2/4 × 4 policies × A*/D* | 3,200 | complete | cross-planner table and delay figure |
| CARE-density | 4 structured densities × 6 policies × A*/D* | 4,800 | complete | `care_extensions.*` |
| CARE-random-negative | 4 random densities × 3 policies | 1,200 | complete | `care_extensions.*` |
| CARE-certificate-ablation | cadence plus q/cap variants × A*/D* | 800 | complete | `care_full_method_ablations.*` |
| CARE-topology | 3 topologies × 6 policies × A*/D* | 3,600 | complete | `care_extensions.*` |
| CARE-scale | 4/8/16/32 agents × 4 policies | 1,600 | complete | `care_extensions.*` |
| CARE-external-reconciliation-FOV | 3 FOVs × 6 losses × 3 published methods + 3 anchors × A*/D* | 21,600 | complete | `care_external_baselines_*`, protocol diagnostics |
| CARE-task-aware-ladder-FOV | 3 FOVs × 8 ladder methods × A*/D* | 4,800 | complete | `care_task_aware_*`, paired and mechanism diagnostics |

The overlapping primary conditions were launched independently in four studies.
`care_cross_study_reproducibility.json` verifies 1,600 FOV, 800 delay and
1,200 density rows against the main run with zero non-timing differences.
