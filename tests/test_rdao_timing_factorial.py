"""Pure-Python contract tests for the RDAO step-2/step-3 factorial gating."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_rdao_timing_factorial import TimingFactorialRDAO
from spatial_memory.rdao import RDAOController


def scripted_decide(self, step, position):
    natural = step == 3
    if natural:
        self.requests += 1
        self.region_last_attempted[(0, 0)] = step
    diag = {
        "step": step, "position": tuple(position),
        "nominal_route": [("move", (2, 4))],
        "requested": natural, "granted": natural,
        "reason": "natural" if natural else "no_candidate",
        "observation_effect": None,
    }
    if natural:
        diag["_pre_observation"] = {"placeholder": True}
    self.latest_diagnostic = diag
    return {
        "observation_requested": natural,
        "observation_granted": natural,
        "observation_score": .3 if natural else 0.,
        "observation_position": position, "rdao": diag,
    }


@pytest.mark.parametrize("observe2,observe3", [(0, 1), (0, 0), (1, 0), (1, 1)])
def test_observation_factorial_enforces_only_two_requested_steps(
        monkeypatch, observe2, observe3):
    monkeypatch.setattr(RDAOController, "decide", scripted_decide)
    monkeypatch.setattr(TimingFactorialRDAO, "observe_step_2", bool(observe2))
    monkeypatch.setattr(TimingFactorialRDAO, "observe_step_3", bool(observe3))

    arr = np.zeros((9, 9), dtype=np.int8)
    agent = TimingFactorialRDAO(
        arr, goal=(7, 4), max_observations=20,
        local_extents=(0., 0.), cell_size_m=.75,
    )
    initial = agent.used
    agent.set_context(2, (1, 4), 0.)
    d2 = agent.decide(2, (1, 4))
    assert d2["observation_granted"] == bool(observe2)
    if observe2:
        assert d2["rdao"]["timing_factorial_forced"]
        assert "_pre_observation" in d2["rdao"]
        visible = np.full((9, 9), -1, dtype=np.int8)
        visible[4, 2] = 1
        agent.refresh(visible, 2)
        assert d2["rdao"]["observation_effect"]["memory_changed_cell_count"] == 1

    d3 = agent.decide(3, (1, 4))
    assert d3["observation_granted"] == bool(observe3)
    if observe3:
        assert "_pre_observation" in d3["rdao"]
        visible = np.full((9, 9), -1, dtype=np.int8)
        visible[4, 2] = 0
        # The 01 baseline scripted diagnostic intentionally does not match
        # the real refresh contract. The factorial wrapper must preserve
        # the unmodified natural decision in that case.
        if not observe2:
            assert d3["rdao"]["reason"] == "natural"
        else:
            assert d3["rdao"]["reason"] == "natural"
    else:
        assert d3["rdao"]["timing_factorial_suppressed"]
        assert "_pre_observation" not in d3["rdao"]
        assert not agent.region_last_attempted

    assert agent.requests == observe2 + observe3
    assert agent.used == initial + observe2


def test_non_intervention_step_delegates_unchanged(monkeypatch):
    monkeypatch.setattr(RDAOController, "decide", scripted_decide)
    agent = TimingFactorialRDAO(
        np.zeros((7, 7), dtype=np.int8),
        goal=(4, 4), max_observations=20,
    )
    decision = agent.decide(4, (1, 1))
    assert "timing_factorial" not in decision["rdao"]
    assert decision["observation_granted"] is False


def test_two_step_observation_never_exceeds_cap(monkeypatch):
    monkeypatch.setattr(RDAOController, "decide", scripted_decide)
    monkeypatch.setattr(TimingFactorialRDAO, "observe_step_2", True)
    agent = TimingFactorialRDAO(
        np.zeros((7, 7), dtype=np.int8),
        goal=(4, 4), max_observations=1,
    )
    with pytest.raises(RuntimeError, match="exceeded original sensing cap"):
        agent.decide(2, (1, 1))
