"""Exact directed byte budget accounting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CommunicationBudget:
    total_bytes: int
    spent_bytes: int = 0

    def __post_init__(self) -> None:
        if self.total_bytes < 0:
            raise ValueError("communication budget cannot be negative")

    @property
    def remaining_bytes(self) -> int:
        return self.total_bytes - self.spent_bytes

    def can_spend(self, cost_bytes: int) -> bool:
        return cost_bytes >= 0 and cost_bytes <= self.remaining_bytes

    def spend(self, cost_bytes: int) -> None:
        if not self.can_spend(cost_bytes):
            raise ValueError("transmission exceeds exact byte budget")
        self.spent_bytes += cost_bytes
