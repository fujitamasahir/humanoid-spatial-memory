"""Event-triggered Periodic and Age observation controls (candidate A).

Two opt-in PROSPECTIVE development policies sharing the original memory
representation, 61-ray observation, emergency safety and selected-action
MuJoCo collision shield. No RDAO route-score, counterfactual planner,
shadow truth, scene occupancy, pedestrian oracle or future scan input.

Allowed triggering events are *previously executed* public feedback:
1. The selected action was REJECTED by the unchanged action shield.
2. The normal observed-map G1 planner returned no route.
Both events are delivered only AFTER that step's sensing decision;
they can request a normal authorized spatial-memory observation at
the NEXT opportunity. Merely being near a pedestrian is not a trigger.

Periodic base: due when >= frozen interval since last observation,
rather than a global fixed tick. An early event scan resets that
clock and can REPLACE a later periodic tick rather than add a scan.
Without events, this is exactly ordinary frozen periodic.

Age base: preserve frozen AdaptiveObserver score and age threshold.
Early event scan refreshes the usual observed-cell timestamps;
without events, this is exactly ordinary frozen age.

Avoid frantic repeated scans: event scan is considered only if
at least two steps have passed since last authorized scan, and at
least three steps have passed since the last event-triggered scan.
Frozen FIRST candidate rules are not fitted to FIT world outcomes.
The shared cap includes the initial scan.

Safety and route-planning remain unchanged; new scans may change
the actual planner's future decisions via normal public memory.
No assertions of superior completion or sensing efficiency.
"""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .scheduling import ObservationController


@dataclass(frozen=True)
class EventObservationParameters:
    """Frozen conservative cooldown for prospective development screen."""
    min_steps_since_any_observation: int = 2
    min_steps_since_event_observation: int = 3

    def __post_init__(self):
        if (type(self.min_steps_since_any_observation) is not int or
                type(self.min_steps_since_event_observation) is not int or
                self.min_steps_since_any_observation < 1 or
                self.min_steps_since_event_observation < 1):
            raise ValueError("Event scan cooldowns must be positive integers")


class EventTriggeredObservationController:
    """Drop-in observation-controller API for frozen Periodic/Age G1 evaluator.

    Must receive ONLY public past selected-action rejection and actual
    observed-map planner "no route" feedback using note_* methods.
    """

    def __init__(self, initial, method, *, interval=2, radius=3,
                 parameters=None, max_observations=None,
                 event_parameters=None):
        if method not in ("periodic", "age"):
            raise ValueError("Only Periodic or Age may be event-triggered")
        self.method = method
        self.interval = int(interval)
        if self.interval < 1:
            raise ValueError("Periodic interval must be positive")
        self.base = ObservationController(
            initial, method, interval=interval, radius=radius,
            parameters=parameters, max_observations=max_observations)
        self.memory = self.base.memory
        self.params = event_parameters or EventObservationParameters()
        self.requests = self.denied = 0
        self.last_observation_step = 0
        self.last_event_observation_step = -10**9
        self._blocked_pending = False
        self._no_route_pending = False
        self.feedback_blocked_count = 0
        self.feedback_no_route_count = 0
        self.event_observation_count = 0
        self.ordinary_observation_count = 0
        self.decisions = []
        self.observation_log = []
        self._next_scan_reason = None

    @property
    def cap(self):
        return self.base.cap

    @property
    def used(self):
        return self.base.used

    @property
    def remaining(self):
        return None if self.cap is None else max(0, self.cap-self.used)

    def note_selected_action_rejected(self, step):
        """From completed selected-action shield, not an unselected query."""
        if int(step) < 1:
            raise ValueError("Action feedback must follow an executed step")
        self._blocked_pending = True
        self.feedback_blocked_count += 1

    def note_no_route(self, step):
        """From completed public-map planner, no hidden occupancy consulted."""
        if int(step) < 1:
            raise ValueError("Route feedback must follow an executed step")
        self._no_route_pending = True
        self.feedback_no_route_count += 1

    def _baseline_due(self, step, position):
        if self.method == "periodic":
            return (step > 0 and step-self.last_observation_step >= self.interval), None
        observer = self.base.agent
        score = observer.score(step, position)
        return bool(step > 0 and score >= observer.threshold()), float(score)

    def decide(self, step, position):
        step = int(step)
        if step < 1:
            return {
                "observation_requested": False,
                "observation_granted": False,
                "observation_score": None,
                "observation_position": tuple(position),
            }
        baseline_due, baseline_score = self._baseline_due(step, position)
        event_type = (
            "blocked_selected_action" if self._blocked_pending else
            "no_observed_map_route" if self._no_route_pending else None)
        eligible_event = bool(event_type and
            step-self.last_observation_step >=
                self.params.min_steps_since_any_observation and
            step-self.last_event_observation_step >=
                self.params.min_steps_since_event_observation)
        request = baseline_due or eligible_event
        allowed = request and (self.cap is None or self.used < self.cap)
        self.requests += int(request)
        self.denied += int(request and not allowed)
        # If both are due, mark event so the experiment counts a
        # genuinely event-coincident baseline tick separately;
        # the event is EXTRACONTRIBUTORY only when baseline_due is false.
        reason = ("baseline_and_event" if baseline_due and eligible_event else
                  "baseline" if baseline_due else
                  "event" if eligible_event else "not_due")
        if request and not allowed:
            reason = "budget_exhausted"
        decision = {
            "observation_requested": bool(request),
            "observation_granted": bool(allowed),
            "observation_score": baseline_score,
            "observation_position": tuple(position),
            "event_reason": reason,
        }
        self._next_scan_reason = reason if allowed else None
        self.decisions.append({
            "step":step, "baseline_due":bool(baseline_due),
            "pending_blocked":bool(self._blocked_pending),
            "pending_no_route":bool(self._no_route_pending),
            "eligible_event": bool(eligible_event), "requested":bool(request),
            "granted":bool(allowed), "reason":reason,
            "observed_count_before":self.used,
        })
        return decision

    def refresh(self, observation, step):
        observation = np.asarray(observation, dtype=np.int8)
        before = self.memory.grid.copy()
        visible = observation >= 0
        self.base.refresh(observation, int(step))
        changes = int(np.count_nonzero(visible & (before != observation)))
        unknown_new = int(np.count_nonzero(visible & (before == -1)))
        reason = self._next_scan_reason
        if reason is None:
            raise RuntimeError("Unauthorized event policy memory refresh")
        self.observation_log.append({
            "step":int(step),"reason":reason,"changed_cells":changes,
            "newly_known_cells":unknown_new,
            "visible_cells":int(np.count_nonzero(visible)),
        })
        if reason in ("event","baseline_and_event"):
            self.event_observation_count += 1
            self.last_event_observation_step = int(step)
        else:
            self.ordinary_observation_count += 1
        self._blocked_pending = False
        self._no_route_pending = False
        self.last_observation_step = int(step)
        self._next_scan_reason = None
