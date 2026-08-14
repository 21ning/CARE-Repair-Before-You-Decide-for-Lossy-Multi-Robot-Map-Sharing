"""Canonical map-cluster bootstrap confidence intervals.

Every analyzer orders observations by the frozen map/network key before calling
these helpers.  All endpoints with the same number of maps use one public,
fixed resampling-index matrix.  Consequently, the same endpoint vector always
receives the same interval across tables and studies, without making the
pseudo-random stream depend on observed values or analyzer loop order.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np


BOOTSTRAP_DRAWS = 20_000
BOOTSTRAP_SEED = 20_260_814


def _vector(values: np.ndarray) -> np.ndarray:
    result = np.ascontiguousarray(values, dtype="<f8")
    if result.ndim != 1 or not len(result):
        raise ValueError("bootstrap input must be a non-empty one-dimensional vector")
    if not np.isfinite(result).all():
        raise ValueError("bootstrap input must contain only finite values")
    return result


@lru_cache(maxsize=None)
def _cluster_indices(map_count: int, draws: int) -> np.ndarray:
    if map_count < 1 or draws < 1:
        raise ValueError("map count and bootstrap draws must be positive")
    # Mix only declared design constants, never method, metric, or data values.
    seed = BOOTSTRAP_SEED + 1_000_003 * map_count + 10_007 * draws
    indices = np.random.default_rng(seed).integers(
        0, map_count, size=(draws, map_count),
    )
    indices.flags.writeable = False
    return indices


def bootstrap_mean_ci(
    values: np.ndarray, *, draws: int = BOOTSTRAP_DRAWS,
) -> tuple[float, float]:
    """Return a deterministic percentile CI for a map-level mean."""
    # Map clusters are exchangeable for a marginal mean.  Canonical sorting
    # prevents a lexicographic-vs-numeric seed order from changing Monte Carlo
    # quantiles for an otherwise identical endpoint vector.
    vector = np.sort(_vector(values))
    if draws < 1:
        raise ValueError("bootstrap draws must be positive")
    indices = _cluster_indices(len(vector), draws)
    means = vector[indices].mean(axis=1)
    return tuple(float(value) for value in np.quantile(means, (.025, .975)))


def bootstrap_ratio_ci(
    numerators: np.ndarray, denominators: np.ndarray, *,
    draws: int = BOOTSTRAP_DRAWS,
) -> tuple[float, float]:
    """Return a deterministic cluster-bootstrap CI for a ratio of sums."""
    numerator = _vector(numerators)
    denominator = _vector(denominators)
    if numerator.shape != denominator.shape:
        raise ValueError("ratio bootstrap vectors must have identical shapes")
    # Preserve each map's numerator/denominator pair while canonicalizing the
    # exchangeable cluster order.
    order = np.lexsort((denominator, numerator))
    numerator = numerator[order]
    denominator = denominator[order]
    if draws < 1:
        raise ValueError("bootstrap draws must be positive")
    indices = _cluster_indices(len(numerator), draws)
    numerator_sums = numerator[indices].sum(axis=1)
    denominator_sums = denominator[indices].sum(axis=1)
    ratios = np.divide(
        numerator_sums, denominator_sums,
        out=np.full_like(numerator_sums, np.nan),
        where=denominator_sums > 0,
    )
    if np.isnan(ratios).all():
        raise ValueError("ratio bootstrap has no positive denominator resamples")
    return tuple(float(value) for value in np.nanquantile(ratios, (.025, .975)))
