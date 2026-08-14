# Information-sharing spectrum

CARE is placed between two explicit communication endpoints under the same
lossy, byte-capped link.

| Strategy | Trigger | Content | Endpoint |
| --- | --- | --- | --- |
| No Communication | never | nothing | zero-byte local sensing |
| CARE | action-conflicting uncertainty exists | bounded minimum decision certificate | selective repair |
| Continuous Full Sync | every step (`K=1`) | rotating known replica state | indiscriminate sharing |

Continuous Full Sync is not an oracle. It experiences the same packet loss,
delay, fixed-width cell codec, sender cap, deterministic link trace and
attempted-byte accounting as CARE. When a complete replica exceeds one-step
capacity, its deterministic cursor rotates through chunks.

## Frozen controlled experiment

The matrix has 1,800 executions: three strategies, three FOVs, A*/D* Lite and
100 paired layouts. Those layouts are independent clutter realizations under
the same multifork decision template.

This matrix predates direct role fields. Since every controlled observer
completes, seeker CSR is derived exactly as `2 × overall CSR - 1`. The primary
column below is explicitly derived; overall CSR remains a diagnostic.

| FOV | Planner | Strategy | Derived seeker CSR | Overall CSR | Mean EL | Attempted KB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 5×5 | A* | No Communication | 0.0000 | 0.5000 | 25.00 | 0.00 |
| 5×5 | A* | CARE | 0.4725 | 0.7362 | 25.00 | 53.25 |
| 5×5 | A* | Continuous Full Sync | 0.4500 | 0.7250 | 25.00 | 891.80 |
| 5×5 | D* Lite | No Communication | 0.0000 | 0.5000 | 25.00 | 0.00 |
| 5×5 | D* Lite | CARE | 0.5375 | 0.7688 | 25.00 | 53.25 |
| 5×5 | D* Lite | Continuous Full Sync | 0.5100 | 0.7550 | 25.00 | 891.80 |
| 7×7 | A* | No Communication | 0.4775 | 0.7388 | 25.00 | 0.00 |
| 7×7 | A* | CARE | 0.8750 | 0.9375 | 24.43 | 67.79 |
| 7×7 | A* | Continuous Full Sync | 0.9625 | 0.9812 | 24.14 | 861.12 |

At 5×5, derived paired CARE-minus-No-Communication seeker effects are +0.4725
with A* and +0.5375 with D* Lite. Full-Sync-minus-CARE is `-0.0225
[-0.0525, 0.0075]` and `-0.0275 [-0.0600, 0.0050]`; no primary reliability
advantage is detected despite about 838.55 KB additional traffic.

At 7×7 A*, Continuous Full Sync gains `+0.0875 [0.0550, 0.1225]` derived
seeker CSR, shortens all-robot episode length by `0.29 [0.19, 0.40]` steps,
and sends about 793.33 KB more. This is the expected high-reliability,
high-traffic endpoint.

The 25-step all-robot EL at 3×3 and 5×5 is a ceiling effect: incomplete seeker
trials hit the fixed horizon. It cannot support a primary speed claim. New runs
therefore also serialize `mean_seeker_completion_step_censored`.

Generated legacy tables are in `paper/tables/care_information_spectrum*` and
retain overall CSR for traceability. Submission-facing claims must use the
derived role endpoint or regenerated direct role fields.
