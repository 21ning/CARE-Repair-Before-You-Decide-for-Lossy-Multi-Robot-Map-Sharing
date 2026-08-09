"""Explicit occupancy states retained by every online belief."""

from enum import IntEnum


class CellState(IntEnum):
    UNKNOWN = -1
    FREE = 0
    BLOCKED = 1
