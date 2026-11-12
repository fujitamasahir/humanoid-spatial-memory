"""Fast intervention contract checks, using no MuJoCo scene or held-out worlds."""
import copy
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_rdao_one_shot_interventions import (
    InterventionRDAO, _compare_trace, _first_difference,
)
from spatial_memory.rdao import RDAOController


def _agent():
    grid = np.zeros((9, 9), dtype=np.int8)
    return InterventionRDAO(
        grid, goal=(7, 4), max_observations=20,
        local_extents=(0., 0.), cell_size_m=.75)


def _scripted_original(self, step, position):
    """Simulate a reject at step 2, then a natural accept at step 3."""
    accepted = step == 3
    if accepted:
        self.requests += 1
        self.region_last_attempted[(1, 1)] = step
    diagnostic = {
        "step": step, "nominal_route": [("move", (2, 4))],
        "requested": accepted, "granted": accepted,
        "reason": "natural_accept" if accepted else "low_score",
        "score": .3 if accepted else .1, "threshold": .2,
    }
    if accepted:
        diagnostic["_pre_observation"] = {"placeholder": True}
    self.latest_diagnostic = diagnostic
    return {
        "observation_requested": accepted,
        "observation_granted": accepted,
        "observation_score": diagnostic["score"],
        "observation_position": position,
        "rdao": diagnostic,
    }


def test_force_a_rejected_observation_uses_original_refresh_contract(monkeypatch):
    monkeypatch.setattr(RDAOController, "decide", _scripted_original)
    monkeypatch.setattr(InterventionRDAO, "force_step", 2)
    monkeypatch.setattr(InterventionRDAO, "variant", "extra")
    agent = _agent()
    agent.set_context(2, (1, 4), 0.)
    result = agent.decide(2, (1, 4))
    assert result["observation_granted"]
    assert result["rdao"]["intervention_forced"]
    assert "_pre_observation" in result["rdao"]
    assert agent.requests == 1
    assert agent.used == 1  # decide does not grant actual sensing until refresh
    observation = np.full(agent.memory.grid.shape, -1, dtype=np.int8)
    observation[4, 2] = 0
    agent.refresh(observation, 2)
    assert agent.used == 2
    assert result["rdao"]["observation_effect"] is not None
    assert result["rdao"]["observation_effect"]["memory_changed_cell_count"] == 0


def test_swap_suppresses_only_one_subsequent_natural_request(monkeypatch):
    monkeypatch.setattr(RDAOController, "decide", _scripted_original)
    monkeypatch.setattr(InterventionRDAO, "force_step", 2)
    monkeypatch.setattr(InterventionRDAO, "variant", "swap")
    agent = _agent()
    agent.set_context(2, (1, 4), 0.)
    assert agent.decide(2, (1, 4))["observation_granted"]
    result = agent.decide(3, (1, 4))
    assert not result["observation_granted"]
    assert result["rdao"]["intervention_suppressed"]
    assert "_pre_observation" not in result["rdao"]
    assert agent.requests == 1
    assert not agent.region_last_attempted
    assert agent.suppressed_next


def test_originally_granted_step_cannot_be_forced_again(monkeypatch):
    monkeypatch.setattr(RDAOController, "decide", _scripted_original)
    monkeypatch.setattr(InterventionRDAO, "force_step", 3)
    monkeypatch.setattr(InterventionRDAO, "variant", "extra")
    agent = _agent()
    with pytest.raises(RuntimeError, match="originally rejected"):
        agent.decide(3, (1, 4))


def test_replay_exact_prefix_and_behavioral_divergence():
    saved = {"steps": [
        {"step": 0, "position": [1, 4], "action": None},
        {"step": 1, "position": [2, 4], "action": ["move", [2, 4]]},
        {"step": 2, "position": [3, 4], "action": ["move", [3, 4]]},
    ]}
    changed = copy.deepcopy(saved)
    changed["steps"][2]["action"] = ["turn", 1]
    _compare_trace(saved, changed, before_step=2)
    assert _first_difference(saved, changed) == 2
    with pytest.raises(RuntimeError, match="behavior mismatch"):
        _compare_trace(saved, changed)
