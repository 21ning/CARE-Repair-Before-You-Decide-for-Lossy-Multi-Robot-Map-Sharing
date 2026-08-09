# CARE: deadline-aware decision-critical replica repair

CARE treats replica repair as a constrained communication decision, rather
than a fixed retry rule. Robot `i` holds only its explicit local replica
`b_i(t)`; the method never reads the true map or another robot's memory.

## Optimization target

At step `t`, let `Q_i(t)` be the cells included in a digest query and let
`B(Q)=16+6|Q|` be its exact encoded query cost. CARE uses the following online
surrogate for the otherwise unobservable decision-consistency constraint:

```text
minimize    B(Q_i(t))
subject to  the repair response can arrive before the first robust-action
            ambiguity on the receiver's current plan, and
            Q_i(t) covers every unknown witness on the ambiguous branch.
```

The objective prices the actual binary codec. Patch bytes are then charged
exactly as `4+13M`, where `M` is the number of newer cells returned by a peer.
The constraint is local and computable; it is not an oracle guarantee that a
peer already knows every requested cell.

## Deadline derivation

The receiver plans twice on the same versioned replica:

- `pi+`: UNKNOWN is traversable (the operational optimistic plan);
- `pi-`: UNKNOWN is blocked (the pessimistic bound).

Their first path divergence establishes that uncertainty can change the plan.
Let `k` be the index of the first UNKNOWN cell on `pi+`. The last safe time to
repair before committing to that uncertain transition is therefore
`tau = max(0, k-1)` environment steps. The query/patch protocol has round-trip latency

```text
L_rtt = 2 * link_delay_steps.
```

CARE sends a repair only when `tau >= L_rtt`. A repair that cannot arrive by
the decision is suppressed and recorded as `deadline_infeasible`; this is a
derived deadline rule, not a tuned delay threshold.

## Byte-minimal decision certificate

If a repair is feasible, CARE takes both branches from their first divergence
to their first reconvergence. For the next route commitment, direct branch
feasibility is determined by branch vertices and their one-step successors, so
CARE defines a one-hop action-graph influence certificate and removes every already-known cell. Every
remaining digest entry costs six bytes. The complete set is the robust local
certificate; if the codec cap binds, path order gives the minimum-byte prefix
that protects the earliest decisions first.

`corridor_horizon` is retained only as a maximum work/message guard. Unlike
PSR-UT, it no longer means "always query H future steps plus a hand-set
radius." `corridor_radius` is not used by deadline-aware CARE.

## Planner independence

The protocol consumes only a path and a pessimistic path from the common
`Planner` interface. The repository evaluates it with:

- deterministic four-neighbour A* (fresh static search);
- deterministic D* Lite (incremental replanning after map changes and robot
  motion).

Planner identity is a first-class experiment column. Both planners use the
same maps, link traces, packet codec, budgets, and policy code.
