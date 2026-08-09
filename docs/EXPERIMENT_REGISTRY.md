# CARE Experiment Registry

All completed studies use frozen, versioned implementations, 100 fully
independent maps per policy-condition, one matched loss trace per map, and 32
workers. The raw episode outputs are intentionally excluded from this compact
submission repository; the final derived tables and figures are retained in
`paper/`.

| ID | Design | Policies | Status | Evidence retained in repository |
| --- | --- | --- | --- | --- |
| PSR-UT-formal-001 | 13 studies: loss, density, delay, cadence, scope, timing, and controls | One-shot, Retry-All, Path-Weighted ARQ, Mismatch Full Repair, PSR-UT; matched ablations | complete, 8,600 episodes | `paper/tables/psr_ut_primary_comparison.*`, `paper/figures/psr_ut_*` |
| PSR-UT-periodic-001 | Primary decision geometry; K=4 periodic full anti-entropy | Periodic Full Sync | complete, 100 episodes | `paper/tables/psr_ut_primary_comparison.*` |
| PSR-UT-action-001 | Utility trigger versus action-triggered repair | Action-triggered repair, PSR-UT | complete, 200 episodes | `paper/tables/psr_ut_ablation_extension_summary.md` |
| PSR-UT-scale-001 | 4/8/16/32-agent tiled scale extension | four matched policies | complete, 1,600 episodes | `paper/tables/psr_ut_ablation_extension_summary.md` |
| PSR-UT-topology-001 | T-junction, asymmetric-fork, narrow-bypass decision geometries | five primary policies | complete, 1,500 episodes | `paper/tables/psr_ut_ablation_extension_summary.md` |
| PSR-UT-codec-audit-001 | Binary codec integration rerun on the paired action-trigger condition | Action-triggered repair, PSR-UT | complete, 200 episodes | `docs/WIRE_CODEC_AUDIT.md` |
| CARE-deadline-planner-001 | 4 delays $\times$ 2 planners on the primary decision geometry | One-shot, Action-triggered, PSR-UT, CARE | complete, 3,200 episodes | `docs/CARE_GATE_RESULT.md`, `paper/tables/care_cross_planner_primary.*`, `paper/figures/care_cross_planner_delay.png` |
| CARE-certificate-gate-001 | Exact scenario certificate and positive-delay dual-certificate promotion gate | One-shot, PSR-UT, CARE-Lite, CARE | complete, 3,200 episodes | `docs/CARE_ALGORITHM.md`, `docs/CARE_FINAL_RESULTS.md` |
| CARE-loss-baselines-001 | 6 loss rates $\times$ 8 policies $\times$ A*/D* Lite | One-shot, Retry-All, Path-Weighted, Periodic Full, Mismatch Full, PSR-UT, CARE-Lite, CARE | complete, 9,600 episodes / 100 unique fingerprints | `paper/tables/care_loss_baselines_manifest.json`, `care_loss_baselines_primary.*`, `care_loss_baselines_paired.*`, `paper/figures/care_loss_baseline_sweep.*` |

The obsolete Conditional-CMVR/Oracle direction, preliminary PSR variants,
EPOM training artifacts, and their results are not part of this submission.
