# CARE claim--evidence audit

This audit freezes what the submission may and may not claim.

| Claim | Direct evidence | Status / boundary |
| --- | --- | --- |
| The scenario query is minimum encoded size in the declared family. | `minimum_scenario_certificate`; exact enumeration tests in `tests/test_replica_protocol.py`; theorem in `CARE_ALGORITHM.md`. | Proven for at most 8 candidate cells, at most 2 blocked candidates, uniform 6-byte query entries. Not an unbounded robust-map theorem. |
| The repair decision uses no truth map or peer memory. | `replica_protocol.py` accepts receiver `BeliefMap`/paths; peer state is accessed only after an encoded query is delivered. | Supported by interface and runner separation. |
| CARE improves over One-shot at 30% loss. | `care_loss_baselines_paired.csv`: A* +0.0975 [0.0788, 0.1163], D* Lite +0.0950 [0.0775, 0.1125]. | Supported; map/trace paired. |
| CARE reduces traffic versus PSR-UT without detected primary-point reliability loss. | A*: +0.0050 CSR [-0.0125, 0.0225], -7.98 KB [-8.20, -7.76]. D*: +0.0100 CSR [-0.0063, 0.0262], -7.97 KB. | Supported as statistical equivalence/non-inferiority plus lower traffic, not proof of identical policies. |
| Exact certificates improve CARE-Lite efficiency. | A*: +0.0000 CSR [-0.0138, 0.0138], -0.83 KB [-1.00, -0.66]. D*: +0.0013 CSR [-0.0125, 0.0150], -0.94 KB. | Supported at the 30% primary point. At 50% loss CARE trades CSR for lower traffic. |
| CARE is robust across packet-loss rates. | Six-loss sweep in `care_loss_baseline_sweep.png`; positive paired gain over One-shot for every nonzero loss rate. | Supported for i.i.d. loss probabilities 0.1--0.5. No burst-loss claim. |
| CARE is planner-independent. | Full matched matrix repeated under A* and D* Lite; same qualitative ordering and near-identical traffic. | Supported for these two four-neighbor shortest-path planners, not arbitrary learned planners. |
| CARE dominates all baselines. | ARQ and Periodic Full obtain higher CSR at much higher traffic. | **Rejected.** The supported claim is a low-traffic Pareto operating point. |
| CARE outperforms DCC/SCRIMP/PPO. | No representation-matched reproduction exists; those methods solve different policy/communication problems. | **Not claimed.** They are related work, not numerical baselines. |
| CARE has negligible computation. | 0.767/0.867 s per 25-step episode under A*/D* Lite; 2.52x/2.09x CARE-Lite. | **Not claimed.** Computation is bounded and measured. |

## Submission freeze checklist

- complete final matrix: 9,600/9,600 episodes;
- 100 independent map clusters in every condition;
- map/trace pairing verified before statistics;
- sample SD, 20,000-draw cluster CI and paired effect size retained;
- full eight-policy primary table retained;
- high-loss negative boundary retained;
- A*/D* Lite planner sensitivity retained;
- exact wire byte accounting and decoder validation retained;
- complete test suite passes;
- README, method document, paper and generated artifacts use the same final
  method names and primary numbers.
