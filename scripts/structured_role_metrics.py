"""Role-aware metrics for the frozen structured CARE experiments.

The legacy structured CSVs predate per-role result fields.  Their generators
pair one observer with one seeker for every critical fork.  The observers start
one move from their goals and were independently audited to succeed in every
serialized structured layout.  Consequently, for these *structured families
only*, seeker CSR is exactly ``2 * overall completion rate - 1``.

Never apply this identity to the unconditioned random-map negative control.
"""

from __future__ import annotations


STRUCTURED_FAMILIES = {
    "multifork_cluttered",
    "multifork_t_junction",
    "multifork_asymmetric_fork",
    "multifork_narrow_bypass",
    "tiled_cluttered_fork",
}


def is_structured_row(row: dict[str, str]) -> bool:
    """Return whether the observer/seeker identity is valid for ``row``."""

    return row.get("topology_family", "") in STRUCTURED_FAMILIES


def seeker_success_rate(row: dict[str, str]) -> float:
    """Read direct seeker CSR, or derive it for an audited legacy family."""

    direct = row.get("seeker_success_rate", "")
    if direct not in (None, ""):
        return float(direct)
    if not is_structured_row(row):
        raise ValueError(
            "seeker CSR cannot be derived outside an audited structured family: "
            f"{row.get('topology_family')!r}"
        )
    value = 2.0 * float(row["completion_success_rate"]) - 1.0
    if not -1e-12 <= value <= 1.0 + 1e-12:
        raise ValueError(f"derived seeker CSR outside [0, 1]: {value}")
    return min(1.0, max(0.0, value))


def metric_value(row: dict[str, str], metric: str) -> float:
    """Read a numeric metric, including role-aware seeker CSR."""

    if metric == "seeker_success_rate":
        return seeker_success_rate(row)
    return float(row[metric])


ROLE_PROVENANCE = (
    "Legacy structured rows omit role fields. Seeker CSR is derived exactly as "
    "2*overall_completion_rate-1 after auditing that all paired observers "
    "succeed; the identity is never used for random-map controls."
)
