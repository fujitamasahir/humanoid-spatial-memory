# Phase 1.5A-2 common controller specification

2026-11-07, proposal v0.2. Mathematical specification only. No controller or
navigation episode was implemented. This **replaces**, rather than silently
repairs, v0.1's per-map capped-distance controller. All six schedulers and two
ablations share it. See [architecture G](phase1_5a2_architecture_decision.md) and
[prior/model](phase1_5a2_spatial_prior_review.md).

## Timing and public inputs

Initialization: known pose x_0, goal g, initial charged observation at t=0, no
move/query repetition at t=0. For each t=1,...,80: terminate if already at goal;
incorporate the previous move's resulting pose, predict current occupancy after
the world advances, freeze routing potential, decide optional query, update from
its actual return if granted, choose action and move in the **current** world.
Advance the world only once per step. Sensing has zero simulated latency.

An entry into the pre-move robot cell already caused by this advancement is
unavoidable by a same-time query. It remains in the evaluator's contact metric;
the controller's future hazard proxy concerns entry on the **next** advancement.
No evaluator contact label enters control. Public movement and resulting known
pose may imply a blocked target, as ordinary proprioceptive information.

Actions, in deterministic tie order: north(0,-1), east(1,0), south(0,1), west(-1,0),
wait. Exclude moves outside the interior (the publicly occupied outer ring).
Wait is always available. Under a current map z, an occupied target gives B_a=1
and x'_a=x; otherwise move to target and B_a=0. Wait has B_a=0,x'_a=x even if
the current cell is occupied. Do not infer a free source cell from continued
overlap. Equal numerical mean losses within1e-12 absolute are ties; keep first
in this fixed order. Floating summation/state order is part of the implementation
lock, with golden fixtures. No method-specific tie rule is permitted.

## A finite public routing potential

Let p_i=P_t^-(Z_i=1) from the generative predictive mixture. Each is a marginal
under the agent model, not true occupancy. Interior protected start/goal have p=0.
Use directed grid edges u->v of cost

```
c(v) = 1 + 9*p_v/(1-p_v+.05), in [1,181].
D_t(u) = minimum sum of c(v) on an interior path from u to g.
s_t = minimum c(v) over interior cardinal neighbors v of current x.
phi_t(u) = clip((D_t(u)-D_t(x))/s_t, -1, 1).
```

The interior grid is connected as a **planning graph**, regardless of modeled
occupancy. All c are finite; D_t exists and D_t(g)=0. Reverse Dijkstra computes
it exactly. This is a soft routing heuristic: a known-looking wall has a high
finite cost, not a magical available passage. An actual move into it is still
blocked by physics and receives the blocked penalty. Do not hard-delete high-p
cells or replace no paths with1; there is no unreachable-distance saturation.
The graph does not claim the true goal is reachable.

Freeze D_t, s_t and p^- for **all** prior/posterior/hypothetical action losses at
this decision. A query changes belief over blocking/hazard outcomes, not these
potential numbers until the next step. This restriction makes the evaluated and
executed one-step decision consistent, but underestimates value of information
that changes a long-term route without changing local risk. No active viewpoint
planning or global POMDP optimality is claimed.

The coefficients9 and .05 are explicit engineering utility conventions: strongly
penalize high modeled occupancy while preserving finite costs. They are not
estimated from Phase 1.4 outcomes or asserted optimal. Alternatives require
review before development, not post-assessment tuning.

## State and action loss

For t<T, current map z and next map z_next, define

```
L_t(a,z,z_next) = .005 + .1*B_a + .2*phi_t(x'_a)
                 - I[x'_a=g]
                 + I[x'_a!=g] * I[z(x'_a)=0 and z_next(x'_a)=1].
```

Current terms are elapsed-action cost, blocked movement, bounded progress and
immediate goal reward. Future entry is a one-step proxy for dynamic contact,
coefficient1. A failed move stays at x; score hazard at x rather than the blocked
target. Ongoing occupancy at x is not a new entry. If the goal is reached now,
terminate and suppress future hazard; no next-state cost is charged at the goal.

At t=T replace shaping and future terms by a terminal failure loss:
`L_T(a,z)=.005+.1*B_a+I[x'_a!=g]`.
After termination loss/action/query are zero. No forecast Z_T+1 is generated.
This explicitly aligns the last action with completion; earlier decisions remain
myopic proxies rather than a Bellman-optimal contact-free completion objective.

The global loss range is [-1.195,1.305], width2.5. Progress may give negative
loss, which is intentional and bounded. Only differences affect a one-step
decision. The .005 constant cancels between nonterminal actions; it does not
alone minimize elapsed steps. Goal reward and potential are what favor progress.
Do not equate utility improvement with a measured goal/contact-free gain.

### Forecast marginalization and action selection

For each sampled current map, analytically integrate the tile-refresh kernel.
Replace the last indicator's expectation with
`I[z(x'_a)=0] * r * B_C(bit at x'_a=1)` for an unprotected cell, zero for a
protected cell/goal or t=T. Thus `Lbar(a,z)=E[L(a,z,Z_next)|z]` exactly within
the declared model. Forecast occupancy is uncertain even when Z is known;
current sensing cannot reveal the next refresh. No P=8 future-map bank is used.

The controller minimizes `mean_{s=1..64} Lbar(a,z_s)` over64 prior or posterior
control samples from the selected G operator. The same current-state loss and
fixed D_t appear before/after queries. A generating outer evaluation state never
enters this training bank. Changes to the potential, model, forecast rule,
numerical precision or action ordering invalidate the method lock.

## Exact finite fixtures: progress is possible, not guaranteed

These are hand-specified loss/probability tables, not executed spatial episodes.
All are checked with rational arithmetic in the
[standalone mathematical tests](../scripts/audit_phase1_5a2.py).

1. **Known safe progress:** a free forward step with phi=-1, no hazard and no
   goal arrival has loss `.005-.2=-.195`; wait has .005. Progress strictly wins.
   A safe detour step on the least-cost soft route has the same contrast even
   if it initially increases Manhattan distance. No truth path is supplied.
2. **Uncertain progress:** forward blocked with probability1/4, phi=-1 if it
   moves and0 if blocked, conditional entry risk .01 only after moving. Mean
   loss is `.005+.1/4-.2*3/4+.01*3/4=-.1125`. Protected-source wait costs .005.
   The controller therefore need not wait merely because occupancy is uncertain.
3. **Legitimate waiting:** the same example with blocked probability.9 gives
   `.005+.09-.02+.001=.076`, greater than safe wait .005. A universally moving
   controller would be wrong here; waiting is not itself a design failure.
4. **Action-relevant sensing:** two equiprobable worlds swap which of two
   phi=-1 actions is blocked. With no hazard, a free action costs-.195 and a
   blocked one .105; either prior mean is-.045, less than wait .005. Perfect
   sensing lowers risk to-.195: exact model EVSI=.15, exceeding price .02.
   Symmetric .05-bit-error identifying observations give EVSI=.135.
5. **Terminal goal:** at T, a known-free goal step costs .005; wait short of
   goal costs1.005. Goal arrival has neither shaping ambiguity nor post-goal
   hazard. Initial x=g terminates before any optional query.
6. **No decision relevance:** if one action is optimal after every possible
   observation, exact EVSI=0 despite uncertain cells. Under the approximate
   algorithm, control-sampling error can give negative value; preserve it.

Fixtures demonstrate a coherent progress mechanism and an activation range.
They do not guarantee avoiding traps, oscillation or repeated high-p wall
attempts. The soft potential can prefer a wall shortcut over a long true detour;
query value ignores future route-potential changes, and one-step safety can
favor waiting too long. Publish these failure modes rather than adding an
assessment-time exploration bonus, wait timeout or navigation repair.

## Observation-cost units and fair comparisons

One new-entry hazard has utility cost1. A full granted sensor call costs c_s=.02
in those same utility units; charge initialization too. The primary gate compares
the proposed policy-conditioned value estimate with c_s, with no grid-area
normalization, shadow price or two-SE confidence claim. Cost does not disappear
when a return is unhelpful. Track requests, denials and actual grants separately.
Cap8 includes initialization; an exhausted cap never invokes the sensor.

All scheduler rows share this controller, model, potential and physical sensor.
Legacy route-weighted scheduling keeps its frozen internal feature scale while
the ledger uses .02; it is a timing port, not a historical end-to-end reproduction.
Only the phantom-goal ablation changes the gate's goal/potential/loss; its actual
controller always uses the real goal. The one-cell ablation changes gate
information, not what the real full sensor returns after a grant.

## Scientific scope

This loss is not physical collision severity, balance risk, energy or humanoid
traversability. It does not model uncertain pose, sensing latency or braking.
The contact-free endpoint remains separate from utility. Progress and sensing
fixtures, calibration, bounded rejection and runtime must pass development-only
checks before assessment. The controller is fully specified for review but
neither implemented nor empirically validated here.
