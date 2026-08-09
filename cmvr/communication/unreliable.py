"""Deterministic directed loss/delay channel for explicit map messages.

This module intentionally has no access to a map, planner, or router.  It is a
small transport layer that charges every attempted data and control message and
keeps a complete immutable event log for later reliability analysis.
"""

from __future__ import annotations

from hashlib import sha256
from dataclasses import dataclass
from enum import Enum
from typing import Any


class MessageKind(str, Enum):
    DELTA = "delta"
    ACK = "ack"
    DIGEST_QUERY = "digest_query"
    REPLICA_DIGEST = "replica_digest"
    PATCH = "patch"


class MessageStatus(str, Enum):
    SENT = "sent"
    LOST = "lost"
    DELIVERED = "delivered"
    DEFERRED = "deferred"


@dataclass(frozen=True)
class LinkConfig:
    """A seeded link model shared by every policy in a matched run."""

    loss_probability: float = 0.0
    delay_steps: int = 0
    seed: int = 0
    burst_start_step: int | None = None
    burst_length_steps: int = 0

    def __post_init__(self) -> None:
        if not 0.0 <= self.loss_probability <= 1.0:
            raise ValueError("loss_probability must lie in [0, 1]")
        if self.delay_steps < 0 or self.burst_length_steps < 0:
            raise ValueError("delay and burst length must be non-negative")
        if self.burst_start_step is None and self.burst_length_steps:
            raise ValueError("a burst length requires burst_start_step")

    def is_burst_outage(self, step: int) -> bool:
        return (
            self.burst_start_step is not None
            and self.burst_start_step <= step < self.burst_start_step + self.burst_length_steps
        )


@dataclass(frozen=True)
class NetworkMessage:
    """An explicitly priced directed payload carried by :class:`UnreliableNetwork`."""

    message_id: int
    kind: MessageKind
    sender_id: int
    receiver_id: int
    payload: Any
    byte_size: int
    created_at: int
    category: str
    link_key: str
    is_retransmission: bool = False

    def __post_init__(self) -> None:
        if self.sender_id == self.receiver_id:
            raise ValueError("network messages must be directed to a different receiver")
        if self.byte_size <= 0:
            raise ValueError("network messages must have a positive authoritative byte size")


@dataclass(frozen=True)
class NetworkEvent:
    message_id: int
    kind: MessageKind
    sender_id: int
    receiver_id: int
    byte_size: int
    category: str
    attempted_at: int
    arrival_at: int | None
    status: MessageStatus
    is_retransmission: bool


class UnreliableNetwork:
    """Seeded loss/delay transport with append-only, auditable events."""

    def __init__(self, config: LinkConfig) -> None:
        self.config = config
        self._next_message_id = 0
        self._in_flight: dict[int, list[NetworkMessage]] = {}
        self.events: list[NetworkEvent] = []

    def make_message(
        self,
        kind: MessageKind,
        sender_id: int,
        receiver_id: int,
        payload: Any,
        byte_size: int,
        created_at: int,
        *,
        category: str,
        link_key: str | None = None,
        is_retransmission: bool = False,
    ) -> NetworkMessage:
        message = NetworkMessage(
            self._next_message_id, kind, sender_id, receiver_id, payload,
            byte_size, created_at, category,
            link_key or f"{kind.value}|{sender_id}|{receiver_id}|{created_at}|{self._next_message_id}",
            is_retransmission,
        )
        self._next_message_id += 1
        return message

    def defer(self, message: NetworkMessage, step: int) -> None:
        self.events.append(NetworkEvent(
            message.message_id, message.kind, message.sender_id, message.receiver_id,
            message.byte_size, message.category, step, None, MessageStatus.DEFERRED, message.is_retransmission,
        ))

    def send(self, message: NetworkMessage, step: int) -> bool:
        """Attempt a message once; return whether it was admitted to flight."""
        if self.config.is_burst_outage(step) or self._loss_draw(message.link_key) < self.config.loss_probability:
            self.events.append(NetworkEvent(
                message.message_id, message.kind, message.sender_id, message.receiver_id,
                message.byte_size, message.category, step, None, MessageStatus.LOST, message.is_retransmission,
            ))
            return False
        arrival = step + self.config.delay_steps
        self._in_flight.setdefault(arrival, []).append(message)
        self.events.append(NetworkEvent(
            message.message_id, message.kind, message.sender_id, message.receiver_id,
            message.byte_size, message.category, step, arrival, MessageStatus.SENT, message.is_retransmission,
        ))
        return True

    def _loss_draw(self, link_key: str) -> float:
        """A stable per-packet draw keeps common packets matched across policies."""
        digest = sha256(f"{self.config.seed}|{link_key}".encode("utf-8")).digest()
        return int.from_bytes(digest[:8], "big") / 2**64

    def receive(self, step: int) -> tuple[NetworkMessage, ...]:
        """Return all messages whose delivery time has arrived at ``step``."""
        arrived: list[NetworkMessage] = []
        for arrival in sorted(time for time in self._in_flight if time <= step):
            arrived.extend(self._in_flight.pop(arrival))
        arrived.sort(key=lambda message: message.message_id)
        for message in arrived:
            self.events.append(NetworkEvent(
                message.message_id, message.kind, message.sender_id, message.receiver_id,
                message.byte_size, message.category, message.created_at, step, MessageStatus.DELIVERED,
                message.is_retransmission,
            ))
        return tuple(arrived)

    def summary(self) -> dict[str, int]:
        delivered = [event for event in self.events if event.status is MessageStatus.DELIVERED]
        attempted = [event for event in self.events if event.status in {MessageStatus.SENT, MessageStatus.LOST}]
        result = {
            "attempted_messages": len(attempted),
            "attempted_bytes": sum(event.byte_size for event in attempted),
            "lost_messages": sum(event.status is MessageStatus.LOST for event in self.events),
            "lost_bytes": sum(event.byte_size for event in self.events if event.status is MessageStatus.LOST),
            "delivered_messages": len(delivered),
            "delivered_bytes": sum(event.byte_size for event in delivered),
            "deferred_messages": sum(event.status is MessageStatus.DEFERRED for event in self.events),
            "attempted_retransmission_messages": sum(event.is_retransmission for event in attempted),
            "attempted_retransmission_bytes": sum(event.byte_size for event in attempted if event.is_retransmission),
        }
        for category in ("data", "control", "repair"):
            result[f"attempted_{category}_bytes"] = sum(
                event.byte_size for event in attempted if event.category == category
            )
            result[f"delivered_{category}_bytes"] = sum(
                event.byte_size for event in delivered if event.category == category
            )
        return result
