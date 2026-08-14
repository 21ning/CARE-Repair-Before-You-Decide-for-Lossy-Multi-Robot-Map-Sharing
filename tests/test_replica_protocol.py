from __future__ import annotations

from inspect import signature

from cmvr.communication import (
    ReplicaPolicy, bernoulli_local_decoder_probabilities,
    bernoulli_rate_distortion_plan,
    deadline_decision_repair_plan, decision_candidate_cells, first_path_divergence, full_replica_chunk,
    minimum_scenario_certificate, ocbc_forward_simulation_plan,
    ordered_digest_peers, path_guided_spatial_coverage_plan, planning_corridor,
    path_aware_top_k_plan, replica_digest, scenario_blocked_sets,
    single_cell_sensitivity_plan, voi_per_byte_plan,
)
from cmvr.mapping import BeliefMap, MapUpdate


def test_planning_corridor_is_canonical_and_manhattan_dilated() -> None:
    cells = planning_corridor(((1, 1), (1, 2), (1, 3)), (5, 5), horizon=1, radius=1)
    assert cells == ((0, 2), (1, 1), (1, 2), (1, 3), (2, 2))


def test_deadline_plan_derives_slack_and_queries_only_unknown_witnesses() -> None:
    belief = BeliefMap((7, 7))
    for y in (1, 2):
        belief.apply_update(MapUpdate.create(
            sender_id=0, x=3, y=y, cell_state=0, version=1, observed_at=0,
        ))
    optimistic = ((3, 1), (3, 2), (3, 3), (3, 4), (3, 5))
    pessimistic = ((3, 1), (3, 2), (2, 2), (2, 3), (2, 4), (3, 4), (3, 5))
    plan = deadline_decision_repair_plan(
        belief, optimistic, pessimistic, round_trip_steps=1,
        max_horizon=8, max_cells=12,
    )
    assert first_path_divergence(optimistic, pessimistic) == 1
    assert plan.ambiguous and plan.feasible
    assert plan.decision_slack_steps == 1
    assert (3, 3) in plan.cells
    assert all(int(belief.occupancy[cell]) < 0 for cell in plan.cells)


def test_deadline_plan_suppresses_repairs_that_cannot_arrive_in_time() -> None:
    belief = BeliefMap((5, 5))
    plan = deadline_decision_repair_plan(
        belief, ((2, 1), (2, 2), (2, 3)), ((2, 1), (1, 1), (1, 2)),
        round_trip_steps=2, max_horizon=8, max_cells=12,
    )
    assert plan.ambiguous and not plan.feasible
    assert plan.decision_slack_steps == 0
    assert plan.cells == ()

    ungated = deadline_decision_repair_plan(
        belief, ((2, 1), (2, 2), (2, 3)), ((2, 1), (1, 1), (1, 2)),
        round_trip_steps=2, max_horizon=8, max_cells=12,
        enforce_deadline=False,
    )
    assert ungated.ambiguous and not ungated.feasible
    assert ungated.decision_slack_steps == plan.decision_slack_steps
    assert ungated.cells


def test_scenario_certificate_is_the_exact_minimum_hitting_set() -> None:
    a, b, c = (1, 1), (1, 2), (1, 3)
    common = ((3, 1), (3, 2), (3, 3))
    right = common + ((3, 4),)
    up = common + ((2, 3),)
    paths = {
        frozenset(): right,
        frozenset((a, b)): up,
        frozenset((b, c)): up,
    }
    certificate = minimum_scenario_certificate(
        (a, b, c), paths, round_trip_steps=2,
    )
    assert certificate.cells == (b,)
    assert certificate.conflicting_pairs == 2
    assert certificate.feasible_pairs == 2
    assert certificate.infeasible_pairs == 0


def test_scenario_certificate_records_pairs_that_miss_the_deadline() -> None:
    cell = (1, 1)
    certificate = minimum_scenario_certificate(
        (cell,), {
            frozenset(): ((2, 1), (2, 2)),
            frozenset((cell,)): ((2, 1), (1, 1)),
        },
        round_trip_steps=1,
    )
    assert certificate.cells == ()
    assert certificate.conflicting_pairs == 1
    assert certificate.feasible_pairs == 0
    assert certificate.infeasible_pairs == 1


def test_q_sparse_scenario_family_has_declared_bounded_size() -> None:
    candidates = tuple((1, index) for index in range(8))
    scenarios = scenario_blocked_sets(candidates, uncertainty_order=2)
    assert len(scenarios) == 1 + 8 + 28
    assert scenarios[0] == frozenset()
    assert all(len(scenario) <= 2 for scenario in scenarios)


def test_candidate_cap_can_be_audited_against_the_uncapped_set() -> None:
    belief = BeliefMap((9, 9))
    path = tuple((4, column) for column in range(1, 8))
    uncapped = decision_candidate_cells(
        belief, path, max_horizon=6, max_candidates=None,
    )
    capped = decision_candidate_cells(
        belief, path, max_horizon=6, max_candidates=4,
    )
    assert len(uncapped) > 4
    assert capped == uncapped[:4]


def test_path_aware_top_k_uses_earliest_path_influence_without_replanning() -> None:
    belief = BeliefMap((7, 7))
    path = ((3, 1), (3, 2), (3, 3), (3, 4))
    plan = path_aware_top_k_plan(
        belief, path, max_horizon=3, max_cells=3,
    )

    assert len(plan.candidate_cells) > len(plan.cells)
    assert plan.cells == plan.candidate_cells[:3]
    assert plan.cells[0] == (3, 2)
    assert plan.sensitive_cells == 0


def test_pgsc_is_deterministic_budgeted_and_not_path_proximity_top_k() -> None:
    belief = BeliefMap((7, 7))
    path = ((3, 1), (3, 2), (3, 3), (3, 4), (3, 5))
    pgsc = path_guided_spatial_coverage_plan(
        belief, path, max_horizon=4, max_cells=4, sigma=1.0,
    )
    repeated = path_guided_spatial_coverage_plan(
        belief, path, max_horizon=4, max_cells=4, sigma=1.0,
    )
    top_k = path_aware_top_k_plan(
        belief, path, max_horizon=4, max_cells=4,
    )

    assert pgsc == repeated
    assert len(pgsc.cells) == 4 == len(set(pgsc.cells))
    assert len(pgsc.candidate_cells) <= 2 * len(pgsc.cells)
    assert set(pgsc.cells) <= set(pgsc.candidate_cells)
    assert pgsc.cells != top_k.cells
    assert path_guided_spatial_coverage_plan(
        belief, path, max_horizon=4, max_cells=0, sigma=1.0,
    ).cells == ()
    assert ReplicaPolicy.PGSC_REPAIR is ReplicaPolicy.PATH_GUIDED_COMPRESSION


def test_brd_uses_only_local_decoder_uncertainty_and_differs_from_pgsc() -> None:
    belief = BeliefMap((7, 7))
    for x, y, state in (
        (2, 2, 1), (2, 3, 0), (4, 4, 1), (4, 5, 1), (3, 0, 0),
    ):
        belief.apply_update(MapUpdate.create(
            sender_id=0, x=x, y=y, cell_state=state,
            version=1, observed_at=0,
        ))
    path = ((3, 1), (3, 2), (3, 3), (3, 4), (3, 5))
    probabilities = bernoulli_local_decoder_probabilities(
        belief, ((3, 2), (3, 4), (0, 0)), sigma=1.0,
    )
    brd = bernoulli_rate_distortion_plan(
        belief, path, max_horizon=4, max_cells=4, sigma=1.0,
    )
    pgsc = path_guided_spatial_coverage_plan(
        belief, path, max_horizon=4, max_cells=4, sigma=1.0,
    )

    assert all(0.0 < probability < 1.0 for probability in probabilities.values())
    assert probabilities[(3, 4)] > probabilities[(0, 0)]
    assert len(brd.cells) == 4
    assert brd.cells != pgsc.cells
    assert brd == bernoulli_rate_distortion_plan(
        belief, path, max_horizon=4, max_cells=4, sigma=1.0,
    )
    assert ReplicaPolicy.BRD_REPAIR is ReplicaPolicy.RATE_DISTORTION_COMPRESSION


def test_ocbc_fs_is_seeded_budgeted_and_accepts_only_explicit_priors() -> None:
    candidates = ((3, 2), (3, 3), (3, 4))
    optimistic = ((3, 1), (3, 2), (3, 3), (3, 4), (3, 5))
    blocked_paths = {
        candidates[0]: ((3, 1), (2, 1), (2, 2), (2, 3), (2, 4)),
        candidates[1]: ((3, 1), (3, 2), (2, 2), (2, 3), (2, 4)),
        candidates[2]: ((3, 1), (3, 2), (3, 3), (2, 3), (2, 4)),
    }
    arguments = dict(
        max_horizon=4, max_cells=2, samples=512, seed=19,
        blocked_probabilities={
            candidates[0]: .9, candidates[1]: .5, candidates[2]: .1,
        },
    )
    first = ocbc_forward_simulation_plan(
        candidates, optimistic, blocked_paths, **arguments,
    )
    second = ocbc_forward_simulation_plan(
        candidates, optimistic, blocked_paths, **arguments,
    )

    assert first == second
    assert 0 < len(first.cells) <= 2
    assert first.cells[0] == candidates[0]
    assert set(first.cells) <= set(candidates)
    assert ReplicaPolicy.OCBC_FS_REPAIR is ReplicaPolicy.OCBC_FORWARD_SIMULATION


def test_voi_per_byte_is_deterministic_bounded_and_uses_actual_entry_costs() -> None:
    candidates = ((3, 2), (3, 3), (3, 4))
    optimistic = ((3, 1), (3, 2), (3, 3), (3, 4), (3, 5))
    blocked_paths = {
        candidates[0]: ((3, 1), (2, 1), (2, 2), (2, 3), (2, 4)),
        candidates[1]: ((3, 1), (3, 2), (2, 2), (2, 3), (2, 4)),
        candidates[2]: ((3, 1), (3, 2), (3, 3), (2, 3), (2, 4)),
    }
    priors = {candidates[0]: .2, candidates[1]: .4, candidates[2]: .8}
    first = voi_per_byte_plan(
        candidates, optimistic, blocked_paths,
        max_horizon=4, max_cells=2, blocked_probabilities=priors,
        query_entry_bytes=6, patch_entry_bytes=13,
    )
    second = voi_per_byte_plan(
        candidates, optimistic, blocked_paths,
        max_horizon=4, max_cells=2, blocked_probabilities=priors,
        query_entry_bytes=12, patch_entry_bytes=26,
    )

    # Multiplying every marginal cell cost by the same factor preserves the
    # ordering while still making the charged cost an explicit API input.
    assert first == second
    assert 0 < len(first.cells) <= 2
    assert first.cells[0] == candidates[2]
    assert ReplicaPolicy.VOI_PER_BYTE_REPAIR is ReplicaPolicy.VOI_REPAIR


def test_closest_work_selector_apis_cannot_receive_truth_or_peer_replicas() -> None:
    forbidden = {"true_map", "truth", "peer_belief", "peer_replica"}
    for selector in (
        path_guided_spatial_coverage_plan,
        bernoulli_rate_distortion_plan,
        ocbc_forward_simulation_plan,
        voi_per_byte_plan,
    ):
        assert forbidden.isdisjoint(signature(selector).parameters)


def test_single_cell_sensitivity_ranks_actions_and_enforces_deadline() -> None:
    a, b, c = (1, 1), (1, 2), (1, 3)
    optimistic = ((3, 1), (3, 2), (3, 3), (3, 4))
    immediate = ((3, 1), (2, 1), (2, 2), (2, 3))
    later = ((3, 1), (3, 2), (2, 2), (2, 3))
    unchanged = optimistic

    zero_delay = single_cell_sensitivity_plan(
        (a, b, c), optimistic,
        {a: later, b: immediate, c: unchanged},
        round_trip_steps=0, max_cells=2,
    )
    assert zero_delay.cells == (b, a)
    assert zero_delay.sensitive_cells == 2
    assert zero_delay.infeasible_cells == 0

    delayed = single_cell_sensitivity_plan(
        (a, b, c), optimistic,
        {a: later, b: immediate, c: unchanged},
        round_trip_steps=1, max_cells=2,
    )
    assert delayed.cells == (a,)
    assert delayed.sensitive_cells == 2
    assert delayed.infeasible_cells == 1


def test_scenario_certificate_tie_break_is_deterministic() -> None:
    a, b = (1, 1), (1, 2)
    right = ((2, 1), (2, 2), (2, 3))
    left = ((2, 1), (1, 1), (1, 2))
    certificate = minimum_scenario_certificate(
        (a, b), {
            frozenset(): right,
            frozenset((a, b)): left,
        },
        round_trip_steps=0,
    )
    # Either cell separates the two scenarios; candidate order selects a.
    assert certificate.cells == (a,)


def test_full_replica_chunks_cover_the_domain_without_oversized_digest() -> None:
    chunks = [full_replica_chunk((3, 4), max_cells=5, phase=phase) for phase in range(3)]
    assert all(1 <= len(chunk) <= 5 for chunk in chunks)
    assert set().union(*map(set, chunks)) == {(x, y) for x in range(3) for y in range(4)}
    assert full_replica_chunk((3, 4), max_cells=5, phase=3) == chunks[0]


def test_digest_peer_order_uses_online_distance_then_rotates_ties() -> None:
    positions = ((5, 5), (5, 4), (5, 6), (8, 5))
    assert ordered_digest_peers(requester_id=0, positions=positions, phase=0, limit=1) == (1,)
    assert ordered_digest_peers(requester_id=0, positions=positions, phase=1, limit=1) == (2,)


def test_replica_digest_changes_when_any_known_stamp_or_state_changes() -> None:
    belief = BeliefMap((4, 4))
    initial = replica_digest(belief)
    belief.apply_update(MapUpdate.create(sender_id=1, x=2, y=3, cell_state=1, version=1, observed_at=2))
    assert replica_digest(belief) != initial
