from __future__ import annotations

from scripts.analyze_psr_external_baselines import analyze


def _rows() -> list[dict[str, str]]:
    policies = (
        "one_shot_delta", "retry_all_arq", "path_weighted_arq",
        "periodic_full_sync", "mismatch_triggered_full_repair", "utility_triggered_repair",
    )
    rows = []
    for seed in range(100):
        for policy in policies:
            rows.append({
                "seed": str(seed), "layout_seed": str(seed), "network_seed": str(seed),
                "policy": policy, "loss_probability": "0.3", "delay_steps": "0",
                "instance_fingerprint": f"instance-{seed}", "completion_success_rate": "1.0",
                "episode_length": "20", "attempted_bytes": "100", "attempted_data_bytes": "50",
                "attempted_control_bytes": "25", "attempted_repair_bytes": "25",
                "delivered_bytes": "70", "delivered_data_bytes": "35",
                "delivered_control_bytes": "20", "delivered_repair_bytes": "15",
                "attempted_retransmission_messages": "2", "attempted_retransmission_bytes": "26",
            })
    return rows


def test_external_baseline_analysis_requires_complete_matched_matrix() -> None:
    summary, pairs = analyze(_rows())
    assert len(summary) == 6
    assert len(pairs) == 60
    assert all(row["paired_trials"] == 100 for row in pairs)
