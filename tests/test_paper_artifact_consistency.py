from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "paper" / "tables"


def _rows(name: str) -> list[dict[str, str]]:
    return list(csv.DictReader((TABLES / name).open()))


def _ci_pair(text: str) -> tuple[float, float]:
    low, high = text.strip("[]").split(",")
    return float(low), float(high)


def test_overlapping_primary_anchors_have_identical_cis() -> None:
    main = _rows("care_loss_baselines_primary.csv")
    closest = _rows("care_closest_work_primary.csv")
    delay = _rows("care_cross_planner_primary.csv")

    for planner in ("A*", "D* Lite"):
        delay_planner = "astar" if planner == "A*" else "dstar_lite"
        for method in ("One-shot", "CARE"):
            main_row = next(
                row for row in main
                if row["planner"] == planner and row["method"] == method
            )
            closest_row = next(
                row for row in closest
                if row["planner"] == planner and row["method"] == method
            )
            delay_row = next(
                row for row in delay
                if row["planner"] == delay_planner and row["method"] == method
            )
            assert main_row["csr_mean"] == closest_row["seeker_csr_mean"]
            assert main_row["csr_std"] == closest_row["seeker_csr_std"]
            assert main_row["csr_ci95"] == closest_row["seeker_csr_ci95"]
            assert _ci_pair(main_row["csr_ci95"]) == (
                float(delay_row["seeker_csr_ci95_low"]),
                float(delay_row["seeker_csr_ci95_high"]),
            )


def test_gate_zero_delay_identical_vectors_have_identical_cis() -> None:
    rows = _rows("care_commitment_gate.csv")
    for planner in ("A*", "D* Lite"):
        matched = [
            row for row in rows
            if row["planner"] == planner and row["delay_steps"] == "0"
        ]
        assert len(matched) == 2
        assert len({row["seeker_success_ci95"] for row in matched}) == 1
        assert len({row["pair_success_ci95"] for row in matched}) == 1
        assert all(
            row["seeker_success_ci95"] == row["pair_success_ci95"]
            for row in matched
        )


def test_natural_scale_paired_table_exposes_all_null_intervals() -> None:
    rows = _rows("care_natural_scale_paired.csv")
    assert len(rows) == 8
    assert {(row["agents"], row["planner"]) for row in rows} == {
        (str(agents), planner)
        for agents in (4, 8, 16, 32) for planner in ("A*", "D* Lite")
    }
    assert all(
        (low := _ci_pair(row["seeker_ci95"])[0]) <= 0.0
        <= _ci_pair(row["seeker_ci95"])[1]
        for row in rows
    )
