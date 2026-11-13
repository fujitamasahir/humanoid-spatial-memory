"""RDAO v2.2 experimental: decision-protected CURRENT-view quality.

Frozen one-variable hypothesis relative to v2 viewpoint:
discount partially-covered current-view candidates ONLY if observing
them cannot change the immediately chosen G1 action under v1's already
computed public-map free/occupied route counterfactual.

Protect first-action changes and reachability changes at full v2 score.
No fitted world-specific steps, outcome labels, oracle, shadow sensor,
future sensor values or hidden geometry. The original planner, 20-scan
cap, next-view competition and true-geometry action shield are unchanged.

Like all RDAO v2 modules this is an opt-in, single-threaded
development candidate, NOT a validated policy or hardware controller.
"""
from __future__ import annotations

import numpy as np

from .rdao_v2 import RDAOv2ViewpointController, viewpoint_quality_public


def protects_immediate_route_decision(counterfactual: dict) -> bool:
    """Decision-critical observations are NOT discounted for view quality.

    Uses only the existing v1 free/occupied observed-map A* results.
    A hypothetical newly occupied region that changes reachability
    or the next nominal action cannot be safely dismissed based on FOV.
    """
    if counterfactual.get("first_action_changes", False):
        return True
    free = counterfactual.get("free_reachable")
    occupied = counterfactual.get("occupied_reachable")
    return free is not None and occupied is not None and bool(free) != bool(occupied)


class RDAOv22DecisionProtectedController(RDAOv2ViewpointController):
    """Preserve urgent decisions while downweighting low-quality edge scans."""

    def _candidate_scores(self, step, position, yaw, nominal_route, planning_ns):
        positions, results, _best, planning_ns = super()._candidate_scores(
            step, position, yaw, nominal_route, planning_ns)
        kwargs = dict(
            cell_size_m=self.cell_size_m, range_m=self.range_m,
            horizontal_fov_deg=self.horizontal_fov_deg,
            ray_count=self.ray_count,
            unknown_open_probability=(
                self.parameters.unknown_blocker_open_probability))
        for item in results:
            cf = item.get("counterfactual") or {}
            protected = protects_immediate_route_decision(cf)
            item["v22_protected_immediate_decision"] = protected
            item["v22_current_view_discount"] = 1.0
            item["v22_base_score_after_lookahead"] = float(item["score"])
            if protected or not self.use_visibility:
                continue
            visibility = float(item.get("visibility") or 0.0)
            if visibility <= 0:
                continue
            cells = item.get("cells") or []
            if not cells:
                continue
            quality = item.get("v2_current_view_quality")
            if quality is None:
                quality = float(np.mean([
                    viewpoint_quality_public(
                        self.memory.grid, position, yaw, cell, **kwargs)
                    for cell in cells]))
            # Angular coverage is in [0,1]; preserve v2's already
            # computed next-viewpoint deferral and multiply only
            # noncritical current-view region scores.
            weight = min(1.0, max(0.0, float(quality) / visibility))
            item["v22_current_view_discount"] = weight
            item["score"] = float(item["score"]) * weight
        best = max(results, key=lambda item: (
            item["score"], tuple(item["region"]))) if results else None
        return positions, results, best, planning_ns
