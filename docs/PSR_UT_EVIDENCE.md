# PSR-UT final evidence

Every formal condition uses 100 completely independent map instances. Each map
has one deterministic independent loss trace, and all policies are matched by
map fingerprint and trace. We report trial-level mean and sample standard
deviation; 95% CIs use a deterministic 20,000-draw bootstrap over maps. All
runs used 32 worker processes.

## Primary comparison

The eight-agent decision-critical fork task at 30% loss and zero delay is the
primary condition. PSR-UT is a reliability--traffic operating point, not a
claim of universal superiority to unconstrained ARQ.

| Method | CSR mean ± SD | 95% CI | Attempted bytes mean ± SD |
| --- | ---: | ---: | ---: |
| One-shot | 0.8400 ± 0.0928 | [0.8200, 0.8600] | 65,352 ± 1,213 |
| PSR-UT | 0.9325 ± 0.0850 | [0.9163, 0.9475] | 75,774 ± 1,358 |
| Retry-All ARQ | 0.9762 ± 0.0527 | [0.9650, 0.9862] | 263,898 ± 4,228 |
| Path-Weighted ARQ | 0.9775 ± 0.0528 | [0.9663, 0.9875] | 263,920 ± 4,174 |
| Periodic Full Anti-Entropy (K=4) | 0.9575 ± 0.0670 | [0.9438, 0.9700] | 285,779 ± 16,239 |
| Mismatch Full Repair | 0.9150 ± 0.0903 | [0.8975, 0.9313] | 578,893 ± 31,923 |

PSR-UT improves CSR over One-shot by +0.0925 (paired 95% CI
[+0.0750,+0.1100]) for 10,422 additional attempted bytes
([+10,184,+10,664]). It is 0.0438 below Retry-All
([-0.0600,-0.0275]) while sending 188,125 fewer bytes
([-188,911,-187,340]).

The conventional Periodic Full Anti-Entropy control sends ordinary one-shot
deltas between K=4 full-replica rounds and rotates replica chunks fairly under
the same per-sender byte cap. It achieves higher CSR than PSR-UT by 0.0250
(PSR-UT minus Periodic: [-0.0425,-0.0075]) but requires 210,006 additional
attempted bytes per episode ([206,894,213,216]). It is therefore a higher-
traffic reliability endpoint, not a counterexample to PSR-UT's operating point.

## Ablations

- Utility-sensitive trigger versus action-triggered repair: +0.0925 CSR
  [+0.0750,+0.1100] for 8,272 additional bytes [8,041,8,507].
- Cadence: changing only the interval from one to four steps lowers PSR-UT CSR
  from 0.9325 to 0.8488, establishing a decision deadline.
- Scope: relative to Full Replica Repair, PSR-UT gains +0.0925 CSR
  [+0.0750,+0.1100] while sending 98,202 fewer bytes
  [-98,611,-97,790].

## Extensions and boundaries

- Loss 0.1/0.2/0.3/0.4/0.5: PSR-UT CSR is
  0.9913/0.9750/0.9325/0.9175/0.8388. It exceeds One-shot in every nonzero
  loss condition, but trails reliable ARQ at the higher-loss points.
- The delay boundary is explicit: PSR-UT CSR decreases from 0.9325 at zero
  delay to 0.9075, 0.8550, and 0.7388 at one, two, and four delivery steps.
- Scale: PSR-UT's paired advantage over One-shot is +0.0050, +0.0025,
  +0.0019, and +0.0003 at 4/8/16/32 agents. The practical cost reduction
  relative to ARQ remains large, but the reliability increment is small on
  these tiled-scale instances and is reported as such.
- Independent topologies retain material gains over One-shot: T-junction
  +0.1163 [0.0963,0.1375], asymmetric fork +0.1175 [0.0975,0.1388], and narrow
  bypass +0.1275 [0.1075,0.1475]. PSR-UT remains below ARQ in all three.
- Random-map negative controls are approximately equal to One-shot at each
  density. Generic replica discrepancy alone is not sufficient; the method's
  scope is a decision-critical route choice before a deadline.

The raw evidence used for this frozen report was removed from the compact
submission repository during curation. Recreate it only by rerunning the
frozen configurations in `docs/REPRODUCIBILITY.md`; no retained claim depends
on a hidden result file.
