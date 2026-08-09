#!/usr/bin/env python3
"""Audit and summarize the final PSR-UT 100-independent-map matrix."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


METRICS = (
    "completion_success_rate", "instance_success_rate", "episode_length",
    "mean_replica_error", "mean_path_repairable_error", "mean_path_truth_error",
    "mean_recovery_latency", "unresolved_repair_events", "repair_events",
    "attempted_messages", "attempted_bytes", "lost_messages", "lost_bytes",
    "delivered_messages", "delivered_bytes", "deferred_messages",
    "attempted_retransmission_messages", "attempted_retransmission_bytes",
    "attempted_data_bytes", "delivered_data_bytes", "attempted_control_bytes",
    "delivered_control_bytes", "attempted_repair_bytes", "delivered_repair_bytes",
)
PAIRED_METRICS = (
    "completion_success_rate", "instance_success_rate", "episode_length",
    "mean_replica_error", "mean_path_repairable_error", "delivered_bytes",
    "attempted_bytes", "attempted_retransmission_bytes",
)
FOCAL_POLICY = "utility_triggered_repair"


def bootstrap(values: np.ndarray, *, seed: int) -> tuple[float, float]:
    """Deterministic bootstrap confidence interval over independent maps."""
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(20_000, len(values)), replace=True).mean(axis=1)
    return tuple(float(item) for item in np.quantile(means, (.025, .975)))


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def load_matrix(root: Path) -> dict[str, list[dict[str, str]]]:
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("design") != "100 independent matched maps with one independent network trace per map":
        raise ValueError("unexpected formal-matrix design")
    if len(manifest.get("map_seeds", ())) != 100:
        raise ValueError("formal matrix must contain 100 independent map seeds")
    outputs: dict[str, list[dict[str, str]]] = {}
    for study in manifest["studies"]:
        name = study["study"]
        rows = list(csv.DictReader((root / name / "results.csv").open()))
        required_fields = {"topology_family", "map_size", "num_agents", "layout_seed", "network_seed"}
        if not rows or not required_fields.issubset(rows[0]):
            raise ValueError(f"{name} lacks required per-row design fields")
        config = study["config"]
        if len(config.get("seeds", ())) != 100:
            raise ValueError(f"{name} does not specify 100 independent map seeds")
        expected = 100 * len(config["obstacle_densities"]) * len(config["loss_probabilities"]) * len(config["delay_steps"]) * len(config["policies"])
        if len(rows) != expected or study["rows"] != expected:
            raise ValueError(f"{name} has missing or unexpected raw rows")
        groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[(row["density"], row["loss_probability"], row["delay_steps"], row["policy"])].append(row)
        expected_pairs = {(str(seed), str(seed)) for seed in config["seeds"]}
        for group in groups.values():
            actual_pairs = {(row["layout_seed"], row["network_seed"]) for row in group}
            if len(group) != 100 or actual_pairs != expected_pairs:
                raise ValueError(f"{name} does not have the frozen 100-independent-map design")
        outputs[name] = rows
    return outputs


def summarize(studies: dict[str, list[dict[str, str]]]) -> list[dict]:
    output = []
    for study, rows in studies.items():
        groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            groups[(row["density"], row["loss_probability"], row["delay_steps"], row["policy"])].append(row)
        for group_index, ((density, loss, delay, policy), group) in enumerate(sorted(groups.items())):
            item = {"study": study, "density": density, "loss_probability": loss, "delay_steps": delay,
                    "policy": policy, "trials": len(group), "independent_maps": len({row["layout_seed"] for row in group})}
            for metric_index, metric in enumerate(METRICS):
                values = np.asarray([float(row[metric]) for row in group if row[metric] not in {"", "None"}])
                item[f"mean_{metric}"] = float(values.mean()) if len(values) else None
                item[f"std_{metric}"] = float(values.std(ddof=1)) if len(values) > 1 else None
                low, high = bootstrap(values, seed=group_index * len(METRICS) + metric_index) if len(values) else (None, None)
                item[f"ci95_low_{metric}"], item[f"ci95_high_{metric}"] = low, high
            output.append(item)
    return output


def paired(studies: dict[str, list[dict[str, str]]]) -> list[dict]:
    output = []
    for study, rows in studies.items():
        groups: dict[tuple[str, str, str], dict[str, dict[tuple[str, str], dict[str, str]]]] = defaultdict(lambda: defaultdict(dict))
        for row in rows:
            groups[(row["density"], row["loss_probability"], row["delay_steps"])][row["policy"]][(row["layout_seed"], row["network_seed"])] = row
        for (density, loss, delay), policies in groups.items():
            if FOCAL_POLICY not in policies:
                continue
            for comparator, comparator_rows in policies.items():
                if comparator == FOCAL_POLICY:
                    continue
                pairs = sorted(set(policies[FOCAL_POLICY]) & set(comparator_rows))
                if len(pairs) != 100:
                    raise ValueError(f"{study}: incomplete PSR-UT pairing against {comparator}")
                for metric_index, metric in enumerate(PAIRED_METRICS):
                    values = np.asarray([float(policies[FOCAL_POLICY][pair][metric]) - float(comparator_rows[pair][metric]) for pair in pairs])
                    low, high = bootstrap(values, seed=10_000 + metric_index)
                    output.append({"study": study, "density": density, "loss_probability": loss, "delay_steps": delay,
                                   "metric": metric, "left": FOCAL_POLICY, "right": comparator, "paired_trials": len(pairs),
                                   "mean_difference": float(values.mean()), "std_difference": float(values.std(ddof=1)),
                                   "ci95_low": low, "ci95_high": high})
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-directory", type=Path, default=Path("results/psr_ut_formal_100map_matrix"))
    parser.add_argument("--output-directory", type=Path, default=Path("results/psr_ut_formal_100map_matrix/analysis"))
    args = parser.parse_args(); args.output_directory.mkdir(parents=True, exist_ok=True)
    studies = load_matrix(args.input_directory)
    summary, comparisons = summarize(studies), paired(studies)
    write_csv(args.output_directory / "summary_mean_std_ci.csv", summary)
    write_csv(args.output_directory / "paired_mean_std_ci.csv", comparisons)
    (args.output_directory / "README.md").write_text(
        "# Formal PSR-UT 100-map analysis\n\nEach summary uses 100 independent maps with one matched independent network trace per map, trial-level sample standard deviation (`ddof=1`), and a deterministic 20,000-draw bootstrap 95% CI. Paired rows subtract the matched policy outcomes on each map before bootstrapping.\n"
    )
    print(json.dumps({"studies": len(studies), "summary_rows": len(summary), "paired_rows": len(comparisons)}))


if __name__ == "__main__":
    main()
