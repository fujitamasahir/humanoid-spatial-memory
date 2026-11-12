"""Public synthetic regression tests for RDAO v2.1 angular scan quality."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"src"), str(ROOT/"scripts")]

from spatial_memory import rdao as rdao_module
from spatial_memory.rdao import RDAOController
from spatial_memory.rdao_v2 import (
    RDAOv2ViewpointController, footprint_visibility_public,
    viewpoint_quality_public,
)
from spatial_memory.rdao_v21_quality import RDAOv21CurrentQualityController


def agent(grid, cls):
    return cls(grid, goal=(7, 7), max_observations=20,
               local_extents=(0., 0.), cell_size_m=.75)


def test_angular_quality_is_bounded_by_footprint_visibility():
    grid = np.zeros((16, 16), dtype=np.int8)
    target = (5, 7)
    kwargs = dict(cell_size_m=.75, range_m=6.,
                  horizontal_fov_deg=120., ray_count=61,
                  unknown_open_probability=.5)
    for yaw in (0., math.pi/2, math.pi, -math.pi/2):
        base = footprint_visibility_public(
            grid, (3, 3), yaw, target, **kwargs)
        quality = viewpoint_quality_public(
            grid, (3, 3), yaw, target, **kwargs)
        assert 0. <= quality <= base


def test_v21_region_score_uses_quality_when_v2_uses_binary_feasibility():
    grid = np.zeros((16, 16), dtype=np.int8)
    grid[7, 5] = -1
    v2, v21 = agent(grid, RDAOv2ViewpointController), agent(
        grid, RDAOv21CurrentQualityController)
    route = [("turn", 1), ("move", (4, 6)), ("move", (4, 7)),
             ("turn", 0), ("move", (5, 7))]
    _, a = v2._regions(6, (4, 5), 0., route)
    _, b = v21._regions(6, (4, 5), 0., route)
    def candidate_visibility(regions):
        return [vis for _, _, cells in regions
                for cell, vis, unc, index in cells
                if cell == (5, 7)]
    av, bv = candidate_visibility(a), candidate_visibility(b)
    assert av and bv
    assert 0 < bv[0] < av[0]
    assert rdao_module.predicted_cell_visibility is not (
        viewpoint_quality_public)


def test_v21_retains_same_next_viewopportunity_and_budget_params():
    grid = np.zeros((12, 12), dtype=np.int8)
    grid[6, 5] = -1
    a = agent(grid, RDAOv21CurrentQualityController)
    b = agent(grid, RDAOv2ViewpointController)
    assert a.parameters == b.parameters
    assert a.cap == b.cap == 20
    assert a.unknown == b.unknown
    assert a.use_route_relevance and b.use_route_relevance
    assert a.use_timing and b.use_timing


def test_v21_restores_visibility_hook_on_exception(monkeypatch):
    grid = np.zeros((12, 12), dtype=np.int8)
    c = agent(grid, RDAOv21CurrentQualityController)
    original = rdao_module.predicted_cell_visibility

    def unexpected(*args, **kwargs):
        assert rdao_module.predicted_cell_visibility is (
            viewpoint_quality_public)
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(RDAOController, "_regions", unexpected)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        c._regions(3, (4, 4), 0., [])
    assert rdao_module.predicted_cell_visibility is original


def test_v21_decide_uses_original_rdao_observation_interfaces():
    grid = np.zeros((9, 9), dtype=np.int8)
    grid[4, 3] = -1
    c = agent(grid, RDAOv21CurrentQualityController)
    c.set_context(1, (1, 4), 0.)
    before = c.memory.grid.copy()
    obs = c.decide(1, (1, 4))
    assert obs["observation_requested"] in (True, False)
    assert obs["observation_granted"] in (True, False)
    assert np.array_equal(c.memory.grid, before)
    assert obs["rdao"]["remaining_observation_budget"] == 19
    assert rdao_module.predicted_cell_visibility is not (
        viewpoint_quality_public)
