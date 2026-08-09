"""Closed-loop explicit-replica MAPF under a deterministic lossy channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import process_time
from typing import Iterable

import numpy as np
from pogema import GridConfig, pogema_v0

from cmvr.communication import (
    CommunicationBudget, DeltaPayload, DigestQuery, MessageKind, NetworkMessage,
    PSRConfig, PatchPayload, ReplicaPolicy, UnreliableNetwork, belief_stamp,
    full_replica_chunk, ordered_digest_peers, planning_corridor,
    path_weight, replica_digest, update_from_belief, update_stamp,
)
from cmvr.env.instance import EpisodeInstance
from cmvr.mapping import BeliefMap, DeltaEncoder, MapUpdate, PlanningMapAdapter
from cmvr.planning import AStarPlanner, Coordinate
from cmvr.utils.seeding import seed_everything


# POGEMA action convention: 0=wait, 1=up, 2=down, 3=left, 4=right.
_ACTION_BY_DELTA = {(0, 0): 0, (-1, 0): 1, (1, 0): 2, (0, -1): 3, (0, 1): 4}


def coordinate_to_action(current: Coordinate, next_coordinate: Coordinate) -> int:
    """Convert a one-cell coordinate displacement to POGEMA's action index."""
    delta = (next_coordinate[0] - current[0], next_coordinate[1] - current[1])
    try:
        return _ACTION_BY_DELTA[delta]
    except KeyError as error:
        raise ValueError(f"coordinates are not a valid one-step move: {delta}") from error


@dataclass(frozen=True)
class ReplicaStep:
    step: int
    replica_error: float
    path_repairable_error: float
    path_truth_error: float
    repair_events: int
    candidate_updates: int


@dataclass(frozen=True)
class PSRResult:
    policy: str
    episode_length: int
    completed: tuple[bool, ...]
    action_trace: tuple[tuple[int, ...], ...]
    traces: tuple[ReplicaStep, ...]
    network_summary: dict[str, int]
    mean_replica_error: float
    mean_path_repairable_error: float
    mean_path_truth_error: float
    mean_recovery_latency: float | None
    unresolved_repair_events: int
    repair_events: int
    optimistic_planning_calls: int
    pessimistic_planning_calls: int
    utility_trigger_checks: int
    utility_triggered_receivers: int
    corridor_query_receivers: int
    planning_cpu_ms: float = field(compare=False)
    utility_trigger_cpu_ms: float = field(compare=False)
    episode_cpu_ms: float = field(compare=False)

    @property
    def completion_success_rate(self) -> float:
        return sum(self.completed) / len(self.completed)

    @property
    def instance_success_rate(self) -> float:
        return float(all(self.completed))


@dataclass
class _DeliveryTask:
    update: MapUpdate
    receiver_id: int
    attempts: int = 0

    @property
    def key(self) -> tuple[str, int]:
        return self.update.update_id, self.receiver_id


class PSRClosedLoopRunner:
    """Run one explicit-replica policy on a fixed instance and link trace."""

    def __init__(self, *, policy: ReplicaPolicy, config: PSRConfig) -> None:
        self.policy = ReplicaPolicy(policy)
        self.config = config
        self.adapter = PlanningMapAdapter("optimistic")
        self.pessimistic_adapter = PlanningMapAdapter("pessimistic")
        self.planner = AStarPlanner()
        self.encoder = DeltaEncoder()
        self._optimistic_planning_calls = self._pessimistic_planning_calls = 0
        self._utility_trigger_checks = self._utility_triggered_receivers = 0
        self._corridor_query_receivers = 0
        self._planning_cpu_seconds = self._utility_trigger_cpu_seconds = 0.0

    def run(self, instance: EpisodeInstance) -> PSRResult:
        episode_start = process_time()
        self._optimistic_planning_calls = 0
        self._pessimistic_planning_calls = 0
        self._utility_trigger_checks = 0
        self._utility_triggered_receivers = 0
        self._corridor_query_receivers = 0
        self._planning_cpu_seconds = 0.0
        self._utility_trigger_cpu_seconds = 0.0
        seed_everything(instance.generation_seed)
        environment = pogema_v0(grid_config=GridConfig(
            seed=instance.generation_seed, size=instance.map_size, map=instance.obstacle_map.astype(int).tolist(),
            agents_xy=[list(value) for value in instance.starts], targets_xy=[list(value) for value in instance.goals],
            num_agents=instance.num_agents, obs_radius=instance.observation_radius,
            max_episode_steps=instance.max_episode_steps, collision_system=instance.collision_system,
        ))
        observations = environment.reset()
        beliefs = tuple(BeliefMap(instance.obstacle_map.shape) for _ in range(instance.num_agents))
        network = UnreliableNetwork(self.config.link)
        outboxes: list[dict[tuple[str, int], _DeliveryTask]] = [dict() for _ in range(instance.num_agents)]
        full_repair_outboxes: list[dict[tuple[str, int], _DeliveryTask]] = [dict() for _ in range(instance.num_agents)]
        completed = [False] * instance.num_agents
        active_repair_start: list[int | None] = [None] * instance.num_agents
        recovery_latencies: list[int] = []
        traces: list[ReplicaStep] = []
        action_trace: list[tuple[int, ...]] = []
        repair_events = 0

        for step in range(instance.max_episode_steps):
            data_budget = [CommunicationBudget(self.config.data_bytes_per_agent_per_step) for _ in beliefs]
            control_budget = [CommunicationBudget(self.config.control_bytes_per_agent_per_step) for _ in beliefs]
            repair_events += self._drain_arrivals(network, step, beliefs, outboxes, full_repair_outboxes, data_budget, control_budget)
            positions = self._positions(environment)
            local_updates = []
            for sender_id, observation in enumerate(observations):
                updates = self.encoder.observe(beliefs[sender_id], observation[0], positions[sender_id], sender_id=sender_id, step=step)
                local_updates.extend(updates)
                self._enqueue_updates(outboxes, updates, sender_id, len(beliefs))
            paths = self._paths(beliefs, positions, instance.goals)
            self._dispatch_data(network, step, beliefs, outboxes, full_repair_outboxes, data_budget, control_budget, paths, positions, instance.goals)
            repair_events += self._drain_arrivals(network, step, beliefs, outboxes, full_repair_outboxes, data_budget, control_budget)
            paths = self._paths(beliefs, positions, instance.goals)
            replica_error = self._replica_error(beliefs)
            repairable, path_truth_error = self._path_errors(beliefs, paths, instance.obstacle_map)
            for agent, error in enumerate(repairable):
                if error > 0 and active_repair_start[agent] is None:
                    active_repair_start[agent] = step
                elif error == 0 and active_repair_start[agent] is not None:
                    recovery_latencies.append(step - active_repair_start[agent])
                    active_repair_start[agent] = None
            traces.append(ReplicaStep(step, replica_error, float(np.mean(repairable)), path_truth_error, repair_events, len(local_updates)))
            actions = tuple(0 if completed[index] else self._action(paths[index], positions[index]) for index in range(instance.num_agents))
            action_trace.append(actions)
            observations, _, _, _ = environment.step(actions)
            latest = self._positions(environment)
            for index, position in enumerate(latest):
                completed[index] = completed[index] or position == instance.goals[index]
            if all(completed):
                break

        unresolved = sum(start is not None for start in active_repair_start)
        return PSRResult(
            self.policy.value, len(traces), tuple(completed), tuple(action_trace), tuple(traces), network.summary(),
            float(np.mean([trace.replica_error for trace in traces])) if traces else 0.0,
            float(np.mean([trace.path_repairable_error for trace in traces])) if traces else 0.0,
            float(np.mean([trace.path_truth_error for trace in traces])) if traces else 0.0,
            float(np.mean(recovery_latencies)) if recovery_latencies else None,
            unresolved, repair_events,
            self._optimistic_planning_calls, self._pessimistic_planning_calls,
            self._utility_trigger_checks, self._utility_triggered_receivers,
            self._corridor_query_receivers,
            self._planning_cpu_seconds * 1_000,
            self._utility_trigger_cpu_seconds * 1_000,
            (process_time() - episode_start) * 1_000,
        )

    def _enqueue_updates(self, outboxes: list[dict[tuple[str, int], _DeliveryTask]], updates: Iterable[MapUpdate], sender_id: int, agents: int) -> None:
        if self.policy is ReplicaPolicy.NO_COMMUNICATION:
            return
        for update in updates:
            for receiver_id in range(agents):
                if receiver_id != sender_id:
                    task = _DeliveryTask(update, receiver_id)
                    outboxes[sender_id][task.key] = task

    def _dispatch_data(self, network: UnreliableNetwork, step: int, beliefs: tuple[BeliefMap, ...], outboxes: list[dict[tuple[str, int], _DeliveryTask]], full_repair_outboxes: list[dict[tuple[str, int], _DeliveryTask]], data_budget: list[CommunicationBudget], control_budget: list[CommunicationBudget], paths: tuple[tuple[Coordinate, ...], ...], positions: tuple[Coordinate, ...], goals: tuple[Coordinate, ...]) -> None:
        is_periodic_sync_step = (
            self.policy is ReplicaPolicy.PERIODIC_FULL_SYNC
            and step % self.config.sync_interval_steps == 0
        )
        if self.policy in {
            ReplicaPolicy.ONE_SHOT_DELTA, ReplicaPolicy.RETRY_ALL_ARQ,
            ReplicaPolicy.FULL_REPLICA_REPAIR,
            ReplicaPolicy.PATH_WEIGHTED_ARQ, ReplicaPolicy.MISMATCH_TRIGGERED_FULL_REPAIR,
            ReplicaPolicy.ACTION_TRIGGERED_REPAIR,
            ReplicaPolicy.UTILITY_TRIGGERED_REPAIR,
        } or (self.policy is ReplicaPolicy.PERIODIC_FULL_SYNC and not is_periodic_sync_step):
            self._send_delta_tasks(network, step, outboxes, data_budget, paths)
        if is_periodic_sync_step:
            self._periodic_full_sync(network, step, beliefs, data_budget)
        if self.policy is ReplicaPolicy.PERIODIC_REGIONAL_SYNC and step % self.config.sync_interval_steps == 0:
            self._send_queries(network, step, beliefs, control_budget, paths, positions, regional_only=True)
        if self.policy is ReplicaPolicy.ACTION_TRIGGERED_REPAIR and step % self.config.repair_interval_steps == 0:
            self._send_queries(network, step, beliefs, control_budget, paths, positions, regional_only=False, action_only=True)
        if self.policy is ReplicaPolicy.UTILITY_TRIGGERED_REPAIR and step % self.config.repair_interval_steps == 0:
            self._send_queries(network, step, beliefs, control_budget, paths, positions, regional_only=False, utility_triggered=True, goals=goals)
        if self.policy is ReplicaPolicy.FULL_REPLICA_REPAIR and step % self.config.repair_interval_steps == 0:
            self._send_queries(network, step, beliefs, control_budget, paths, positions, regional_only=False, full_replica=True)
        if self.policy is ReplicaPolicy.MISMATCH_TRIGGERED_FULL_REPAIR and step % self.config.repair_interval_steps == 0:
            self._send_replica_digests(network, step, beliefs, control_budget, positions)
            self._send_full_repair_tasks(network, step, full_repair_outboxes, data_budget)

    def _send_delta_tasks(self, network: UnreliableNetwork, step: int, outboxes: list[dict[tuple[str, int], _DeliveryTask]], data_budget: list[CommunicationBudget], paths: tuple[tuple[Coordinate, ...], ...] | None = None) -> None:
        for sender_id, outbox in enumerate(outboxes):
            tasks = list(outbox.items())
            if self.policy is ReplicaPolicy.RETRY_ALL_ARQ:
                tasks = self._interleave_first_attempts_and_retries(tasks, step)
            elif self.policy is ReplicaPolicy.PATH_WEIGHTED_ARQ:
                if paths is None:
                    raise ValueError("Path-Weighted ARQ requires receiver-local paths")
                tasks.sort(key=lambda item: (
                    -path_weight(
                        (item[1].update.x, item[1].update.y), paths[item[1].receiver_id],
                        sigma=self.config.path_weighted_sigma,
                    ),
                    item[1].attempts, item[1].update.observed_at, item[1].update.x,
                    item[1].update.y, item[1].receiver_id,
                ))
            else:
                tasks.sort(key=lambda item: (
                    item[1].update.observed_at, item[1].update.x, item[1].update.y,
                    item[1].receiver_id,
                ))
            for key, task in tasks:
                attempt = task.attempts
                message = network.make_message(
                    MessageKind.DELTA, sender_id, task.receiver_id,
                    DeltaPayload(task.update, key if self.policy in {ReplicaPolicy.RETRY_ALL_ARQ, ReplicaPolicy.PATH_WEIGHTED_ARQ} else None),
                    task.update.encoded_size_bytes, step, category="data",
                    link_key=f"delta|{task.update.update_id}|{task.receiver_id}|{attempt}",
                    is_retransmission=attempt > 0,
                )
                if not self._try_send(network, message, step, data_budget[sender_id]):
                    continue
                task.attempts += 1
                if self.policy in {
                    ReplicaPolicy.ONE_SHOT_DELTA,
                    ReplicaPolicy.PERIODIC_FULL_SYNC,
                    ReplicaPolicy.FULL_REPLICA_REPAIR, ReplicaPolicy.MISMATCH_TRIGGERED_FULL_REPAIR,
                    ReplicaPolicy.ACTION_TRIGGERED_REPAIR, ReplicaPolicy.UTILITY_TRIGGERED_REPAIR,
                }:
                    outbox.pop(key, None)

    @staticmethod
    def _interleave_first_attempts_and_retries(
        tasks: list[tuple[tuple[str, int], _DeliveryTask]], step: int,
    ) -> list[tuple[tuple[str, int], _DeliveryTask]]:
        """Schedule Retry-All fairly under a small data cap.

        A timestamp-only queue starves fresh observations after an old loss.
        A first-attempt-only queue starves every retry while local discovery
        continues.  Alternate those two classes and use attempt count within
        the retry class, so neither behavior is hidden by the scheduler.
        """
        key = lambda item: (
            item[1].attempts, item[1].update.observed_at, item[1].update.x,
            item[1].update.y, item[1].receiver_id,
        )
        fresh = sorted((item for item in tasks if item[1].attempts == 0), key=key)
        retries = sorted((item for item in tasks if item[1].attempts > 0), key=key)
        primary, secondary = (fresh, retries) if step % 2 == 0 else (retries, fresh)
        ordered: list[tuple[tuple[str, int], _DeliveryTask]] = []
        while primary or secondary:
            if primary:
                ordered.append(primary.pop(0))
            if secondary:
                ordered.append(secondary.pop(0))
        return ordered

    def _periodic_full_sync(
        self, network: UnreliableNetwork, step: int, beliefs: tuple[BeliefMap, ...],
        data_budget: list[CommunicationBudget],
    ) -> None:
        """Send a budget-bounded, fair chunk of every known replica.

        This is the conventional anti-entropy control: it has no mismatch,
        path, or action test.  On each K-step sync round it replaces ordinary
        delta traffic with a full-replica chunk under the exact same sender
        data cap.  The deterministic round rotates both cells and peers, so a
        small cap cannot silently starve high-index receivers or later cells.
        """
        sync_round = step // self.config.sync_interval_steps
        for sender_id, belief in enumerate(beliefs):
            updates = tuple(
                item for x in range(belief.shape[0]) for y in range(belief.shape[1])
                if (item := update_from_belief(belief, (x, y))) is not None
            )
            receivers = tuple(receiver_id for receiver_id in range(len(beliefs)) if receiver_id != sender_id)
            if not updates or not receivers:
                continue
            messages_per_round = data_budget[sender_id].remaining_bytes // updates[0].encoded_size_bytes
            cells_per_receiver = max(1, messages_per_round // len(receivers))
            cell_start = (sync_round * cells_per_receiver) % len(updates)
            receiver_start = sync_round % len(receivers)
            for cell_offset in range(cells_per_receiver):
                update = updates[(cell_start + cell_offset) % len(updates)]
                for receiver_offset in range(len(receivers)):
                    receiver_id = receivers[(receiver_start + receiver_offset) % len(receivers)]
                    message = network.make_message(
                        MessageKind.DELTA, sender_id, receiver_id,
                        DeltaPayload(update, is_repair=True), update.encoded_size_bytes,
                        step, category="repair",
                        link_key=f"periodic-full|{sync_round}|{update.update_id}|{receiver_id}",
                    )
                    if not self._try_send(network, message, step, data_budget[sender_id]):
                        break
                else:
                    continue
                break

    def _send_queries(
        self, network: UnreliableNetwork, step: int, beliefs: tuple[BeliefMap, ...],
        control_budget: list[CommunicationBudget], paths: tuple[tuple[Coordinate, ...], ...],
        positions: tuple[Coordinate, ...], *, regional_only: bool, full_replica: bool = False,
        action_only: bool = False, utility_triggered: bool = False,
        goals: tuple[Coordinate, ...] | None = None,
    ) -> None:
        for requester_id, path in enumerate(paths):
            if utility_triggered and (goals is None or not self._action_is_utility_sensitive(
                beliefs[requester_id], positions[requester_id], goals[requester_id], path,
            )):
                continue
            if utility_triggered:
                self._utility_triggered_receivers += 1
            if not regional_only and not full_replica:
                self._corridor_query_receivers += 1
            cells = self._query_cells(path, beliefs[requester_id].shape, step, full_replica=full_replica, action_only=action_only)
            if not cells:
                continue
            payload = DigestQuery(cells, tuple(belief_stamp(beliefs[requester_id], cell) for cell in cells), regional_only, action_only)
            byte_size = self.config.digest_base_bytes + self.config.digest_entry_bytes * len(cells)
            # A bounded control plane uses deterministic round-robin gossip,
            # rather than permanently preferring low-index peers when a digest
            # budget cannot cover every teammate in one round.
            phase = step // (self.config.sync_interval_steps if regional_only else self.config.repair_interval_steps)
            for peer_id in ordered_digest_peers(
                requester_id=requester_id, positions=positions, phase=phase,
                limit=self.config.max_digest_peers,
            ):
                message = network.make_message(MessageKind.DIGEST_QUERY, requester_id, peer_id, payload, byte_size, step, category="control", link_key=f"digest|{step}|{requester_id}|{peer_id}|{regional_only}|{action_only}|{cells}")
                self._try_send(network, message, step, control_budget[requester_id])

    def _send_replica_digests(
        self, network: UnreliableNetwork, step: int, beliefs: tuple[BeliefMap, ...],
        control_budget: list[CommunicationBudget], positions: tuple[Coordinate, ...],
    ) -> None:
        """Ask a nearest peer whether the complete explicit replica differs."""
        phase = step // self.config.repair_interval_steps
        for requester_id, belief in enumerate(beliefs):
            payload = replica_digest(belief)
            for peer_id in ordered_digest_peers(
                requester_id=requester_id, positions=positions, phase=phase,
                limit=self.config.max_digest_peers,
            ):
                message = network.make_message(
                    MessageKind.REPLICA_DIGEST, requester_id, peer_id, payload,
                    self.config.replica_digest_bytes, step, category="control",
                    link_key=f"replica-digest|{step}|{requester_id}|{peer_id}|{payload.digest}",
                )
                self._try_send(network, message, step, control_budget[requester_id])

    def _send_full_repair_tasks(
        self, network: UnreliableNetwork, step: int,
        full_repair_outboxes: list[dict[tuple[str, int], _DeliveryTask]],
        data_budget: list[CommunicationBudget],
    ) -> None:
        """Send queued full-replica state only after a received mismatch digest."""
        for sender_id, outbox in enumerate(full_repair_outboxes):
            tasks = sorted(outbox.items(), key=lambda item: (
                item[1].update.observed_at, item[1].update.x, item[1].update.y,
                item[1].receiver_id,
            ))
            for key, task in tasks:
                message = network.make_message(
                    MessageKind.DELTA, sender_id, task.receiver_id,
                    DeltaPayload(task.update, is_repair=True), task.update.encoded_size_bytes,
                    step, category="repair",
                    link_key=f"mismatch-full|{task.update.update_id}|{task.receiver_id}|{task.attempts}",
                )
                if not self._try_send(network, message, step, data_budget[sender_id]):
                    continue
                task.attempts += 1
                outbox.pop(key, None)

    @staticmethod
    def _enqueue_full_replica(
        outboxes: list[dict[tuple[str, int], _DeliveryTask]], belief: BeliefMap,
        sender_id: int, receiver_id: int,
    ) -> None:
        for x in range(belief.shape[0]):
            for y in range(belief.shape[1]):
                update = update_from_belief(belief, (x, y))
                if update is not None:
                    task = _DeliveryTask(update, receiver_id)
                    outboxes[sender_id][task.key] = task

    def _drain_arrivals(self, network: UnreliableNetwork, step: int, beliefs: tuple[BeliefMap, ...], outboxes: list[dict[tuple[str, int], _DeliveryTask]], full_repair_outboxes: list[dict[tuple[str, int], _DeliveryTask]], data_budget: list[CommunicationBudget], control_budget: list[CommunicationBudget]) -> int:
        repair_events = 0
        while True:
            arrived = network.receive(step)
            if not arrived:
                return repair_events
            for message in arrived:
                repair_events += self._handle_message(network, message, step, beliefs, outboxes, full_repair_outboxes, data_budget, control_budget)

    def _handle_message(self, network: UnreliableNetwork, message: NetworkMessage, step: int, beliefs: tuple[BeliefMap, ...], outboxes: list[dict[tuple[str, int], _DeliveryTask]], full_repair_outboxes: list[dict[tuple[str, int], _DeliveryTask]], data_budget: list[CommunicationBudget], control_budget: list[CommunicationBudget]) -> int:
        if message.kind is MessageKind.DELTA:
            payload = message.payload
            assert isinstance(payload, DeltaPayload)
            applied = beliefs[message.receiver_id].apply_update(payload.update)
            if payload.task_key is not None:
                ack = network.make_message(MessageKind.ACK, message.receiver_id, message.sender_id, payload.task_key, self.config.ack_bytes, step, category="control", link_key=f"ack|{payload.task_key}|{message.message_id}")
                self._try_send(network, ack, step, control_budget[message.receiver_id])
            return int(payload.is_repair and applied)
        if message.kind is MessageKind.ACK:
            if isinstance(message.payload, tuple):
                outboxes[message.receiver_id].pop(message.payload, None)
            return 0
        if message.kind is MessageKind.DIGEST_QUERY:
            payload = message.payload
            assert isinstance(payload, DigestQuery)
            source_belief = beliefs[message.receiver_id]
            patch = []
            for cell, requester_stamp in zip(payload.cells, payload.requester_stamps):
                update = update_from_belief(source_belief, cell)
                if update is not None and (payload.regional_only or update_stamp(update) > requester_stamp):
                    patch.append(update)
            if patch:
                response = network.make_message(MessageKind.PATCH, message.receiver_id, message.sender_id, PatchPayload(tuple(patch)), self.config.patch_base_bytes + sum(update.encoded_size_bytes for update in patch), step, category="repair", link_key=f"patch|{step}|{message.receiver_id}|{message.sender_id}|{tuple(update.update_id for update in patch)}")
                self._try_send(network, response, step, data_budget[message.receiver_id])
            return 0
        if message.kind is MessageKind.REPLICA_DIGEST:
            payload = message.payload
            if payload != replica_digest(beliefs[message.receiver_id]):
                self._enqueue_full_replica(
                    full_repair_outboxes, beliefs[message.receiver_id],
                    sender_id=message.receiver_id, receiver_id=message.sender_id,
                )
            return 0
        if message.kind is MessageKind.PATCH:
            payload = message.payload
            assert isinstance(payload, PatchPayload)
            applied = sum(beliefs[message.receiver_id].apply_update(update) for update in payload.updates)
            return int(applied > 0)
        raise ValueError(f"unsupported message kind: {message.kind}")

    @staticmethod
    def _try_send(network: UnreliableNetwork, message: NetworkMessage, step: int, budget: CommunicationBudget) -> bool:
        if not budget.can_spend(message.byte_size):
            network.defer(message, step)
            return False
        budget.spend(message.byte_size)
        network.send(message, step)
        return True

    def _paths(self, beliefs: tuple[BeliefMap, ...], positions: tuple[Coordinate, ...], goals: tuple[Coordinate, ...]) -> tuple[tuple[Coordinate, ...], ...]:
        started = process_time()
        paths = tuple(self.planner.plan(self.adapter.to_planning_map(belief), positions[index], goals[index]).path for index, belief in enumerate(beliefs))
        self._optimistic_planning_calls += len(beliefs)
        self._planning_cpu_seconds += process_time() - started
        return paths

    def _action_is_utility_sensitive(
        self, belief: BeliefMap, position: Coordinate, goal: Coordinate, optimistic_path: tuple[Coordinate, ...],
    ) -> bool:
        """Binary local expected-utility proxy: unknown state changes next action.

        This takes no truth-map or peer-map input. A query is worthwhile only
        when treating unobserved cells as blocked changes the receiver's next
        fixed-A* action versus its operational optimistic plan.
        """
        self._utility_trigger_checks += 1
        started = process_time()
        pessimistic_path = self.planner.plan(self.pessimistic_adapter.to_planning_map(belief), position, goal).path
        elapsed = process_time() - started
        self._pessimistic_planning_calls += 1
        self._planning_cpu_seconds += elapsed
        self._utility_trigger_cpu_seconds += elapsed
        return self._action(optimistic_path, position) != self._action(pessimistic_path, position)

    @staticmethod
    def _action(path: tuple[Coordinate, ...], position: Coordinate) -> int:
        return coordinate_to_action(position, path[1]) if len(path) > 1 else 0

    def _query_cells(
        self, path: tuple[Coordinate, ...], shape: tuple[int, int], step: int, *, full_replica: bool,
        action_only: bool = False,
    ) -> tuple[Coordinate, ...]:
        if full_replica:
            phase = step // self.config.repair_interval_steps
            return full_replica_chunk(
                shape, max_cells=self.config.max_digest_cells_per_message(), phase=phase,
            )
        if action_only:
            return path[1:2]
        return planning_corridor(
            path, shape, horizon=self.config.corridor_horizon, radius=self.config.corridor_radius,
        )

    @staticmethod
    def _positions(environment) -> tuple[Coordinate, ...]:
        return tuple(tuple(map(int, item)) for item in environment.grid.get_agents_xy(ignore_borders=True))

    @staticmethod
    def _replica_error(beliefs: tuple[BeliefMap, ...]) -> float:
        if len(beliefs) < 2:
            return 0.0
        total = disagreements = 0
        for left in range(len(beliefs)):
            for right in range(left + 1, len(beliefs)):
                a, b = beliefs[left], beliefs[right]
                unequal = (a.occupancy != b.occupancy) | (a.versions != b.versions) | (a.last_observed_step != b.last_observed_step) | (a.source_ids != b.source_ids)
                disagreements += int(unequal.sum())
                total += unequal.size
        return disagreements / total if total else 0.0

    def _path_errors(self, beliefs: tuple[BeliefMap, ...], paths: tuple[tuple[Coordinate, ...], ...], true_map: np.ndarray) -> tuple[list[float], float]:
        repairable, truth_errors = [], []
        for receiver, path in enumerate(paths):
            cells = planning_corridor(
                path, beliefs[receiver].shape, horizon=self.config.corridor_horizon,
                radius=self.config.corridor_radius,
            )
            if not cells:
                repairable.append(0.0); truth_errors.append(0.0); continue
            newer = truth_wrong = 0
            for cell in cells:
                own_stamp = belief_stamp(beliefs[receiver], cell)
                newer += any(belief_stamp(beliefs[peer], cell) > own_stamp for peer in range(len(beliefs)) if peer != receiver)
                observed = int(beliefs[receiver].occupancy[cell])
                truth_wrong += observed < 0 or observed != int(true_map[cell])
            repairable.append(newer / len(cells))
            truth_errors.append(truth_wrong / len(cells))
        return repairable, float(np.mean(truth_errors))
