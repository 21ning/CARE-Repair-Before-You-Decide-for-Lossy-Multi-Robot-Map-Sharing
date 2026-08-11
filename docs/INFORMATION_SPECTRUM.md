# Information-sharing spectrum

CARE is evaluated between two explicit communication endpoints rather than
only against variants that already communicate.

| Strategy | Trigger | Content | Intended endpoint |
| --- | --- | --- | --- |
| No Communication | never | nothing | zero-byte local sensing |
| CARE | decision conflict remains repairable | minimum bounded decision certificate | selective communication |
| Continuous Full Sync | every step (`K=1`) | rotating full-replica state | indiscriminate communication |

Continuous Full Sync is not an idealized oracle. It uses the same 30%-loss
link, delay, fixed cell codec, per-agent byte cap, deterministic loss trace and
attempted-byte accounting as CARE. It saturates the available data budget when
the complete replica does not fit. Calling this baseline perfectly informed
would be incorrect under packet loss; it is the strongest fair continuous
full-state endpoint under the declared communication contract.

## Frozen experiment

The matrix contains 1,800 complete episodes:

- 3 strategies;
- 3×3, 5×5 and 7×7 sensing;
- A* and D* Lite;
- 100 physically distinct matched maps per condition;
- 30% packet loss and zero link delay;
- 32 workers.

Every result includes CSR, mean episode length (EL), attempted traffic,
replica/path error and episode CPU time, with sample SD and 20,000-draw
map-cluster 95% CIs. Paired tables report CSR, EL and traffic differences.

## Results

| FOV | Planner | Strategy | CSR | Mean EL | Attempted KB |
| --- | --- | --- | ---: | ---: | ---: |
| 5×5 | A* | No Communication | 0.5000 | 25.00 | 0.00 |
| 5×5 | A* | CARE | 0.7362 | 25.00 | 53.25 |
| 5×5 | A* | Continuous Full Sync | 0.7250 | 25.00 | 891.80 |
| 5×5 | D* Lite | No Communication | 0.5000 | 25.00 | 0.00 |
| 5×5 | D* Lite | CARE | 0.7688 | 25.00 | 53.25 |
| 5×5 | D* Lite | Continuous Full Sync | 0.7550 | 25.00 | 891.80 |
| 7×7 | A* | No Communication | 0.7388 | 25.00 | 0.00 |
| 7×7 | A* | CARE | 0.9375 | 24.43 | 67.79 |
| 7×7 | A* | Continuous Full Sync | 0.9812 | 24.14 | 861.12 |

At 5×5, CARE improves over No Communication by `+0.2362
[0.2175, 0.2537]` CSR with A* and `+0.2687 [0.2500, 0.2875]` with D* Lite.
Continuous Full Sync minus CARE is `-0.0112 [-0.0262, 0.0037]` and `-0.0138
[-0.0300, 0.0025]`: no reliability advantage is detected despite about
838.55 KB more traffic.

At 7×7, Continuous Full Sync gains `+0.0437 [0.0275, 0.0612]` A* CSR over
CARE and shortens EL by `0.29 [0.19, 0.40]` steps, but sends about 793.33 KB
more. This is the expected high-reliability, high-traffic endpoint.

The 25-step EL at 3×3 and 5×5 is a real ceiling effect: an episode ends only
when all robots finish, so partially successful trials still reach the fixed
horizon. EL is therefore reported everywhere but is informative primarily at
7×7. It must not be used to claim a speed difference at 5×5.

Full mean/SD/CI results are in `paper/tables/care_information_spectrum.*` and
paired effects are in `paper/tables/care_information_spectrum_paired.*`.
