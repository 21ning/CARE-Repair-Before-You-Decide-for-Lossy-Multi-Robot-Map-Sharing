"""Stable one-cell packet representation for every communication policy."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .cell_state import CellState


@dataclass(frozen=True)
class PacketFormat:
    """Fixed canonical wire allocation for a one-cell update packet."""

    protocol_header_bytes: int = 1
    provenance_coordinate_state_bytes: int = 4
    version_time_bytes: int = 6
    checksum_bytes: int = 2

    @property
    def encoded_size_bytes(self) -> int:
        return (
            self.protocol_header_bytes
            + self.provenance_coordinate_state_bytes
            + self.version_time_bytes
            + self.checksum_bytes
        )


DEFAULT_PACKET_FORMAT = PacketFormat()


@dataclass(frozen=True)
class MapUpdate:
    """An immutable sender-observed cell version and its fixed packet size."""

    update_id: str
    sender_id: int
    x: int
    y: int
    cell_state: CellState
    version: int
    observed_at: int
    encoded_size_bytes: int

    @classmethod
    def create(
        cls,
        *,
        sender_id: int,
        x: int,
        y: int,
        cell_state: CellState,
        version: int,
        observed_at: int,
        packet_format: PacketFormat = DEFAULT_PACKET_FORMAT,
    ) -> "MapUpdate":
        stable_fields = f"v1|{sender_id}|{x}|{y}|{int(cell_state)}|{version}|{observed_at}"
        update_id = sha256(stable_fields.encode("utf-8")).hexdigest()
        return cls(
            update_id=update_id,
            sender_id=sender_id,
            x=x,
            y=y,
            cell_state=CellState(cell_state),
            version=version,
            observed_at=observed_at,
            encoded_size_bytes=packet_format.encoded_size_bytes,
        )

    def to_dict(self) -> dict[str, int | str]:
        return {
            "update_id": self.update_id,
            "sender_id": self.sender_id,
            "x": self.x,
            "y": self.y,
            "cell_state": int(self.cell_state),
            "version": self.version,
            "observed_at": self.observed_at,
            "encoded_size_bytes": self.encoded_size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, int | str]) -> "MapUpdate":
        return cls(
            update_id=str(data["update_id"]),
            sender_id=int(data["sender_id"]),
            x=int(data["x"]),
            y=int(data["y"]),
            cell_state=CellState(int(data["cell_state"])),
            version=int(data["version"]),
            observed_at=int(data["observed_at"]),
            encoded_size_bytes=int(data["encoded_size_bytes"]),
        )
