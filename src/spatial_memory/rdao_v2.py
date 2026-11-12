"""Experimental RDAO v2: public-map next-viewpoint observation competition.

Opt-in DEVELOPMENT controller, not a validated policy. Combines the
footprint-extent visibility candidate with one-step observation opportunity
preservation. Postpone scanning a region when the same uncertain cells are
likely significantly better-covered after the FIRST nominal public-map G1 action.

No oracle geometry, shadow raycasts, episode-specific steps/identities,
future sensor returns or special movement privileges. G1 planning,
emergency sensor, selected-action shield, observation cap,
budget price and region relevance remain unchanged.

Relative to v1: (1) region visibility uses cell footprint extent;
(2) a region's decision score is conservatively reduced when the NEXT
nominal pose offers a materially better view without entering an unknown
cell. This hypothetical next pose is NOT guaranteed by actual safety shield.
Constants represent a frozen development hypothesis, not fitted world rules.
"""
from __future__ import annotations

import math

import numpy as np

from . import rdao as rdao_module
from .navigation import HEADINGS
from .observation import line_cells
from .rdao import RDAOController, _wrap_angle

HALF_CELL_DIAGONAL = math.sqrt(2.0) / 2.0
MIN_RELATIVE_GAIN = 1.25
MIN_ABSOLUTE_GAIN = 0.10
DEFER_SCORE_MULTIPLIER = 0.50


def footprint_visibility_public(grid, position, yaw, cell, *,
                                cell_size_m, range_m, horizontal_fov_deg,
                                ray_count, unknown_open_probability=.5):
    """Same public-map extent approximation as frozen offline audit.

    Scores geometric feasibility and remembered-line attenuation, NOT
    calibrated sensor hit probabilities. No hidden occupancy is queried.
    """
    cx, cy = map(int, cell)
    px, py = map(int, position)
    if not (0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1]):
        return 0.0
    dx, dy = cx - px, cy - py
    distance = math.hypot(dx, dy) * cell_size_m
    if distance <= 1e-12:
        return 0.0
    radius = cell_size_m * HALF_CELL_DIAGONAL
    if distance - radius > range_m:
        return 0.0
    extent = math.atan2(radius, max(distance, cell_size_m * .25))
    rel = _wrap_angle(math.atan2(dy, dx) - float(yaw))
    half_fov = math.radians(horizontal_fov_deg) / 2.0
    if abs(rel) > half_fov + extent:
        return 0.0
    ray_step = 2.0 * half_fov / max(1, ray_count - 1)
    nearest = max(0, min(ray_count - 1, round((rel + half_fov) / ray_step)))
    ray_angle = -half_fov + nearest * ray_step
    if abs(rel - ray_angle) > extent + ray_step / 2.0:
        return 0.0
    confidence = 1.0
    origin = (px, py)
    for bx, by in line_cells(origin, (cx, cy)):
        if (bx, by) == origin or (bx, by) == (cx, cy):
            continue
        if not (0 <= by < grid.shape[0] and 0 <= bx < grid.shape[1]):
            return 0.0
        value = int(grid[by, bx])
        if value == 1:
            return 0.0
        if value == -1:
            confidence *= unknown_open_probability
    return float(confidence)


def viewpoint_quality_public(grid, position, yaw, cell, *,
                             cell_size_m, range_m, horizontal_fov_deg,
                             ray_count, unknown_open_probability=.5):
    """Public-map visibility feasibility times angular sensor-coverage proxy.

    The base footprint score is almost binary in angle: rotating in place
    would otherwise NEVER improve a currently visible cell's predicted
    score. Multiply by an explicit conservative FOV-edge margin from 0 to 1,
    estimating how fully a cell's angular extent is within the sensor cone.
    This is a HEURISTIC geometric quality, not calibrated hit probability.
    """
    visible = footprint_visibility_public(
        grid, position, yaw, cell, cell_size_m=cell_size_m,
        range_m=range_m, horizontal_fov_deg=horizontal_fov_deg,
        ray_count=ray_count,
        unknown_open_probability=unknown_open_probability)
    if visible <= 0:
        return 0.0
    dx, dy = int(cell[0])-int(position[0]), int(cell[1])-int(position[1])
    dist = math.hypot(dx, dy) * cell_size_m
    extent = math.atan2(cell_size_m*HALF_CELL_DIAGONAL,
                        max(dist, cell_size_m*.25))
    half = math.radians(horizontal_fov_deg)/2.0
    relative = abs(_wrap_angle(math.atan2(dy, dx)-float(yaw)))
    angular_coverage = max(0.0, min(
        1.0, (half + extent - relative) / max(2*extent, 1e-12)))
    return visible * angular_coverage

def next_public_viewpoint(grid, position, yaw, route):
    """One hypothetical public route action; not a real-world oracle check.

    Before translating into a possibly blocked UNKNOWN cell, do NOT defer.
    Turns are candidates using public 4-heading convention.
    """
    if not route:
        return None
    action, value = route[0]
    pos = tuple(map(int, position))
    if action == "turn":
        return pos, float(HEADINGS[int(value) % 4]), "turn"
    if action == "move":
        x, y = map(int, value)
        if not (0 <= y < grid.shape[0] and 0 <= x < grid.shape[1]):
            return None
        if int(grid[y, x]) != 0:
            return None
        return (x, y), float(yaw), "move_known_free"
    return None


class RDAOv2ViewpointController(RDAOController):
    """Experimental public-memory v2 controller retaining v1 safety API.

    Only observation scoring changes. Run single-threaded: the inherited
    RDAO module uses a function-level visibility hook.
    """

    def _regions(self, step, position, yaw, nominal_route):
        original = rdao_module.predicted_cell_visibility
        if original is footprint_visibility_public:
            raise RuntimeError("Unexpected nested v2 visibility override")
        rdao_module.predicted_cell_visibility = footprint_visibility_public
        try:
            return super()._regions(step, position, yaw, nominal_route)
        finally:
            rdao_module.predicted_cell_visibility = original

    def _candidate_scores(self, step, position, yaw, nominal_route, planning_ns):
        positions, results, _best, planning_ns = super()._candidate_scores(
            step, position, yaw, nominal_route, planning_ns)
        next_view = next_public_viewpoint(
            self.memory.grid, position, yaw, nominal_route)
        for item in results:
            item["v2_base_score"] = float(item["score"])
            item["v2_next_visibility"] = None
            item["v2_current_view_quality"] = None
            item["v2_next_view_quality"] = None
            item["v2_deferred"] = False
            item["v2_next_view_action"] = next_view[2] if next_view else None
            if next_view is None:
                continue
            future_pos, future_yaw, _ = next_view
            cells = item["cells"]
            if not cells or float(item["visibility"]) <= 0.0:
                continue
            kwargs = dict(
                cell_size_m=self.cell_size_m, range_m=self.range_m,
                horizontal_fov_deg=self.horizontal_fov_deg,
                ray_count=self.ray_count,
                unknown_open_probability=(
                    self.parameters.unknown_blocker_open_probability))
            now = float(np.mean([
                viewpoint_quality_public(
                    self.memory.grid, position, yaw, cell, **kwargs)
                for cell in cells
            ]))
            predicted_next = float(np.mean([
                viewpoint_quality_public(
                    self.memory.grid, future_pos, future_yaw, cell, **kwargs)
                for cell in cells
            ]))
            item["v2_current_view_quality"] = now
            item["v2_next_view_quality"] = predicted_next
            item["v2_next_visibility"] = predicted_next
            if (predicted_next >= now * MIN_RELATIVE_GAIN and
                    predicted_next - now >= MIN_ABSOLUTE_GAIN):
                item["score"] = float(item["score"]) * DEFER_SCORE_MULTIPLIER
                item["v2_deferred"] = True
        best = max(results, key=lambda item: (
            item["score"], tuple(item["region"]))) if results else None
        return positions, results, best, planning_ns
