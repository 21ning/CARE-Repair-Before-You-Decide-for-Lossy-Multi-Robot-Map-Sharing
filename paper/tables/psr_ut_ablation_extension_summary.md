# PSR-UT ablations and extensions (100 independent maps per condition)

All intervals below are deterministic 20,000-draw bootstrap 95% confidence
intervals over the 100 independent maps. `ΔCSR` is paired PSR-UT minus the
named comparator.

## Full-method paired ablations

Every row pairs the full PSR-UT method (utility-sensitive trigger, one-step
cadence, and corridor-scoped repair) with the single component-matched
ablation on exactly the same 100 maps and loss traces. No One-shot comparison
appears in this ablation table.

| Component removed or changed | Full PSR-UT CSR mean ± SD | Ablated method CSR mean ± SD | Paired ΔCSR (95% CI) | Full / ablated attempted bytes |
| --- | ---: | ---: | ---: | ---: |
| Utility-sensitive trigger → action-triggered repair | 0.9325 ± 0.0803 | 0.8400 ± 0.1067 | +0.0925 [+0.0750, +0.1113] | 75,774 / 67,502 |
| Cadence: 1 step → 4 steps | 0.9325 ± 0.0803 | 0.8488 ± 0.1025 | +0.0838 [+0.0663, +0.1013] | 75,774 / 68,076 |
| Corridor scope → full-replica scope | 0.9325 ± 0.0803 | 0.8400 ± 0.1067 | +0.0925 [+0.0750, +0.1100] | 75,774 / 173,976 |

The first two ablations reduce traffic by 8.3 KB and 7.7 KB respectively but
lose reliability; full-replica repair is both less reliable and 98.2 KB more
expensive than full PSR-UT.

## Delay boundary (unchanged evidence)

| Delay steps | PSR-UT CSR mean ± SD | Attempted bytes | Paired ΔCSR vs One-shot (95% CI) |
| --- | ---: | ---: | ---: |
| Delay 0 | 0.9325 ± 0.0803 | 75,774 | One-shot | +0.0925 [+0.0750, +0.1100] |
| Delay 1 | 0.9075 ± 0.0967 | 76,719 | One-shot | +0.0613 [+0.0463, +0.0775] |
| Delay 2 | 0.8550 ± 0.1047 | 79,753 | One-shot | +0.0000 [0.0000, 0.0000] |
| Delay 4 | 0.7388 ± 0.0908 | 87,200 | One-shot | +0.0000 [0.0000, 0.0000] |

## Scale extension

| Agents / map | PSR-UT CSR mean ± SD | Attempted bytes | ΔCSR vs One-shot (95% CI) |
| --- | ---: | ---: | ---: |
| 4 / 24×24 | 0.7250 ± 0.0754 | 15,548 | +0.0050 [0.0000, +0.0125] |
| 8 / 32×32 | 0.7350 ± 0.0408 | 79,998 | +0.0025 [0.0000, +0.0063] |
| 16 / 48×48 | 0.7781 ± 0.0391 | 323,918 | +0.0019 [0.0000, +0.0044] |
| 32 / 64×64 | 0.8191 ± 0.0403 | 1,323,197 | +0.0003 [0.0000, +0.0009] |

## Independent topology extensions

| Topology | PSR-UT CSR mean ± SD | Attempted bytes | ΔCSR vs One-shot (95% CI) |
| --- | ---: | ---: | ---: |
| T-junction | 0.9775 ± 0.0544 | 93,808 | +0.1163 [+0.0963, +0.1375] |
| Asymmetric fork | 0.9563 ± 0.0741 | 83,520 | +0.1175 [+0.0975, +0.1388] |
| Narrow bypass | 0.9800 ± 0.0461 | 86,227 | +0.1275 [+0.1075, +0.1475] |
