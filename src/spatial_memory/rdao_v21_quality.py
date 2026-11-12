"""Opt-in RDAO v2.1: current-view quality as well as next-view quality.

One change relative to RDAOv2ViewpointController: the CURRENT viewpoint's
region visibility score is weighted by angular cell coverage, not binary
centerline-corrected visibility alone. The same public angular-coverage
heuristic already used for v2's next-view calculation is reused here.

The hypothesis: avoid low-quality FOV-edge scans without making the
next-view deferral more aggressive or changing the original budget-adjusted
threshold. This can LOSE valuable scans and is not assumed to improve
success. Full fitted-development evaluation and then independent worlds
are required.

Public ternary memory, nominal route, public pose/yaw only. No latent
world geometry, shadow sensing, step/world allowlists or controller
alteration to true-G1 actions. The default v1/v2 are unchanged.
"""
from __future__ import annotations

from . import rdao as rdao_module
from .rdao import RDAOController
from .rdao_v2 import RDAOv2ViewpointController, viewpoint_quality_public


class RDAOv21CurrentQualityController(RDAOv2ViewpointController):
    """Replace ONLY candidate region current visibility with view quality.

    The v2 next-view competition and all other inherited v1 logic run
    unchanged. Scoped global visibility hook is single-threaded only.
    """

    def _regions(self, step, position, yaw, nominal_route):
        original = rdao_module.predicted_cell_visibility
        if original is viewpoint_quality_public:
            raise RuntimeError("Unexpected nested v2.1 quality override")
        rdao_module.predicted_cell_visibility = viewpoint_quality_public
        try:
            # Call the original v1 implementation DIRECTLY: v2._regions
            # intentionally swaps to bare footprint feasibility and would
            # otherwise negate the one-variable current-quality ablation.
            return RDAOController._regions(
                self, step, position, yaw, nominal_route)
        finally:
            rdao_module.predicted_cell_visibility = original
