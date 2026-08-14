# CARE experiment registry

The protocol inventory totals **69,800 episode executions**. This number
includes anchor policies repeated across matrices and is a compute/protocol
count, not the number of independent samples. Every condition uses 100 paired
map-level units and deterministic matched link traces.

Controlled `multifork_cluttered` maps have unique background-clutter bitmaps but
share a protected decision structure. `CARE-scale-legacy` tiles that motif.
Natural matrices instead use immutable Bernoulli maps conditioned on a frozen
action-conflict, visibility, path-length, communication-window, and
disjointness predicate bundle; instance selection completes
and is manifested before any policy runs.

| ID | Design | Executions | Status | Retained evidence |
| --- | --- | ---: | --- | --- |
| CARE-main-5x5 | 6 losses × 8 policies × A*/D* | 9,600 | complete | role-aware `care_loss_baselines_*`, paired loss figure |
| CARE-FOV | 3 FOVs × 10 policies × A*/D* | 6,000 | complete | `care_fov_*`, controlled FOV figure |
| CARE-delay | delays 0/1/2/4 × 4 policies × A*/D* | 3,200 | complete | delay tables/figure |
| CARE-density | 4 controlled densities × 6 policies × A*/D* | 4,800 | complete | `care_extensions.*` |
| CARE-random-negative | 4 generic random densities × 3 policies | 1,200 | complete | negative-control section of `care_extensions.*` |
| CARE-certificate-ablation | cadence and q/cap variants × A*/D* | 800 | complete | full-method paired ablations |
| CARE-topology | 3 protected topology families × 6 policies × A*/D* | 3,600 | complete | controlled topology stress |
| CARE-scale-legacy | 4/8/16/32 robots × 4 policies | 1,600 | complete | **tiled-motif** load stress only |
| CARE-external-reconciliation-FOV | 3 FOVs × 6 losses × 6 methods × A*/D* | 21,600 | complete | codec-matched Scuttlebutt/Merkle/IBLT adaptations |
| CARE-task-aware-ladder-FOV | 3 FOVs × 8 methods × A*/D* | 4,800 | complete | Path-Aware/Single-Cell mechanism ladder |
| CARE-information-spectrum-FOV | 3 endpoints × 3 FOVs × A*/D* | 1,800 | complete | zero-byte/selective/full-sync spectrum |
| CARE-closest-work-FOV | 3 FOVs × 10 methods × A*/D* | 6,000 | complete | OCBC-FS/PGSC/Bernoulli-R-D/VoI adaptations plus anchors |
| CARE-route-slack-gate | 4 delays × 2 auxiliary-witness policies × A*/D* | 1,600 | complete; gate claim rejected | gated vs ungated route-witness ablations; neither is final CARE |
| CARE-natural-primary | 8 methods × A*/D* | 1,600 | complete; broad gain not supported | immutable accepted-layout manifest and direct role-aware outputs |
| CARE-natural-scale | 4 scales × 2 methods × A*/D* | 1,600 | complete; all seeker-effect CIs cross zero | non-tiled natural scale manifests/results |

All 69,800 registered executions are complete. Natural primary CARE-minus-
One-shot seeker effects are `+0.0050 [-0.0050, 0.0150]` A* and `-0.0025
[-0.0125, 0.0075]` D* Lite. Every non-tiled 4/8/16/32 scale interval crosses
zero, so these matrices close an external-validity gap with a negative boundary
rather than extending the controlled positive claim.

The independently launched overlapping controlled anchors agree on non-timing
fields where audited. The new primary rerun writes direct role metrics. Older
controlled matrices may use the audited affine conversion from overall CSR to
seeker CSR, but every such value must be labelled `derived`.

## Repository retention policy

Raw episode directories (`outputs/`), traces and serialized maps are
gitignored because they are large deterministic build products. GitHub retains:

- frozen YAML configs and runner/analyzer source;
- five full accepted-layout manifests in `paper/manifests/` plus analysis
  manifests documenting uniqueness, immutability and population state;
- submission-facing derived CSV/Markdown tables and PDF/PNG figures;
- tests and documentation needed to regenerate raw evidence.

The absence of raw outputs from Git is therefore deliberate and must not be
described as absence of experimental evidence. Reproduction commands are in
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md).
