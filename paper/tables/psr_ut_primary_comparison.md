# PSR-UT primary comparison (100 independent matched maps)

95% CIs use a deterministic 20,000-draw bootstrap over independent maps.

| Method | CSR (95% CI) | Attempted bytes / episode (95% CI) |
| --- | ---: | ---: |
| One-shot | 0.8400 [0.8200, 0.8600] | 65,352 [65,114, 65,594] |
| Retry-All ARQ | 0.9762 [0.9650, 0.9862] | 263,898 [263,082, 264,724] |
| Path-Weighted ARQ | 0.9775 [0.9663, 0.9875] | 263,920 [263,132, 264,700] |
| Periodic Full (K=4) | 0.9575 [0.9437, 0.9700] | 285,779 [282,698, 288,979] |
| Mismatch Full Repair | 0.9150 [0.8975, 0.9313] | 578,893 [572,609, 585,022] |
| PSR-UT | 0.9325 [0.9163, 0.9475] | 75,774 [75,511, 76,044] |
