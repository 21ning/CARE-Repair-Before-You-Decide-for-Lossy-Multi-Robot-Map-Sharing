# Commitment-gate ablation

Final CARE has one time check: scenario pairs whose action divergence precedes
the query--patch round trip are excluded from the exact scenario certificate.
It appends no optimistic/pessimistic route witness.

This historical experiment compares two **ablation-only auxiliary witness**
policies. `certificate_repair_route_gate` adds a route witness only when the
first-UNKNOWN route-slack proxy says it can arrive in time;
`certificate_repair_no_commitment_gate` always retains that raw route witness.
They keep candidate cells, sparse scenarios, exact hitting set, scenario-pair
deadline filter, codec, budgets, loss and delay identical. Neither policy is
the final `certificate_repair` algorithm. Diagnostics separately record gate
checks, closures, raw witness cells and suppressed cells.

Delay zero is an implementation negative control: the two policies must match
on every non-CPU result field. At positive delay the preregistered interpretation
requires the gated witness variant's paired seeker-success CI lower bound to
remain at or above -0.02 and its attempted-byte CI upper bound to be
non-positive. A CI containing
zero is not called proof of equivalence.

## Audited result

Delay zero passes: all 200 matched planner/map policy pairs are identical on
every non-CPU field.

| Planner | Delay | Gate − no-gate seeker success [95% CI] | Attempted KB difference [95% CI] |
| --- | ---: | ---: | ---: |
| A* | 1 | +0.0000 [+0.0000, +0.0000] | +0.00 [+0.00, +0.00] |
| A* | 2 | -0.0525 [-0.0725, -0.0325] | -6.07 [-6.30, -5.85] |
| A* | 4 | +0.0000 [+0.0000, +0.0000] | -12.64 [-12.80, -12.48] |
| D* Lite | 1 | +0.0000 [+0.0000, +0.0000] | +0.00 [+0.00, +0.00] |
| D* Lite | 2 | -0.0575 [-0.0800, -0.0375] | -6.09 [-6.32, -5.86] |
| D* Lite | 4 | +0.0000 [+0.0000, +0.0000] | -12.64 [-12.80, -12.48] |

The delay-2 cells fail the -0.02 non-inferiority rule. Therefore
`supports_incremental_commitment_gate_value=false`: the original route-slack
hard gate saves traffic but suppresses repairs that still improve seeker
completion. The delay-4 traffic saving does not rescue the across-delay claim.
This negative result is retained rather than reinterpreted as deadline value.

The finding does not invalidate the scenario-pair deadline filter, which is
present in both ablation policies and final CARE. It specifically rejects the
additional first-UNKNOWN route-slack gate. The ungated auxiliary route witness
is also not part of final CARE; the final algorithm uses only the exact
deadline-feasible scenario certificate.

```bash
python scripts/run_psr_suite.py \
  --config configs/care_commitment_gate_ablation_100map.yaml \
  --workers 32
python scripts/analyze_care_commitment_gate.py \
  --input-directory outputs/care_route_witness_gate_ablation_100map \
  --output-directory /tmp/care-gate-analysis
```
