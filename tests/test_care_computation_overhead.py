from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from scripts.analyze_care_computation_overhead import analyze


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "paper" / "tables"
CSV_PATH = TABLES / "care_computation_overhead.csv"
MD_PATH = TABLES / "care_computation_overhead.md"
MANIFEST_PATH = TABLES / "care_computation_overhead_manifest.json"

METHODS = {"One-shot", "Path Top-K", "Single-Cell", "CARE-Lite", "CARE"}
PLANNERS = {"A*", "D* Lite"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows() -> list[dict[str, str]]:
    return list(csv.DictReader(CSV_PATH.open()))


def test_overhead_manifest_proves_frozen_design_and_integrity() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["complete"] is True
    assert manifest["analysis_only"] is True
    assert manifest["new_experiments_run"] is False
    assert manifest["condition"] == {
        "instance_family": "multifork_cluttered",
        "map_size": 32,
        "num_agents": 8,
        "observation_radius": 2,
        "fov": "5x5",
        "density": .2,
        "loss_probability": .3,
        "delay_steps": 0,
        "planners": ["astar", "dstar_lite"],
        "policies": [
            "one_shot_delta",
            "path_aware_top_k_repair",
            "single_cell_sensitivity_repair",
            "deadline_aware_repair",
            "certificate_repair",
        ],
        "independent_maps_per_condition": 100,
        "workers": 32,
    }
    audit = manifest["source_audit"]
    assert audit["source_rows"] == 6000
    assert audit["source_groups"] == 60
    assert audit["source_groups_all_have_100_paired_keys"] is True
    assert audit["selected_rows"] == 1000
    assert audit["selected_groups"] == 10
    assert audit["workers"] == 32
    assert "independent episodes" in audit["worker_semantics"]
    assert "one worker process" in audit["worker_semantics"]
    assert audit["paired_keys_per_condition"] == 100
    assert audit["paired_keys_exactly_0_through_99"] is True
    assert audit["unique_instance_fingerprints"] == 100
    assert audit["unique_layout_fingerprints"] == 100
    assert audit["same_instance_per_paired_key_across_planners_and_methods"] is True
    assert audit["same_network_seed_per_paired_key_across_planners_and_methods"] is True
    assert audit["summary_config_exactly_matches_yaml"] is True
    assert audit["common_control_cap_bytes"] == 512
    assert audit["care_path_single_query_cap_cells"] == 8
    assert audit["care_path_single_query_cap_bytes"] == 64
    assert audit["care_lite_query_cap_cells"] == 82
    assert audit["care_lite_query_cap_bytes"] == 508
    assert "not a query-cap-matched comparator" in audit["query_cap_scope"]
    assert set(audit["role_aware_fields_present"]) == {
        "all_seekers_success",
        "completed_mask",
        "critical_pair_success_rate",
        "observer_success_rate",
        "seeker_success_rate",
    }
    assert manifest["confidence_interval"]["draws"] == 20_000
    assert manifest["confidence_interval"]["public_base_seed"] == 20_260_814
    assert manifest["artifacts"]["csv_sha256"] == _sha256(CSV_PATH)
    assert manifest["artifacts"]["markdown_sha256"] == _sha256(MD_PATH)
    assert manifest["implementation"]["bootstrap_module_sha256"] == _sha256(
        ROOT / "scripts" / "bootstrap_ci.py"
    )
    assert manifest["implementation"]["script_sha256"] == _sha256(
        ROOT / "scripts" / "analyze_care_computation_overhead.py"
    )
    assert manifest["source"]["config_sha256"] == _sha256(
        ROOT / "configs" / "care_closest_work_baselines_fov_100map.yaml"
    )
    assert "not the additional 8-cell/64-byte" in manifest["comparison_limit"]
    assert "did not record generation git SHA" in manifest["provenance_limit"]
    assert "not a cross-method primary runtime" in (
        manifest["metric_semantics"]["planning_cpu_ms"]
    )


def test_overhead_table_is_complete_and_pairwise_coherent() -> None:
    rows = _rows()
    assert len(rows) == 10
    assert {(row["planner"], row["method"]) for row in rows} == {
        (planner, method) for planner in PLANNERS for method in METHODS
    }
    for planner in PLANNERS:
        planner_rows = [row for row in rows if row["planner"] == planner]
        care = next(row for row in planner_rows if row["method"] == "CARE")
        care_cpu = float(care["episode_cpu_ms_mean"])
        for row in planner_rows:
            assert row["paired_maps"] == "100"
            episode = float(row["episode_cpu_ms_mean"])
            planning = float(row["planning_cpu_ms_mean"])
            certificate = float(row["certificate_cpu_ms_mean"])
            assert 0.0 <= certificate <= planning <= episode
            assert float(row["episode_cpu_ms_ci95_low"]) <= episode
            assert episode <= float(row["episode_cpu_ms_ci95_high"])
            assert float(row["care_minus_method_episode_cpu_ms_mean"]) == pytest.approx(
                care_cpu - episode, abs=2e-6,
            )
            assert float(row["care_to_method_episode_cpu_ratio"]) == pytest.approx(
                care_cpu / episode, abs=2e-6,
            )
            if row["method"] == "CARE":
                assert certificate > 0
                assert float(row["certificate_scenario_planning_calls_mean"]) > 0
                assert float(row["care_minus_method_episode_cpu_ms_mean"]) == 0
                assert float(row["care_to_method_episode_cpu_ratio"]) == 1
            else:
                assert certificate == 0
                assert float(row["certificate_scenario_planning_calls_mean"]) == 0
        assert next(
            row for row in planner_rows if row["method"] == "Path Top-K"
        )["method_extra_planning_calls_mean"] == "0.000000"
        assert float(next(
            row for row in planner_rows if row["method"] == "Single-Cell"
        )["method_extra_planning_calls_mean"]) > 0
        assert float(next(
            row for row in planner_rows if row["method"] == "CARE-Lite"
        )["method_extra_planning_calls_mean"]) == 200
        for method in ("One-shot", "CARE-Lite"):
            row = next(row for row in planner_rows if row["method"] == method)
            assert row["candidate_cells_available"] == "no"
            assert row["candidate_cells_mean"] == ""
        for method in ("Path Top-K", "Single-Cell", "CARE"):
            row = next(row for row in planner_rows if row["method"] == method)
            assert row["candidate_cells_available"] == "yes"
            assert float(row["candidate_cells_mean"]) > 0


def test_submission_surfaces_keep_compute_and_cap_claims_aligned() -> None:
    paper = (ROOT / "paper" / "care_icassp_draft.tex").read_text()
    readme = (ROOT / "README.md").read_text()
    results = (ROOT / "docs" / "CARE_FINAL_RESULTS.md").read_text()
    task_aware = (ROOT / "docs" / "TASK_AWARE_BASELINES.md").read_text()
    claim_audit = (ROOT / "docs" / "CLAIM_EVIDENCE_AUDIT.md").read_text()
    closest_manifest = json.loads(
        (TABLES / "care_closest_work_manifest.json").read_text()
    )

    assert "4.43 $[4.22,4.64]$/3.26" in paper
    assert "3.92 $[3.68,4.17]$/3.05" in paper
    assert "does not establish a real-time guarantee" in paper
    assert "4.43× [4.22, 4.64] and 3.26× [3.03, 3.52]" in readme
    assert "3.916× [3.680, 4.172]/3.049× [2.805, 3.314]" in results
    assert "may select up to 82 cells (508" in task_aware
    assert "Rejected for CARE-Lite" in claim_audit
    scope = closest_manifest["comparison_scope"]
    assert "four closest-work adaptations" in scope
    assert "CARE-Lite shares the codec and 512-byte control cap" in scope


def test_frozen_raw_source_reproduces_overhead_artifacts(tmp_path: Path) -> None:
    source = ROOT / "outputs" / "care_closest_work_baselines_fov_100map"
    if not (source / "results.csv").is_file():
        pytest.skip("raw frozen output is intentionally not tracked in lightweight clones")
    generated = tmp_path / "tables"
    manifest = analyze(
        source,
        ROOT / "configs" / "care_closest_work_baselines_fov_100map.yaml",
        generated,
    )
    assert (generated / CSV_PATH.name).read_bytes() == CSV_PATH.read_bytes()
    assert (generated / MD_PATH.name).read_bytes() == MD_PATH.read_bytes()
    tracked_manifest = json.loads(MANIFEST_PATH.read_text())
    assert manifest["source"] == tracked_manifest["source"]
    assert manifest["condition"] == tracked_manifest["condition"]
    assert manifest["source_audit"] == tracked_manifest["source_audit"]
    assert manifest["metric_semantics"] == tracked_manifest["metric_semantics"]
    assert manifest["confidence_interval"] == tracked_manifest["confidence_interval"]
    assert manifest["comparison_limit"] == tracked_manifest["comparison_limit"]
    assert manifest["provenance_limit"] == tracked_manifest["provenance_limit"]
