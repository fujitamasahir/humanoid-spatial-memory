"""Grid observations produced by MuJoCo ray intersections, not occupancy truth."""
import math

import numpy as np

from .mujoco_navigation import G1_FORWARD_AXIS


# Scene boxes use half width 0.505 cell while raster-cell boundaries are at
# 0.5 cell. A measured box face can therefore fall 0.005 cell into its
# neighbor. Snap only points within that explicit overlap tolerance, and only
# toward the ray's measured direction of travel.
BOX_BOUNDARY_OVERLAP_CELLS = 0.505 - 0.5


class MujocoRayPerception:
    """Deterministic horizontal ray sensor attached to the G1 torso site.

    The backend sees the evaluator-owned MuJoCo model only to raycast its
    collision/render geometry. Navigation receives only the ternary array
    returned by :meth:`observe`; hit categories are retained as evaluator
    diagnostics in ``last_stats`` and never included in that array.
    """

    def __init__(self, scene, *, range_m=6.0, horizontal_fov_deg=120.0,
                 ray_count=61, sample_spacing_m=0.075):
        values = (range_m, horizontal_fov_deg, sample_spacing_m)
        if not all(math.isfinite(v) and v > 0 for v in values):
            raise ValueError('range, FOV, and sample spacing must be positive and finite')
        if horizontal_fov_deg > 360 or type(ray_count) is not int or ray_count < 2:
            raise ValueError('FOV must be <=360 degrees and ray_count must be >=2')
        self.scene = scene
        self.range_m = float(range_m)
        self.horizontal_fov_deg = float(horizontal_fov_deg)
        self.ray_count = ray_count
        self.sample_spacing_m = float(sample_spacing_m)
        self.geom_groups = np.zeros(6, dtype=np.uint8)
        self.geom_groups[5] = 1
        self.last_stats = {}

    def observe(self, world, position, heading_yaw):
        """Sync evaluator-owned geometry, then return only what rays observe."""
        scene = self.scene
        scene._sync_environment(world)
        scene._set_pose(position, heading_yaw)
        scene.mj.mj_forward(scene.model, scene.data)
        return self.observe_current()

    def observe_current(self):
        scene, mj = self.scene, self.scene.mj
        model, data = scene.model, scene.data
        origin = np.asarray(data.site_xpos[scene.sensor_site_id], dtype=np.float64).copy()
        site_matrix = np.asarray(data.site_xmat[scene.sensor_site_id], dtype=np.float64).reshape(3, 3)
        # MuJoCo site matrices are applied to local axes; local +X is the
        # anterior axis verified for the supplied Unitree G1 MJCF.
        forward = site_matrix @ np.asarray(G1_FORWARD_AXIS)
        left = site_matrix @ np.asarray((0.0, 1.0, 0.0))
        forward[2] = 0.0
        left[2] = 0.0
        forward /= np.linalg.norm(forward)
        left /= np.linalg.norm(left)
        shape = (scene.scenario.height, scene.scenario.width)
        observation = np.full(shape, -1, dtype=np.int8)
        free_cells, occupied_cells = set(), set()
        hits_by_type = dict(walls=0, persistent_obstacles=0, pedestrians=0)
        angles = np.linspace(-math.radians(self.horizontal_fov_deg)/2,
                             math.radians(self.horizontal_fov_deg)/2,
                             self.ray_count)
        geom_id = np.full(1, -1, dtype=np.int32)
        cells_by_ray = []
        hit_count = 0
        visible_pedestrian_cells = set()
        visible_persistent_obstacle_cells = set()

        for offset in angles:
            direction = forward*math.cos(offset) + left*math.sin(offset)
            direction[2] = 0.0
            direction /= np.linalg.norm(direction)
            distance = float(mj.mj_ray(model, data, origin, direction, self.geom_groups,
                                       True, scene.robot_body, geom_id))
            hit = distance >= 0 and distance <= self.range_m
            visible_distance = self.range_m if distance < 0 else min(distance, self.range_m)
            ray_cells = []
            steps = max(1, math.ceil(visible_distance/self.sample_spacing_m))
            for step in range(steps+1):
                ray_distance = min(step*self.sample_spacing_m, visible_distance)
                # A first-hit endpoint is not free space. The start point and
                # measured samples strictly before that endpoint remain free.
                if hit and ray_distance >= distance - 1e-10:
                    continue
                point = origin + direction*ray_distance
                cell = scene.world_to_grid(point[:2])
                x, y = cell
                if 0 <= x < scene.scenario.width and 0 <= y < scene.scenario.height:
                    ray_cells.append(cell)
                    free_cells.add(cell)
            if hit:
                hit_count += 1
                hit_geom = int(geom_id[0])
                # Map only the measured first-hit surface point. Geometry
                # centers are privileged simulator state and can lie behind
                # the visible boundary (or outside the ray's observed path).
                surface = origin + direction * distance
                cell = self._surface_cell(surface[:2], direction[:2])
                x, y = cell
                if 0 <= x < scene.scenario.width and 0 <= y < scene.scenario.height:
                    occupied_cells.add(cell)
                if hit_geom in scene._wall_geom_ids:
                    hits_by_type['walls'] += 1
                elif hit_geom in scene._object_geom_ids.values():
                    hits_by_type['persistent_obstacles'] += 1
                    if 0 <= x < scene.scenario.width and 0 <= y < scene.scenario.height:
                        visible_persistent_obstacle_cells.add((x, y))
                elif hit_geom in scene._ped_geom_ids:
                    hits_by_type['pedestrians'] += 1
                    if 0 <= x < scene.scenario.width and 0 <= y < scene.scenario.height:
                        visible_pedestrian_cells.add((x, y))
            cells_by_ray.append(ray_cells)

        # A cell containing any measured first-hit surface is conservatively
        # occupied: a free ray through another part of the 0.75 m cell does not
        # establish that the whole cell is clear. Boundary snapping above keeps
        # box faces from falsely assigning that hit to the adjacent free cell.
        conflicts = free_cells & occupied_cells
        for x, y in free_cells - conflicts:
            observation[y, x] = 0
        for x, y in occupied_cells:
            observation[y, x] = 1
        self.last_stats = dict(
            ray_count=self.ray_count, ray_hits=hit_count, hits_by_type=hits_by_type,
            visible_cells=len(free_cells | occupied_cells), free_cells=len(free_cells-occupied_cells),
            occupied_cells=len(occupied_cells-conflicts), conflicting_cells=len(conflicts),
            occupied_boundary_overlap_cells=BOX_BOUNDARY_OVERLAP_CELLS, range_m=self.range_m,
            horizontal_fov_deg=self.horizontal_fov_deg,
            sensor_origin_world=origin.tolist(), sensor_height_m=float(origin[2]),
            visible_cells_by_ray=[len(cells) for cells in cells_by_ray],
            visible_pedestrian_cells=sorted(map(list, visible_pedestrian_cells)),
            visible_persistent_obstacle_cells=sorted(map(list, visible_persistent_obstacle_cells)))
        return observation

    def _surface_cell(self, point, direction):
        """Rasterize a measured surface, accounting for the documented box edge overlap."""
        scene = self.scene
        values = (point[0]/scene.cell_size+(scene.scenario.width-1)/2,
                  point[1]/scene.cell_size+(scene.scenario.height-1)/2)
        result = []
        for value, component in zip(values, direction):
            lower = math.floor(value)
            boundary = lower + 0.5
            if abs(value-boundary) <= BOX_BOUNDARY_OVERLAP_CELLS + 1e-10:
                # Resolve the 0.005-cell collision-box overhang to the cell
                # containing the obstacle, using only the ray's approach side.
                result.append(lower+1 if component > 0 else lower if component < 0
                              else math.floor(value+0.5+1e-12))
            else:
                result.append(math.floor(value+0.5+1e-12))
        return tuple(result)
