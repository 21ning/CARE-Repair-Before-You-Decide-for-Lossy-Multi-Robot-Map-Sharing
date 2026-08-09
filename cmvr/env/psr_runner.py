"""Closed-loop explicit-replica MAPF under a deterministic lossy channel."""

from __future__ import annotations

from dataclasses import dataclass, field
from time import process_time
from typing import Callable, Iterable

import numpy as np
from pogema import GridConfig, pogema_v0

from cmvr.communication import (
    ACK_BYTES, DIGEST_ENTRY_BYTES, DIGEST_HEADER_BYTES, DecisionRepairPlan,
    PATCH_HEADER_BYTES, REPLICA_DIGEST_BYTES, CommunicationBudget, DeltaPayload,
    DigestQuery, MessageKind, NetworkMessage, PSRConfig, PatchPayload,
    ReplicaPolicy, UnreliableNetwork, ack_token, belief_stamp, decode_ack,
    ScenarioCertificate, deadline_decision_repair_plan, decision_candidate_cells,
    decode_delta, decode_digest_query, decode_patch, decode_replica_digest,
    encode_ack, encode_delta, encode_digest_query, encode_patch,
    encode_replica_digest, full_replica_chunk, minimum_scenario_certificate,
    ordered_digest_peers, planning_corridor, path_weight, replica_digest,
    scenario_blocked_sets, update_from_belief,
    update_stamp,
)
from cmvr.env.instance import EpisodeInstance, critical_decision_pairs
from cmvr.mapping import BeliefMap, DeltaEncoder, MapUpdate, PlanningMapAdapter
from cmvr.planning import Coordinate, Planner, make_planner
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
    planner: str
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
    deadline_trigger_checks: int
    deadline_ambiguous_receivers: int
    deadline_feasible_receivers: int
    deadline_infeasible_receivers: int
    deadline_query_cells: int
    mean_decision_slack: float | None
    certificate_checks: int
    certificate_scenario_planning_calls: int
    certificate_conflicting_pairs: int
    certificate_feasible_pairs: int
    certificate_infeasible_pairs: int
    certificate_candidate_cells: int
    certificate_query_cells: int
    certificate_candidate_cap_checks: int
    certificate_candidate_cap_hits: int
    certificate_candidate_cap_hit_rate: float
    mean_uncapped_certificate_candidates: float
    critical_pair_count: int
    critical_peer_observation_events: int
    critical_self_observation_events: int
    critical_route_commitment_events: int
    mean_critical_peer_observation_step: float | None
    mean_critical_self_observation_step: float | None
    mean_route_commitment_step: float | None
    mean_visibility_gap_steps: float | None
    mean_usable_communication_window_steps: float | None
    decision_before_self_observation_rate: float | None
    planning_cpu_ms: float = field(compare=False)
    utility_trigger_cpu_ms: float = field(compare=False)
    certificate_cpu_ms: float = field(compare=False)
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

    def __init__(
        self, *, policy: ReplicaPolicy, config: PSRConfig,
        planner: str = "astar",
        step_observer: Callable[
            [int, tuple[BeliefMap, ...], tuple[Coordinate, ...]], None
        ] | None = None,
    ) -> None:
        self.policy = ReplicaPolicy(policy)
        self.config = config
        expected_wire_sizes = (
            DIGEST_HEADER_BYTES, DIGEST_ENTRY_BYTES, ACK_BYTES,
            PATCH_HEADER_BYTES, REPLICA_DIGEST_BYTES,
        )
        configured_wire_sizes = (
            config.digest_base_bytes, config.digest_entry_bytes, config.ack_bytes,
            config.patch_base_bytes, config.replica_digest_bytes,
        )
        if configured_wire_sizes != expected_wire_sizes:
            raise ValueError(
                "PSRConfig packet sizes must match the canonical wire codec: "
                f"configured={configured_wire_sizes}, expected={expected_wire_sizes}"
            )
        self.step_observer = step_observer
        self.planner_name = planner
        self.adapter = PlanningMapAdapter("optimistic")
        self.pessimistic_adapter = PlanningMapAdapter("pessimistic")
        self.planner = make_planner(planner)
        self._optimistic_planners: list[Planner] = []
        self._pessimistic_planners: list[Planner] = []
        self.encoder = DeltaEncoder()
        self._optimistic_planning_calls = self._pessimistic_planning_calls = 0
        self._utility_trigger_checks = self._utility_triggered_receivers = 0
        self._corridor_query_receivers = 0
        self._deadline_trigger_checks = self._deadline_ambiguous_receivers = 0
        self._deadline_feasible_receivers = self._deadline_infeasible_receivers = 0
        self._deadline_query_cells = 0
        self._decision_slacks: list[int] = []
        self._certificate_checks = self._certificate_scenario_planning_calls = 0
        self._certificate_conflicting_pairs = self._certificate_feasible_pairs = 0
        self._certificate_infeasible_pairs = self._certificate_candidate_cells = 0
        self._certificate_query_cells = 0
        self._certificate_candidate_cap_checks = self._certificate_candidate_cap_hits = 0
        self._certificate_uncapped_candidate_cells = 0
        self._planning_cpu_seconds = self._utility_trigger_cpu_seconds = 0.0
        self._certificate_cpu_seconds = 0.0

    def run(self, instance: EpisodeInstance) -> PSRResult:
        if instance.map_size > 64:
            raise ValueError("canonical digest codec supports maps up to 64x64")
        if instance.num_agents > 63:
            raise ValueError("canonical digest codec supports at most 63 agents")
        if instance.max_episode_steps > 65_535:
            raise ValueError("canonical digest codec supports at most 65,535 episode steps")
        episode_start = process_time()
        self._optimistic_planning_calls = 0
        self._pessimistic_planning_calls = 0
        self._utility_trigger_checks = 0
        self._utility_triggered_receivers = 0
        self._corridor_query_receivers = 0
        self._deadline_trigger_checks = self._deadline_ambiguous_receivers = 0
        self._deadline_feasible_receivers = self._deadline_infeasible_receivers = 0
        self._deadline_query_cells = 0
        self._decision_slacks = []
        self._certificate_checks = self._certificate_scenario_planning_calls = 0
        self._certificate_conflicting_pairs = self._certificate_feasible_pairs = 0
        self._certificate_infeasible_pairs = self._certificate_candidate_cells = 0
        self._certificate_query_cells = 0
        self._certificate_candidate_cap_checks = self._certificate_candidate_cap_hits = 0
        self._certificate_uncapped_candidate_cells = 0
        self._planning_cpu_seconds = 0.0
        self._utility_trigger_cpu_seconds = 0.0
        self._certificate_cpu_seconds = 0.0
        seed_everything(instance.generation_seed)
        environment = pogema_v0(grid_config=GridConfig(
            seed=instance.generation_seed, size=instance.map_size, map=instance.obstacle_map.astype(int).tolist(),
            agents_xy=[list(value) for value in instance.starts], targets_xy=[list(value) for value in instance.goals],
            num_agents=instance.num_agents, obs_radius=instance.observation_radius,
            max_episode_steps=instance.max_episode_steps, collision_system=instance.collision_system,
        ))
        observations = environment.reset()
        beliefs = tuple(BeliefMap(instance.obstacle_map.shape) for _ in range(instance.num_agents))
        self._optimistic_planners = [make_planner(self.planner_name) for _ in beliefs]
        self._pessimistic_planners = [make_planner(self.planner_name) for _ in beliefs]
        network = UnreliableNetwork(self.config.link)
        outboxes: list[dict[tuple[str, int], _DeliveryTask]] = [dict() for _ in range(instance.num_agents)]
        full_repair_outboxes: list[dict[tuple[str, int], _DeliveryTask]] = [dict() for _ in range(instance.num_agents)]
        completed = [False] * instance.num_agents
        active_repair_start: list[int | None] = [None] * instance.num_agents
        recovery_latencies: list[int] = []
        traces: list[ReplicaStep] = []
        action_trace: list[tuple[int, ...]] = []
        repair_events = 0
        critical_pairs = critical_decision_pairs(instance)
        peer_observation_steps: list[int | None] = [None] * len(critical_pairs)
        self_observation_steps: list[int | None] = [None] * len(critical_pairs)
        route_commitment_steps: list[int | None] = [None] * len(critical_pairs)

        for step in range(instance.max_episode_steps):
            data_budget = [CommunicationBudget(self.config.data_bytes_per_agent_per_step) for _ in beliefs]
            control_budget = [CommunicationBudget(self.config.control_bytes_per_agent_per_step) for _ in beliefs]
            repair_events += self._drain_arrivals(network, step, beliefs, outboxes, full_repair_outboxes, data_budget, control_budget)
            positions = self._positions(environment)
            for pair_index, pair in enumerate(critical_pairs):
                if peer_observation_steps[pair_index] is None and self._sensor_contains(
                    positions[pair.observer_id], pair.obstacle, instance.observation_radius,
                ):
                    peer_observation_steps[pair_index] = step
                if self_observation_steps[pair_index] is None and self._sensor_contains(
                    positions[pair.seeker_id], pair.obstacle, instance.observation_radius,
                ):
                    self_observation_steps[pair_index] = step
            local_updates = []
            for sender_id, observation in enumerate(observations):
                updates = self.encoder.observe(beliefs[sender_id], observation[0], positions[sender_id], sender_id=sender_id, step=step)
                local_updates.extend(updates)
                self._enqueue_updates(outboxes, updates, sender_id, len(beliefs))
            paths = self._paths(beliefs, positions, instance.goals)
            self._dispatch_data(network, step, beliefs, outboxes, full_repair_outboxes, data_budget, control_budget, paths, positions, instance.goals)
            repair_events += self._drain_arrivals(network, step, beliefs, outboxes, full_repair_outboxes, data_budget, control_budget)
            if self.step_observer is not None:
                self.step_observer(step, tuple(belief.clone() for belief in beliefs), positions)
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
            for pair_index, pair in enumerate(critical_pairs):
                if (
                    route_commitment_steps[pair_index] is None
                    and positions[pair.seeker_id] == pair.commitment
                    and actions[pair.seeker_id] != 0
                ):
                    route_commitment_steps[pair_index] = step
            action_trace.append(actions)
            observations, _, _, _ = environment.step(actions)
            latest = self._positions(environment)
            for index, position in enumerate(latest):
                completed[index] = completed[index] or position == instance.goals[index]
            if all(completed):
                break

        unresolved = sum(start is not None for start in active_repair_start)
        observed_peer = [value for value in peer_observation_steps if value is not None]
        observed_self = [value for value in self_observation_steps if value is not None]
        commitments = [value for value in route_commitment_steps if value is not None]
        visibility_gaps = [
            self_step - peer_step
            for peer_step, self_step in zip(peer_observation_steps, self_observation_steps)
            if peer_step is not None and self_step is not None
        ]
        usable_windows = [
            commitment - peer_step - 2 * self.config.link.delay_steps
            for peer_step, commitment in zip(peer_observation_steps, route_commitment_steps)
            if peer_step is not None and commitment is not None
        ]
        decision_before_self = [
            float(commitment < self_step)
            for commitment, self_step in zip(route_commitment_steps, self_observation_steps)
            if commitment is not None and self_step is not None
        ]
        return PSRResult(
            self.policy.value, self.planner_name, len(traces), tuple(completed), tuple(action_trace), tuple(traces), network.summary(),
            float(np.mean([trace.replica_error for trace in traces])) if traces else 0.0,
            float(np.mean([trace.path_repairable_error for trace in traces])) if traces else 0.0,
            float(np.mean([trace.path_truth_error for trace in traces])) if traces else 0.0,
            float(np.mean(recovery_latencies)) if recovery_latencies else None,
            unresolved, repair_events,
            self._optimistic_planning_calls, self._pessimistic_planning_calls,
            self._utility_trigger_checks, self._utility_triggered_receivers,
            self._corridor_query_receivers,
            self._deadline_trigger_checks, self._deadline_ambiguous_receivers,
            self._deadline_feasible_receivers, self._deadline_infeasible_receivers,
            self._deadline_query_cells,
            float(np.mean(self._decision_slacks)) if self._decision_slacks else None,
            self._certificate_checks, self._certificate_scenario_planning_calls,
            self._certificate_conflicting_pairs, self._certificate_feasible_pairs,
            self._certificate_infeasible_pairs, self._certificate_candidate_cells,
            self._certificate_query_cells,
            self._certificate_candidate_cap_checks,
            self._certificate_candidate_cap_hits,
            (
                self._certificate_candidate_cap_hits / self._certificate_candidate_cap_checks
                if self._certificate_candidate_cap_checks else 0.0
            ),
            (
                self._certificate_uncapped_candidate_cells / self._certificate_candidate_cap_checks
                if self._certificate_candidate_cap_checks else 0.0
            ),
            len(critical_pairs), len(observed_peer), len(observed_self), len(commitments),
            float(np.mean(observed_peer)) if observed_peer else None,
            float(np.mean(observed_self)) if observed_self else None,
            float(np.mean(commitments)) if commitments else None,
            float(np.mean(visibility_gaps)) if visibility_gaps else None,
            float(np.mean(usable_windows)) if usable_windows else None,
            float(np.mean(decision_before_self)) if decision_before_self else None,
            self._planning_cpu_seconds * 1_000,
            self._utility_trigger_cpu_seconds * 1_000,
            self._certificate_cpu_seconds * 1_000,
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
            ReplicaPolicy.DEADLINE_AWARE_REPAIR,
            ReplicaPolicy.CERTIFICATE_REPAIR,
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
        if self.policy is ReplicaPolicy.DEADLINE_AWARE_REPAIR and step % self.config.repair_interval_steps == 0:
            self._send_queries(network, step, beliefs, control_budget, paths, positions, regional_only=False, deadline_aware=True, goals=goals)
        if self.policy is ReplicaPolicy.CERTIFICATE_REPAIR and step % self.config.repair_interval_steps == 0:
            self._send_queries(network, step, beliefs, control_budget, paths, positions, regional_only=False, certificate_triggered=True, goals=goals)
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
                payload = DeltaPayload(
                    task.update,
                    key if self.policy in {
                        ReplicaPolicy.RETRY_ALL_ARQ, ReplicaPolicy.PATH_WEIGHTED_ARQ,
                    } else None,
                )
                encoded = encode_delta(payload, receiver_id=task.receiver_id)
                message = network.make_message(
                    MessageKind.DELTA, sender_id, task.receiver_id,
                    encoded, len(encoded), step, category="data",
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
                    ReplicaPolicy.DEADLINE_AWARE_REPAIR,
                    ReplicaPolicy.CERTIFICATE_REPAIR,
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
                    encoded = encode_delta(
                        DeltaPayload(update, is_repair=True), receiver_id=receiver_id,
                    )
                    message = network.make_message(
                        MessageKind.DELTA, sender_id, receiver_id,
                        encoded, len(encoded),
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
        deadline_aware: bool = False,
        certificate_triggered: bool = False,
        goals: tuple[Coordinate, ...] | None = None,
    ) -> None:
        for requester_id, path in enumerate(paths):
            if utility_triggered and (goals is None or not self._action_is_utility_sensitive(
                beliefs[requester_id], positions[requester_id], goals[requester_id], path,
                requester_id=requester_id,
            )):
                continue
            if utility_triggered:
                self._utility_triggered_receivers += 1
            deadline_plan = None
            if deadline_aware:
                if goals is None:
                    raise ValueError("deadline-aware repair requires receiver goals")
                deadline_plan = self._deadline_plan(
                    beliefs[requester_id], positions[requester_id],
                    goals[requester_id], path, requester_id,
                )
                if not deadline_plan.cells:
                    continue
            certificate = None
            if certificate_triggered:
                if goals is None:
                    raise ValueError("certificate repair requires receiver goals")
                certificate = self._certificate_plan(
                    beliefs[requester_id], positions[requester_id],
                    goals[requester_id], path, requester_id,
                )
                if not certificate.cells:
                    continue
            if not regional_only and not full_replica:
                self._corridor_query_receivers += 1
            if deadline_plan is not None:
                cells = deadline_plan.cells
            elif certificate is not None:
                cells = certificate.cells
            else:
                cells = self._query_cells(
                    path, beliefs[requester_id].shape, step,
                    full_replica=full_replica, action_only=action_only,
                )
            if not cells:
                continue
            payload = DigestQuery(cells, tuple(belief_stamp(beliefs[requester_id], cell) for cell in cells), regional_only, action_only)
            encoded = encode_digest_query(payload)
            # A bounded control plane uses deterministic round-robin gossip,
            # rather than permanently preferring low-index peers when a digest
            # budget cannot cover every teammate in one round.
            phase = step // (self.config.sync_interval_steps if regional_only else self.config.repair_interval_steps)
            for peer_id in ordered_digest_peers(
                requester_id=requester_id, positions=positions, phase=phase,
                limit=self.config.max_digest_peers,
            ):
                message = network.make_message(MessageKind.DIGEST_QUERY, requester_id, peer_id, encoded, len(encoded), step, category="control", link_key=f"digest|{step}|{requester_id}|{peer_id}|{regional_only}|{action_only}|{cells}")
                self._try_send(network, message, step, control_budget[requester_id])

    def _send_replica_digests(
        self, network: UnreliableNetwork, step: int, beliefs: tuple[BeliefMap, ...],
        control_budget: list[CommunicationBudget], positions: tuple[Coordinate, ...],
    ) -> None:
        """Ask a nearest peer whether the complete explicit replica differs."""
        phase = step // self.config.repair_interval_steps
        for requester_id, belief in enumerate(beliefs):
            payload = replica_digest(belief)
            encoded = encode_replica_digest(payload)
            for peer_id in ordered_digest_peers(
                requester_id=requester_id, positions=positions, phase=phase,
                limit=self.config.max_digest_peers,
            ):
                message = network.make_message(
                    MessageKind.REPLICA_DIGEST, requester_id, peer_id, encoded,
                    len(encoded), step, category="control",
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
                encoded = encode_delta(
                    DeltaPayload(task.update, is_repair=True), receiver_id=task.receiver_id,
                )
                message = network.make_message(
                    MessageKind.DELTA, sender_id, task.receiver_id,
                    encoded, len(encoded),
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
            payload = decode_delta(message.payload, receiver_id=message.receiver_id)
            applied = beliefs[message.receiver_id].apply_update(payload.update)
            if payload.task_key is not None:
                encoded = encode_ack(payload.task_key)
                ack = network.make_message(MessageKind.ACK, message.receiver_id, message.sender_id, encoded, len(encoded), step, category="control", link_key=f"ack|{payload.task_key}|{message.message_id}")
                self._try_send(network, ack, step, control_budget[message.receiver_id])
            return int(payload.is_repair and applied)
        if message.kind is MessageKind.ACK:
            token = decode_ack(message.payload)
            matches = [
                key for key in outboxes[message.receiver_id]
                if ack_token(key) == token
            ]
            if len(matches) > 1:
                raise RuntimeError("64-bit ACK token collision in active outbox")
            if matches:
                outboxes[message.receiver_id].pop(matches[0], None)
            return 0
        if message.kind is MessageKind.DIGEST_QUERY:
            payload = decode_digest_query(message.payload)
            source_belief = beliefs[message.receiver_id]
            patch = []
            for cell, requester_stamp in zip(payload.cells, payload.requester_stamps):
                update = update_from_belief(source_belief, cell)
                if update is not None and (payload.regional_only or update_stamp(update) > requester_stamp):
                    patch.append(update)
            if patch:
                encoded = encode_patch(PatchPayload(tuple(patch)))
                response = network.make_message(MessageKind.PATCH, message.receiver_id, message.sender_id, encoded, len(encoded), step, category="repair", link_key=f"patch|{step}|{message.receiver_id}|{message.sender_id}|{tuple(update.update_id for update in patch)}")
                self._try_send(network, response, step, data_budget[message.receiver_id])
            return 0
        if message.kind is MessageKind.REPLICA_DIGEST:
            payload = decode_replica_digest(message.payload)
            if payload != encode_replica_digest(replica_digest(beliefs[message.receiver_id])):
                self._enqueue_full_replica(
                    full_repair_outboxes, beliefs[message.receiver_id],
                    sender_id=message.receiver_id, receiver_id=message.sender_id,
                )
            return 0
        if message.kind is MessageKind.PATCH:
            payload = decode_patch(message.payload)
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
        planners = self._optimistic_planners or [self.planner] * len(beliefs)
        paths = tuple(planners[index].plan(self.adapter.to_planning_map(belief), positions[index], goals[index]).path for index, belief in enumerate(beliefs))
        self._optimistic_planning_calls += len(beliefs)
        self._planning_cpu_seconds += process_time() - started
        return paths

    def _action_is_utility_sensitive(
        self, belief: BeliefMap, position: Coordinate, goal: Coordinate, optimistic_path: tuple[Coordinate, ...],
        *, requester_id: int | None = None,
    ) -> bool:
        """Binary local expected-utility proxy: unknown state changes next action.

        This takes no truth-map or peer-map input. A query is worthwhile only
        when treating unobserved cells as blocked changes the receiver's next
        fixed-A* action versus its operational optimistic plan.
        """
        self._utility_trigger_checks += 1
        started = process_time()
        planner = (
            self._pessimistic_planners[requester_id]
            if requester_id is not None and requester_id < len(self._pessimistic_planners)
            else self.planner
        )
        pessimistic_path = planner.plan(self.pessimistic_adapter.to_planning_map(belief), position, goal).path
        elapsed = process_time() - started
        self._pessimistic_planning_calls += 1
        self._planning_cpu_seconds += elapsed
        self._utility_trigger_cpu_seconds += elapsed
        return self._action(optimistic_path, position) != self._action(pessimistic_path, position)

    def _deadline_plan(
        self, belief: BeliefMap, position: Coordinate, goal: Coordinate,
        optimistic_path: tuple[Coordinate, ...], requester_id: int,
    ) -> DecisionRepairPlan:
        """Derive a local repair deadline and byte-minimal witness set."""
        self._deadline_trigger_checks += 1
        started = process_time()
        pessimistic_path = self._pessimistic_planners[requester_id].plan(
            self.pessimistic_adapter.to_planning_map(belief), position, goal,
        ).path
        elapsed = process_time() - started
        self._pessimistic_planning_calls += 1
        self._planning_cpu_seconds += elapsed
        self._utility_trigger_cpu_seconds += elapsed
        plan = deadline_decision_repair_plan(
            belief, optimistic_path, pessimistic_path,
            round_trip_steps=2 * self.config.link.delay_steps,
            max_horizon=self.config.corridor_horizon,
            max_cells=self.config.max_digest_cells_per_message(),
        )
        if plan.ambiguous:
            self._deadline_ambiguous_receivers += 1
            if plan.decision_slack_steps is not None:
                self._decision_slacks.append(plan.decision_slack_steps)
                if plan.feasible:
                    self._deadline_feasible_receivers += 1
                else:
                    self._deadline_infeasible_receivers += 1
        self._deadline_query_cells += len(plan.cells)
        return plan

    def _certificate_plan(
        self, belief: BeliefMap, position: Coordinate, goal: Coordinate,
        optimistic_path: tuple[Coordinate, ...], requester_id: int,
    ) -> ScenarioCertificate:
        """Solve the bounded scenario-separation certificate exactly."""
        self._certificate_checks += 1
        started = process_time()
        uncapped_candidates = decision_candidate_cells(
            belief, optimistic_path,
            max_horizon=self.config.corridor_horizon,
            max_candidates=None,
        )
        self._certificate_candidate_cap_checks += 1
        self._certificate_uncapped_candidate_cells += len(uncapped_candidates)
        if len(uncapped_candidates) > self.config.certificate_max_cells:
            self._certificate_candidate_cap_hits += 1
        candidates = uncapped_candidates[:self.config.certificate_max_cells]
        blocked_sets = scenario_blocked_sets(
            candidates,
            uncertainty_order=self.config.certificate_uncertainty_order,
        )
        base_map = self.adapter.to_planning_map(belief)
        # The all-free scenario is anchored to the operational planner's
        # current path. Canonical A* evaluates blocked counterfactuals on the
        # shared unit-cost graph, avoiding dependence on incremental-cache
        # update mechanics while retaining the receiver's actual next action.
        scenario_planner = make_planner("astar")
        scenario_paths: dict[frozenset[Coordinate], tuple[Coordinate, ...]] = {}
        for blocked in blocked_sets:
            if not blocked:
                path = optimistic_path
            else:
                scenario_map = base_map.copy()
                for cell in blocked:
                    scenario_map[cell] = 1
                path = scenario_planner.plan(
                    scenario_map, position, goal,
                ).path
                self._certificate_scenario_planning_calls += 1
            scenario_paths[blocked] = path[:self.config.corridor_horizon + 1]
        certificate = minimum_scenario_certificate(
            candidates, scenario_paths,
            round_trip_steps=2 * self.config.link.delay_steps,
        )
        if self.config.link.delay_steps > 0:
            # With positive transport latency, protect both the earliest
            # feasible action distinctions and the later cell-entry
            # commitment.  At zero delay the exact action certificate alone
            # is sufficient and remains byte-minimal.
            fallback = self._deadline_plan(
                belief, position, goal, optimistic_path, requester_id,
            )
            union = tuple(dict.fromkeys(certificate.cells + fallback.cells))
            certificate = ScenarioCertificate(
                union, certificate.candidate_cells, certificate.scenario_count,
                certificate.conflicting_pairs, certificate.feasible_pairs,
                certificate.infeasible_pairs,
            )
        elapsed = process_time() - started
        self._planning_cpu_seconds += elapsed
        self._certificate_cpu_seconds += elapsed
        self._certificate_conflicting_pairs += certificate.conflicting_pairs
        self._certificate_feasible_pairs += certificate.feasible_pairs
        self._certificate_infeasible_pairs += certificate.infeasible_pairs
        self._certificate_candidate_cells += len(certificate.candidate_cells)
        self._certificate_query_cells += len(certificate.cells)
        return certificate

    @staticmethod
    def _sensor_contains(position: Coordinate, cell: Coordinate, radius: int) -> bool:
        """POGEMA square-footprint visibility used only for evaluation timing."""
        return max(abs(position[0] - cell[0]), abs(position[1] - cell[1])) <= radius

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
