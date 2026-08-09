"""Sender-local observation to unique sparse update conversion."""

from __future__ import annotations

from .belief_map import BeliefMap
from .map_update import DEFAULT_PACKET_FORMAT, MapUpdate, PacketFormat


class DeltaEncoder:
    """Owns no truth map; it only transforms an explicit local observation."""

    def __init__(self, packet_format: PacketFormat = DEFAULT_PACKET_FORMAT) -> None:
        self.packet_format = packet_format

    def observe(
        self,
        belief: BeliefMap,
        local_obstacles,
        position: tuple[int, int],
        *,
        sender_id: int,
        step: int,
    ) -> tuple[MapUpdate, ...]:
        return belief.integrate_local_observation(
            local_obstacles,
            position,
            sender_id=sender_id,
            observed_at=step,
            packet_format=self.packet_format,
        )
