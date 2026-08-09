from __future__ import annotations

from dataclasses import replace

import pytest

from cmvr.communication import CommunicationBudget, LinkConfig, MessageStatus, UnreliableNetwork
from cmvr.env import PSRClosedLoopRunner, PSRConfig, ReplicaPolicy, generate_instance
from cmvr.env.psr_runner import _DeliveryTask
from cmvr.mapping import BeliefMap, CellState, MapUpdate
from cmvr.utils.config import ExperimentConfig


def _instance():
    return generate_instance(ExperimentConfig(
        seed=0, map_size=12, obstacle_density=.15, num_agents=4,
        observation_radius=3, max_episode_steps=24,
    ))


def _config(loss: float = .3) -> PSRConfig:
    return PSRConfig(
        data_bytes_per_agent_per_step=104,
        control_bytes_per_agent_per_step=512,
        repair_interval_steps=2,
        link=LinkConfig(loss_probability=loss, delay_steps=0, seed=500),
    )


def test_psr_runner_is_deterministic_and_accounts_for_repair() -> None:
    first = PSRClosedLoopRunner(policy=ReplicaPolicy.UTILITY_TRIGGERED_REPAIR, config=_config()).run(_instance())
    second = PSRClosedLoopRunner(policy=ReplicaPolicy.UTILITY_TRIGGERED_REPAIR, config=_config()).run(_instance())
    assert first == second
    assert first.network_summary["attempted_control_bytes"] > 0
    assert first.network_summary["attempted_repair_bytes"] > 0
    assert first.network_summary["attempted_bytes"] == (
        first.network_summary["attempted_data_bytes"]
        + first.network_summary["attempted_control_bytes"]
        + first.network_summary["attempted_repair_bytes"]
    )


def test_step_observer_receives_isolated_replica_snapshots() -> None:
    snapshots = []
    runner = PSRClosedLoopRunner(
        policy=ReplicaPolicy.UTILITY_TRIGGERED_REPAIR,
        config=_config(loss=0.0),
        step_observer=lambda step, beliefs, positions: snapshots.append(
            (step, beliefs, positions)
        ),
    )
    result = runner.run(_instance())

    assert len(snapshots) == result.episode_length
    assert snapshots[0][0] == 0
    assert len(snapshots[0][1]) == _instance().num_agents
    fingerprint = snapshots[0][1][0].fingerprint()
    snapshots[-1][1][0].occupancy.fill(CellState.UNKNOWN)
    assert snapshots[0][1][0].fingerprint() == fingerprint


def test_runner_rejects_packet_sizes_that_disagree_with_wire_codec() -> None:
    with pytest.raises(ValueError, match="canonical wire codec"):
        PSRClosedLoopRunner(
            policy=ReplicaPolicy.UTILITY_TRIGGERED_REPAIR,
            config=replace(_config(), digest_entry_bytes=7),
        )


def test_runner_rejects_instances_outside_digest_bit_widths() -> None:
    oversized = replace(_instance(), max_episode_steps=65_536)
    with pytest.raises(ValueError, match="65,535"):
        PSRClosedLoopRunner(
            policy=ReplicaPolicy.UTILITY_TRIGGERED_REPAIR, config=_config(),
        ).run(oversized)


def test_retry_all_uses_ack_control_traffic_and_no_comm_uses_none() -> None:
    retry = PSRClosedLoopRunner(policy=ReplicaPolicy.RETRY_ALL_ARQ, config=_config(loss=0.0)).run(_instance())
    none = PSRClosedLoopRunner(policy=ReplicaPolicy.NO_COMMUNICATION, config=_config(loss=0.0)).run(_instance())
    assert retry.network_summary["attempted_data_bytes"] > 0
    assert retry.network_summary["attempted_control_bytes"] > 0
    assert none.network_summary["attempted_bytes"] == 0


def test_retry_all_interleaves_first_attempts_and_old_losses() -> None:
    """A small cap must make progress on both fresh and retried state."""
    runner = PSRClosedLoopRunner(policy=ReplicaPolicy.RETRY_ALL_ARQ, config=_config())
    old = MapUpdate.create(sender_id=0, x=1, y=1, cell_state=0, version=1, observed_at=0)
    fresh = MapUpdate.create(sender_id=0, x=2, y=2, cell_state=0, version=1, observed_at=1)
    old_task = _DeliveryTask(old, receiver_id=1, attempts=4)
    fresh_task = _DeliveryTask(fresh, receiver_id=1, attempts=0)
    outboxes = [{old_task.key: old_task, fresh_task.key: fresh_task}, {}]
    network = UnreliableNetwork(LinkConfig(loss_probability=0.0, delay_steps=0, seed=1))
    budget = [CommunicationBudget(2 * fresh.encoded_size_bytes), CommunicationBudget(0)]

    runner._send_delta_tasks(network, step=0, outboxes=outboxes, data_budget=budget)

    sent = [event for event in network.events if event.status is MessageStatus.SENT]
    assert len(sent) == 2
    assert all(event.byte_size == fresh.encoded_size_bytes for event in sent)
    assert fresh_task.attempts == 1
    assert old_task.attempts == 5
    assert network.summary()["attempted_retransmission_messages"] == 1


def test_full_replica_repair_uses_the_same_budgeted_transport() -> None:
    result = PSRClosedLoopRunner(
        policy=ReplicaPolicy.FULL_REPLICA_REPAIR, config=_config(),
    ).run(_instance())
    assert result.network_summary["attempted_control_bytes"] > 0
    assert result.network_summary["attempted_bytes"] == (
        result.network_summary["attempted_data_bytes"]
        + result.network_summary["attempted_control_bytes"]
        + result.network_summary["attempted_repair_bytes"]
    )


def test_periodic_full_sync_is_deterministic_and_uses_only_the_shared_data_budget() -> None:
    config = PSRConfig(
        data_bytes_per_agent_per_step=104,
        control_bytes_per_agent_per_step=512,
        repair_interval_steps=2,
        sync_interval_steps=2,
        link=LinkConfig(loss_probability=0.0, delay_steps=0, seed=500),
    )
    first = PSRClosedLoopRunner(policy=ReplicaPolicy.PERIODIC_FULL_SYNC, config=config).run(_instance())
    second = PSRClosedLoopRunner(policy=ReplicaPolicy.PERIODIC_FULL_SYNC, config=config).run(_instance())
    assert first == second
    assert first.network_summary["attempted_data_bytes"] > 0
    assert first.network_summary["attempted_repair_bytes"] > 0
    assert first.network_summary["attempted_control_bytes"] == 0
    assert first.network_summary["attempted_bytes"] == (
        first.network_summary["attempted_data_bytes"]
        + first.network_summary["attempted_control_bytes"]
        + first.network_summary["attempted_repair_bytes"]
    )


def test_periodic_full_sync_rotates_peers_under_a_small_budget() -> None:
    runner = PSRClosedLoopRunner(policy=ReplicaPolicy.PERIODIC_FULL_SYNC, config=PSRConfig(
        data_bytes_per_agent_per_step=2 * 13,
        control_bytes_per_agent_per_step=32,
        sync_interval_steps=2,
        link=LinkConfig(loss_probability=0.0, delay_steps=0, seed=1),
    ))
    beliefs = tuple(BeliefMap((2, 2)) for _ in range(3))
    for x in range(2):
        for y in range(2):
            beliefs[0].apply_update(MapUpdate.create(
                sender_id=0, x=x, y=y, cell_state=0, version=1, observed_at=0,
            ))
    network = UnreliableNetwork(LinkConfig(loss_probability=0.0, delay_steps=0, seed=1))
    runner._periodic_full_sync(network, 0, beliefs, [CommunicationBudget(26), CommunicationBudget(0), CommunicationBudget(0)])
    first_receivers = {event.receiver_id for event in network.events if event.sender_id == 0 and event.status is MessageStatus.SENT}
    runner._periodic_full_sync(network, 2, beliefs, [CommunicationBudget(26), CommunicationBudget(0), CommunicationBudget(0)])
    second_receivers = {event.receiver_id for event in network.events if event.sender_id == 0 and event.attempted_at == 2 and event.status is MessageStatus.SENT}
    assert first_receivers == {1, 2}
    assert second_receivers == {1, 2}


def test_path_weighted_arq_prioritizes_receiver_local_path_updates() -> None:
    runner = PSRClosedLoopRunner(policy=ReplicaPolicy.PATH_WEIGHTED_ARQ, config=_config(loss=0.0))
    near = MapUpdate.create(sender_id=0, x=1, y=2, cell_state=0, version=1, observed_at=0)
    far = MapUpdate.create(sender_id=0, x=8, y=8, cell_state=0, version=1, observed_at=0)
    near_task, far_task = _DeliveryTask(near, receiver_id=1), _DeliveryTask(far, receiver_id=1)
    outboxes = [{near_task.key: near_task, far_task.key: far_task}, {}]
    network = UnreliableNetwork(LinkConfig(loss_probability=0.0, delay_steps=0, seed=1))

    runner._send_delta_tasks(
        network, step=0, outboxes=outboxes,
        data_budget=[CommunicationBudget(near.encoded_size_bytes), CommunicationBudget(0)],
        paths=((), ((1, 1), (1, 2), (1, 3))),
    )

    assert near_task.attempts == 1
    assert far_task.attempts == 0


def test_mismatch_triggered_full_repair_uses_only_explicit_replica_state() -> None:
    result = PSRClosedLoopRunner(
        policy=ReplicaPolicy.MISMATCH_TRIGGERED_FULL_REPAIR, config=_config(loss=0.0),
    ).run(_instance())
    assert result.network_summary["attempted_control_bytes"] > 0
    assert result.network_summary["attempted_repair_bytes"] > 0


def test_action_triggered_repair_queries_only_the_immediate_planned_edge() -> None:
    runner = PSRClosedLoopRunner(
        policy=ReplicaPolicy.ACTION_TRIGGERED_REPAIR, config=_config(loss=0.0),
    )
    assert runner._query_cells(((4, 4), (4, 5), (4, 6)), (12, 12), 0, full_replica=False, action_only=True) == ((4, 5),)
    assert runner._query_cells(((4, 4),), (12, 12), 0, full_replica=False, action_only=True) == ()
    result = runner.run(_instance())
    assert result.network_summary["attempted_control_bytes"] > 0
    assert result.network_summary["attempted_bytes"] == (
        result.network_summary["attempted_data_bytes"]
        + result.network_summary["attempted_control_bytes"]
        + result.network_summary["attempted_repair_bytes"]
    )


def test_utility_triggered_repair_uses_only_local_action_sensitivity() -> None:
    runner = PSRClosedLoopRunner(
        policy=ReplicaPolicy.UTILITY_TRIGGERED_REPAIR, config=_config(loss=0.0),
    )
    belief = BeliefMap((12, 12))
    optimistic = runner.planner.plan(runner.adapter.to_planning_map(belief), (5, 5), (5, 8)).path
    assert runner._action_is_utility_sensitive(belief, (5, 5), (5, 8), optimistic)
    result = runner.run(_instance())
    assert result.network_summary["attempted_bytes"] == (
        result.network_summary["attempted_data_bytes"]
        + result.network_summary["attempted_control_bytes"]
        + result.network_summary["attempted_repair_bytes"]
    )


def test_new_triggered_repairs_keep_ordinary_deltas_one_shot() -> None:
    update = MapUpdate.create(sender_id=0, x=1, y=1, cell_state=0, version=1, observed_at=0)
    for policy in (ReplicaPolicy.ACTION_TRIGGERED_REPAIR, ReplicaPolicy.UTILITY_TRIGGERED_REPAIR):
        runner = PSRClosedLoopRunner(policy=policy, config=_config(loss=0.0))
        task = _DeliveryTask(update, receiver_id=1)
        outboxes = [{task.key: task}, {}]
        network = UnreliableNetwork(LinkConfig(loss_probability=0.0, delay_steps=0, seed=1))
        runner._send_delta_tasks(network, step=0, outboxes=outboxes, data_budget=[CommunicationBudget(update.encoded_size_bytes), CommunicationBudget(0)])
        assert task.key not in outboxes[0]
        assert task.attempts == 1
