from __future__ import annotations

import pytest

from cmvr.communication import LinkConfig, MessageKind, MessageStatus, UnreliableNetwork


def test_unreliable_network_is_seeded_and_delays_delivery() -> None:
    network = UnreliableNetwork(LinkConfig(loss_probability=0.0, delay_steps=2, seed=5))
    message = network.make_message(MessageKind.DELTA, 0, 1, b"x" * 13, 13, 3, category="data")
    assert network.send(message, 3)
    assert network.receive(4) == ()
    assert network.receive(5) == (message,)
    assert [event.status for event in network.events] == [MessageStatus.SENT, MessageStatus.DELIVERED]
    assert network.summary()["delivered_data_bytes"] == 13


def test_loss_and_burst_are_logged_without_delivery() -> None:
    network = UnreliableNetwork(LinkConfig(loss_probability=0.0, delay_steps=0, seed=1, burst_start_step=4, burst_length_steps=2))
    first = network.make_message(MessageKind.ACK, 1, 0, b"a" * 8, 8, 4, category="control")
    assert not network.send(first, 4)
    second = network.make_message(MessageKind.ACK, 1, 0, b"a" * 8, 8, 6, category="control")
    assert network.send(second, 6)
    assert network.receive(6) == (second,)
    assert network.summary()["lost_messages"] == 1
    assert network.summary()["delivered_control_bytes"] == 8


def test_network_accepts_only_exact_encoded_bytes() -> None:
    network = UnreliableNetwork(LinkConfig())
    with pytest.raises(TypeError, match="encoded bytes"):
        network.make_message(MessageKind.ACK, 0, 1, "not-bytes", 8, 0, category="control")
    with pytest.raises(ValueError, match="does not match"):
        network.make_message(MessageKind.ACK, 0, 1, b"short", 8, 0, category="control")
