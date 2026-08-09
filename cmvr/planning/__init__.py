"""Deterministic planning primitives used by CARE."""

from .astar import AStarPlanner
from .base import Coordinate, PlanResult, Planner
from .dstar_lite import DStarLitePlanner


def make_planner(name: str) -> Planner:
    """Create a supported planner by its stable experiment identifier."""
    if name == "astar":
        return AStarPlanner()
    if name == "dstar_lite":
        return DStarLitePlanner()
    raise ValueError(f"unsupported planner: {name}")

__all__ = [
    "AStarPlanner", "Coordinate", "DStarLitePlanner", "PlanResult", "Planner",
    "make_planner",
]
