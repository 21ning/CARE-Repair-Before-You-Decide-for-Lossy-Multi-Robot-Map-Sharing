# CARE-DC: deadline-constrained decision certificates

CARE treats lossy map repair as a finite communication optimization problem,
not as a learned retransmission rule. Robot `i` uses only its explicit local
replica `b_i(t)`, current pose and goal. It never reads the ground-truth map or
another robot's memory.

## Problem statement

Let `U_t` be at most `n=8` currently unknown cells on, or one action-graph hop
from, the receiver's next `H=8` optimistic path vertices. A scenario
`omega ⊆ U_t` marks blocked candidates; all other candidates are provisionally
free. CARE uses the bounded uncertainty family

```text
Omega_q(U_t) = {omega ⊆ U_t : |omega| <= q},   q = 2.
```

The family contains at most

```text
S(n,q) = sum_{r=0}^q C(n,r) = 37
```

scenarios. The all-free scenario is anchored to the operational planner's
current path. A deterministic shortest-path oracle evaluates every blocked
counterfactual on the same four-neighbor, unit-cost graph as operational A* or
D* Lite. This avoids counterfactual dependence on incremental-cache update
mechanics while retaining the receiver's actual next action.

For a pair whose action sequences first diverge at step `d(omega, omega')`,
define its distinguishability set

```text
D(omega, omega') = omega symmetric_difference omega'.
```

If the measured query--patch round trip is `L_rtt=2*link_delay_steps`, the pair
is repairable by the present request only when `d(omega, omega') >= L_rtt`.
Let `E_t` contain all such feasible action-conflicting pairs. With the actual
wire codec, a query costs `B(Q)=16+6|Q|` bytes. CARE solves

```text
minimize    B(Q)
over        Q ⊆ U_t
subject to  Q intersects D(e) for every e in E_t.
```

The implementation enumerates candidate subsets in cardinality order and
therefore returns an exact minimum, with deterministic path-priority
tie-breaking. It is not a learned score and has no tuned retransmission
threshold.

## Scenario-separation theorem

**Theorem.** A query `Q ⊆ U_t` identifies every deadline-feasible action
decision in the bounded scenario family if and only if
`Q ∩ D(omega,omega')` is nonempty for every pair in `E_t`.

**Proof.** Querying `Q` observes the binary occupancy signature
`omega ∩ Q`. Two scenarios have identical signatures exactly when
`Q ∩ (omega symmetric_difference omega')` is empty. If that happens for an
action-conflicting pair, the receiver cannot tell which action sequence is
valid, so separation is necessary. If every conflict set is hit, every pair
with different feasible action sequences has different query signatures;
hence the returned cell states identify its action-equivalence class, proving
sufficiency.

**Corollary.** Because every query cell costs the same six encoded bytes, a
minimum-cardinality hitting set is also a minimum-byte query. Cardinality-first
enumeration therefore returns the exact codec-optimal certificate within the
declared scenario family.

The bounded runtime is

```text
scenario planning: O(S(n,q) * P)
conflict construction: O(S(n,q)^2 * H)
exact certificate: O(2^n * |E_t| * n),
```

where `P` is one bounded shortest-path call. With `n=8`, `q=2`, the largest
online problem has 37 scenarios and 256 query subsets. These caps are explicit
computational assumptions, not hidden experimental tuning.

## Route-commitment certificate

Scenario separation determines which cells distinguish locally plausible
actions. Positive transport delay adds a second requirement: the repair must
arrive before the robot enters an uncertain branch.

The receiver also plans on interval endpoints:

- `pi+`: UNKNOWN is traversable (the operational optimistic plan);
- `pi-`: UNKNOWN is blocked (the pessimistic bound).

Let `k` be the first UNKNOWN index on `pi+`. The latest safe repair time is
`tau=max(0,k-1)`. If `tau < L_rtt`, that route-commitment repair is suppressed
and recorded as deadline-infeasible. Otherwise CARE forms a one-hop influence
set from the two branches between their first divergence and reconvergence.

At zero delay, the exact scenario certificate alone is sufficient and
byte-minimal. At positive delay, final CARE uses the **dual certificate**

```text
Q_CARE = Q_scenario union Q_commitment.
```

This protects both scenario-level action identifiability and the later
cell-entry commitment. Duplicate cells are removed before binary encoding.

## Protocol execution

Normal observations remain one-shot version-stamped deltas. A CARE query is a
digest of only the certificate cells. A peer returns only cells whose stamps
dominate the requester's stamps. Delta, digest, patch and acknowledgement
packets all traverse the same directed lossy/delayed link and count against the
same per-step budgets. Attempted traffic includes dropped packets.

## Guarantee boundary

The theorem is exact for the declared `q`-sparse candidate scenario family. It
does not guarantee decision consistency for arbitrary unbounded map
uncertainty, does not assume that a peer knows every requested cell, and does
not claim to dominate reliable ARQ in absolute success. CARE targets a compact
reliability--traffic operating point under decision-critical map loss.

## Planner independence

The closed-loop experiments execute the same protocol with deterministic A*
and incremental D* Lite. Both conditions share maps, link traces, wire codec,
budgets and policy code. Planner identity changes the operational path anchor;
blocked counterfactuals remain defined on their common action graph.
