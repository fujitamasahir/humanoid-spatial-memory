# Phase 2 RDAO gate-route feature analysis: why simple heuristics are insufficient

**Status:** observational analysis of previously tested 36 FIT worlds;
NOT held out; no new MuJoCo runs and no claims about a learned
or deployable RDAO v2 rule.

## Verified outputs and sampling units

Saved source: results/phase2_mujoco/rdao_v1_gate_event_route_features_v1/
gate_event_route_features.csv

- 144 saved episode-policy records were read, yielding 107 gate override
  EVENTS: first=34, every=73.
- first overrides occur in 34 episode schedules but only 19 distinct
  world identities. They are all executed as selected actions, with
  the normal independent emergency safety and actual-model shield.
- The benefit of first was concentrated in just two distinct
  worlds (M:80030009 and M:80030010) across both correlated schedules.
- In the 34 first-gate episodes, the horizon-censored step outcome
  shortened in 4, was unchanged in 16, and lengthened in 14.
  Of the 16 unchanged steps, 11 remain failures censored at 80,
  and five still succeed at the same arrival step.
- A failed episode's horizon-80 step count is NOT its actual
  unobserved arrival time. "Unchanged" does not imply equal
  underlying completion times or similar paths.

Only FIRST gate effects can be classified at the episode level in
this simplified audit: with first, one actually selected action is
overridden at most once per episode. The Every condition may
have multiple interventions along a changing trajectory; assigning
its terminal outcome to every individual event would be causally
invalid. No fit-world statistics should treat schedules as
independent worlds.

## Empirical overlap

Among first-gate episodes, features grouped by the observed
horizon-censored step change:

| Feature | 4 shortened episodes (2 worlds) | 16 same censored steps | 14 lengthened |
|---|---:|---:|---:|
| Mean change to RDAO nominal A* route cost | +3.75 | +5.23 | +5.98 |
| Mean old-route first occupied translation index | 2.50 | 2.94 | 3.00 |
| Mean observed free branches from destination | 1.00 | 1.44 | 1.57 |
| Mean newly known occupied cells | 4.50 | 5.69 | 5.79 |
| Mean total memory changed cells | 7.50 | 12.94 | 15.86 |

The means differ but have overlapping ranges and do not
demonstrate a generalizable decision rule.

**Concrete collision:** M:80030010 step3 (rescue) and
M:80030000 schedule0 step37 (no rescue, remains failed)
share exactly the same triple:

- nominal A* cost increase = 4.50,
- first now-known occupied location on old route = third translation,
- number of observed-free nonbackward destination neighbors = 1.

Thus no deterministic rule using ONLY this triple can distinguish
these two observations. Additional features and better causal
mechanisms might help; this is not an impossibility proof for all
online policies.

Also M:80030000 schedule1 step13 is a successful baseline but
one-step gate adds 4 executed steps. Its triple (4.75, 3, 1)
is similar to the favorable M:80030010 case. Merely tuning
a small cost or blocker threshold to two rescued worlds will
overfit the observed Phase 2 development cases.

### What these features actually mean

The cost and route from RDAO's diagnostic are its nominal
observed-map, footprint-aware A* (with static/unknown assumptions).
That route is **not identical** to the actual selected action of
the independently guarded pedestrian-aware G1 navigation policy.
The local free-branch count looks only at ternary cell centers,
not every branch's swept G1 footprint clearance. Both features
can be useful descriptors, but should not be called a validated
long-horizon route value.

Revisited-origin-within-6-steps is an AFTER-THE-FACT future
trajectory label, not an online signal. Both good and bad gate
interventions can revisit the origin quickly. It cannot be
directly used by a runtime algorithm.

## Fundamental limit of naive one-step planning comparison

Suppose V(m,s) is the optimal cost under an unchanged, fixed
updated memory map m and fixed deterministic planning model,
and a is a legal action from s to s' with cost c(a).
By shortest-path optimality,

    V(m,s) <= c(a) + V(m,s').

Therefore a policy that gates ONLY when
"1 step + updated-map plan from the target is cheaper than
the updated-map plan from the current pose"
will typically reject ALL non-optimal gate actions by design.
The observed gains from action continuation cannot be explained
as an immediate cost improvement on the exact same fixed map.

Benefits must instead be investigated through mechanisms outside
that narrow comparison, such as:
- uncertainty and action-conditioned future sensing viewpoints;
- future observation availability and RDAO scheduling;
- memory update and route reversal/hysteresis effects;
- limited planner approximation, pedestrian dynamics and
  selected-action shield feedback;
- censored success constraints rather than shortest-path cost alone.

The previous shadow visibility results already documented that
the existing predicted_cell_visibility often misses real
route-near new cells. Do not assume it provides a calibrated
estimate of future information gain without a separate
sensor-visibility calibration experiment.

## Next read-only reproducibility check

The new audit script
[scripts/analyze_rdao_gate_feature_separability.py](../scripts/analyze_rdao_gate_feature_separability.py)
and its pure tests
[tests/test_rdao_gate_feature_separability.py](../tests/test_rdao_gate_feature_separability.py)
use the existing feature CSV to report:
- one-action first-gate episode transitions;
- feature ranges/means by paired horizon-censored step effect;
- identical simple feature signatures with different outcomes;
- world versus schedule replication counts;
- all warnings about future-information leakage and
  multiple intervention confounding.

No threshold optimization, predictive fitting, new worlds,
MuJoCo runs, or held-out data access are performed. The script
saves new audit CSV+summary JSON and refuses to overwrite
existing outputs.

Local commands:

~~~sh
git pull --ff-only origin phase2/mujoco-proxy-pilot
.venv/bin/python -m pytest tests/test_rdao_gate_feature_separability.py -q
.venv/bin/python scripts/analyze_rdao_gate_feature_separability.py
~~~

**Authoring status:** These new commands and tests have not yet been
executed on the pinned local environment. Original results are
read-only and unaffected.

## Research decision

Do not promote "first" to RDAO v2 because it raises fit-world
completion 57/72 to only 61/72 (Periodic and Age each 66/72),
lengthens 14 of the 57 originally successful runs, and its
apparent gains derive from only 2 related maze instances.

Recommended next QUESTION (not a claimed result): Could a
low-cost estimate of action-conditioned observation opportunity,
combined with a route-stability constraint and public
collision checking, distinguish useful from wasteful
continuation better than purely geometric blocker counts?
That would require calibrated visibility predictions, strictly
decision-time information and prospective experiments. Only
after development evaluation should the final decision rule
be frozen and tested in held-out worlds.
