from __future__ import annotations

import numpy as np

from scripts.analyze_care_closest_work import _bootstrap as closest_bootstrap
from scripts.analyze_care_loss_baselines import bootstrap as loss_bootstrap
from scripts.bootstrap_ci import bootstrap_mean_ci, bootstrap_ratio_ci


def test_identical_map_vector_has_one_ci_across_analyzers() -> None:
    values = np.asarray([0.0, 0.25, 0.5, 0.75, 1.0] * 20)
    expected = bootstrap_mean_ci(values)

    assert loss_bootstrap(values, seed=1) == expected
    assert closest_bootstrap(values, seed=999_999) == expected
    assert bootstrap_mean_ci(values[::-1]) == expected


def test_ratio_bootstrap_is_deterministic_and_cluster_paired() -> None:
    numerators = np.asarray([0.0, 1.0, 1.0, 2.0] * 25)
    denominators = np.asarray([1.0, 2.0, 2.0, 3.0] * 25)

    first = bootstrap_ratio_ci(numerators, denominators)
    second = bootstrap_ratio_ci(numerators.copy(), denominators.copy())

    assert first == second
    assert bootstrap_ratio_ci(numerators[::-1], denominators[::-1]) == first
    assert first[0] <= numerators.sum() / denominators.sum() <= first[1]
