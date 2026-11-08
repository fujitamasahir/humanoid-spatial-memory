"""MuJoCo adapter for kinematic navigation with the pinned Unitree G1 MJCF."""
from dataclasses import dataclass
import math
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
G1_XML = REPOSITORY_ROOT / 'third_party' / 'unitree_g1' / 'g1.xml'
G1_FORWARD_AXIS = (1.0, 0.0, 0.0)  # Unitree MJCF body convention: local +X is anterior.


def yaw_quaternion(yaw):
    """MuJoCo free-joint quaternion (w, x, y, z) for a world-Z yaw."""
    return (math.cos(yaw/2), 0.0, 0.0, math.sin(yaw/2))


def desired_heading(start, target, cell_size=1.0):
    """Yaw that turns the G1 local +X forward axis toward a grid displacement."""
    dx = (target[0]-start[0])*cell_size
    dy = (target[1]-start[1])*cell_size
    if dx == 0 and dy == 0:
        return None
    return math.atan2(dy, dx)


def angle_delta(target, current):
    return (target-current+math.pi) % (2*math.pi)-math.pi


@dataclass(frozen=True)
class ContactCounts:
    foot_floor: int = 0
    unwanted_floor: int = 0
    pedestrian: int = 0
    wall: int = 0
    persistent_obstacle: int = 0
    robot_self: int = 0

    @property
    def environmental(self):
        return self.unwanted_floor + self.pedestrian + self.wall + self.persistent_obstacle + self.robot_self


class MujocoNavigationScene:
    """Actual G1, stationary at its ``stand`` joint pose and moved kinematically."""

    def __init__(self, scenario, *, cell_size=0.75, timestep=0.02):
        if not math.isfinite(cell_size) or cell_size <= 0:
            raise ValueError('cell_size must be positive and finite')
        if not math.isfinite(timestep) or timestep <= 0:
            raise ValueError('timestep must be positive and finite')
        try:
            import mujoco
        except ImportError as error:
            raise RuntimeError('Install the pinned mujoco dependency to run Phase 2') from error
        self.mj, self.scenario = mujoco, scenario
        self.cell_size, self.timestep = float(cell_size), float(timestep)
        self.xml, self._object_names = self._make_xml()
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.model.opt.timestep = self.timestep
        self.data = mujoco.MjData(self.model)
        self.robot_body = self._body_id('pelvis')
        joint_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'floating_base_joint')
        if joint_id < 0:
            raise ValueError('G1 model is missing floating_base_joint')
        self.robot_qpos_adr = int(self.model.jnt_qposadr[joint_id])
        self.robot_qvel_adr = int(self.model.jnt_dofadr[joint_id])
        key_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_KEY, 'stand')
        if key_id < 0:
            raise ValueError('G1 model is missing stand keyframe')
        self.stand_key_id = int(key_id)
        mujoco.mj_resetDataKeyframe(self.model, self.data, self.stand_key_id)
        self._stand_root = self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7].copy()
        self.pedestrian_bodies = [self._body_id(f'pedestrian_{i}') for i in range(len(scenario.pedestrians))]
        self.pedestrian_mocaps = [int(self.model.body_mocapid[i]) for i in self.pedestrian_bodies]
        self._wall_geom_ids = {self._geom_id(f'wall_{x}_{y}') for x, y in scenario.walls}
        self._object_geom_ids = {cell: self._geom_id(f'object_geom_{cell[0]}_{cell[1]}')
                                 for cell in self._object_names}
        self._object_mocaps = {cell: int(self.model.body_mocapid[self._body_id(name)])
                               for cell, name in self._object_names.items()}
        self._robot_geom_ids = {i for i in range(self.model.ngeom)
                                if self._is_descendant(int(self.model.geom_bodyid[i]), self.robot_body)
                                and int(self.model.geom_contype[i]) != 0}
        self._foot_geom_ids = {i for i in self._robot_geom_ids if self._is_intended_foot(i)}
        self._ped_geom_ids = {i for body in self.pedestrian_bodies for i in range(self.model.ngeom)
                              if int(self.model.geom_bodyid[i]) == body}
        self._floor_geom_id = self._geom_id('floor')
        self.sensor_site_id = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE,
                                                'g1_ray_sensor')
        if self.sensor_site_id < 0:
            raise ValueError('Missing G1-attached ray sensor site')
        self._last_snapshot = None
        self.heading_yaw = 0.0
        self._set_pose(scenario.start, self.heading_yaw)
        self.mj.mj_forward(self.model, self.data)
        self.footprint_half_extents_local = self._measure_footprint_half_extents()

    def _measure_footprint_half_extents(self):
        """Conservative local X/Y bounds from public G1 collision geoms only."""
        root = self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+2].copy()
        extents = [0.0, 0.0]
        for geom in self._robot_geom_ids:
            kind = int(self.model.geom_type[geom])
            size = np.asarray(self.model.geom_size[geom], dtype=float)
            rotation = np.asarray(self.data.geom_xmat[geom]).reshape(3, 3)
            center = np.asarray(self.data.geom_xpos[geom, :2])-root
            for axis_index, axis in enumerate((np.array([1., 0., 0.]),
                                                np.array([0., 1., 0.]))):
                local_axis = rotation.T @ axis
                if kind == int(self.mj.mjtGeom.mjGEOM_BOX):
                    support = float(np.sum(np.abs(local_axis)*size[:3]))
                elif kind == int(self.mj.mjtGeom.mjGEOM_SPHERE):
                    support = float(size[0])
                elif kind in (int(self.mj.mjtGeom.mjGEOM_CAPSULE),
                              int(self.mj.mjtGeom.mjGEOM_CYLINDER)):
                    support = float(size[0]*np.hypot(local_axis[0], local_axis[1])
                                    + size[1]*abs(local_axis[2]))
                elif kind == int(self.mj.mjtGeom.mjGEOM_ELLIPSOID):
                    support = float(np.sqrt(np.sum((local_axis*size[:3])**2)))
                else:
                    # Mesh bounding spheres are conservative and part of the
                    # pinned robot model, not environment geometry.
                    support = float(self.model.geom_rbound[geom])
                extents[axis_index] = max(extents[axis_index],
                    abs(float(np.dot(axis[:2], center)))+support)
        return tuple(extents)

    def _make_xml(self):
        if not G1_XML.is_file():
            raise FileNotFoundError(f'Missing pinned Unitree G1 MJCF: {G1_XML}')
        root = ET.parse(G1_XML).getroot()
        root.set('model', 'phase2_unitree_g1_kinematic_navigation')
        compiler = root.find('compiler')
        compiler.set('meshdir', str((G1_XML.parent / 'assets').resolve()))
        option = root.find('option')
        option.set('timestep', f'{self.timestep:.6g}')
        worldbody = root.find('worldbody')
        torso = next((body for body in root.iter('body') if body.get('name') == 'torso_link'), None)
        if torso is None:
            raise ValueError('G1 model is missing torso_link for the attached perception site')
        # At stand this places the horizontal ray origin about 0.864 m above
        # the floor: above the ankle, below the 0.9 m obstacle tops.
        ET.SubElement(torso, 'site', name='g1_ray_sensor', pos='0.05 0 0.03', size='0.012',
                      rgba='1 0.8 0.1 1')
        spacing = self.cell_size
        extent_x = max(2.0, self.scenario.width * spacing / 2 + spacing)
        extent_y = max(2.0, self.scenario.height * spacing / 2 + spacing)
        ET.SubElement(worldbody, 'light', name='key', pos='0 -4 8', dir='0 0 -1', diffuse='0.8 0.8 0.8')
        ET.SubElement(worldbody, 'camera', name='overview', pos=f'0 {-extent_y*1.9:.6g} {max(extent_x,extent_y)*1.8:.6g}',
                      xyaxes='1 0 0 0 0.85 0.53', fovy='50')
        ET.SubElement(worldbody, 'geom', name='floor', type='plane', size=f'{extent_x:.6g} {extent_y:.6g} 0.1',
                      rgba='0.78 0.80 0.82 1', contype='1', conaffinity='1')
        half = spacing * 0.505
        for x, y in sorted(self.scenario.walls):
            wx, wy = self.grid_to_world((x, y))
            ET.SubElement(worldbody, 'geom', name=f'wall_{x}_{y}', type='box', pos=f'{wx:.6g} {wy:.6g} 1.25',
                          size=f'{half:.6g} {half:.6g} 1.25', rgba='0.23 0.25 0.29 1', group='5')
        object_cells = set(self.scenario.obstacles)
        object_cells.update(tuple(e['cell']) for e in self.scenario.changes)
        object_cells.update(tuple(e['to']) for e in self.scenario.changes if 'to' in e)
        object_names = {}
        for x, y in sorted(object_cells):
            wx, wy = self.grid_to_world((x, y))
            name = f'object_body_{x}_{y}'
            object_names[(x, y)] = name
            base_z = 0 if (x, y) in self.scenario.obstacles else -1000
            body = ET.SubElement(worldbody, 'body', name=name, mocap='true', pos=f'{wx:.6g} {wy:.6g} {base_z}')
            ET.SubElement(body, 'geom', name=f'object_geom_{x}_{y}', type='box', pos='0 0 0.45',
                          size=f'{half:.6g} {half:.6g} 0.45', rgba='0.65 0.35 0.16 1', contype='1', conaffinity='1', group='5')
        for index in range(len(self.scenario.pedestrians)):
            body = ET.SubElement(worldbody, 'body', name=f'pedestrian_{index}', mocap='true')
            ET.SubElement(body, 'geom', name=f'pedestrian_geom_{index}', type='capsule',
                          fromto='0 0 0.20 0 0 1.28', size='0.19', rgba='0.87 0.28 0.22 1', group='5')
        return ET.tostring(root, encoding='unicode'), object_names

    def grid_to_world(self, cell):
        x, y = cell
        return ((x-(self.scenario.width-1)/2)*self.cell_size,
                (y-(self.scenario.height-1)/2)*self.cell_size)

    def world_to_grid(self, point):
        x, y = point
        # Nearest cell center, with stable half-up handling at exact cell
        # boundaries. MuJoCo ray intersections can differ by a few ulps at a
        # box face; Python's banker's round would otherwise move identical
        # physical boundary points between adjacent raster cells.
        return (math.floor(x/self.cell_size+(self.scenario.width-1)/2+0.5+1e-12),
                math.floor(y/self.cell_size+(self.scenario.height-1)/2+0.5+1e-12))

    def _body_id(self, name):
        result = self.mj.mj_name2id(self.model, self.mj.mjtObj.mjOBJ_BODY, name)
        if result < 0:
            raise ValueError(f'Missing MuJoCo body: {name}')
        return int(result)

    def _geom_id(self, name):
        result = self.mj.mj_name2id(self.model, self.mj.mjtObj.mjOBJ_GEOM, name)
        if result < 0:
            raise ValueError(f'Missing MuJoCo geom: {name}')
        return int(result)

    def _is_descendant(self, body, ancestor):
        while body > 0:
            if body == ancestor:
                return True
            body = int(self.model.body_parentid[body])
        return body == ancestor

    def _is_intended_foot(self, geom):
        body_name = self.mj.mj_id2name(self.model, self.mj.mjtObj.mjOBJ_BODY,
                                       int(self.model.geom_bodyid[geom])) or ''
        return ('ankle_roll_link' in body_name and
                int(self.model.geom_type[geom]) == int(self.mj.mjtGeom.mjGEOM_SPHERE) and
                float(self.model.geom_size[geom, 0]) <= 0.0051)

    def _set_pose(self, cell, yaw=0.0):
        x, y = self.grid_to_world(cell)
        self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = self._stand_root
        self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+2] = (x, y)
        self.data.qpos[self.robot_qpos_adr+3:self.robot_qpos_adr+7] = yaw_quaternion(yaw)
        self.data.qvel[:] = 0
        self.heading_yaw = float(yaw)

    def _sync_environment(self, world):
        for index, mocap_id in enumerate(self.pedestrian_mocaps):
            path = self.scenario.pedestrians[index]
            self.data.mocap_pos[mocap_id] = (*self.grid_to_world(path[world.step % len(path)]), 0)
        for cell, mocap_id in self._object_mocaps.items():
            self.data.mocap_pos[mocap_id] = (*self.grid_to_world(cell), 0 if cell in world.objects else -1000)

    def _contacts(self):
        counts = dict(foot_floor=0, unwanted_floor=0, pedestrian=0, wall=0,
                      persistent_obstacle=0, robot_self=0)
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            g1, g2 = int(contact.geom1), int(contact.geom2)
            r1, r2 = g1 in self._robot_geom_ids, g2 in self._robot_geom_ids
            if not (r1 or r2):
                continue
            if r1 and r2:
                counts['robot_self'] += 1
                continue
            robot_geom, other = (g1, g2) if r1 else (g2, g1)
            if other == self._floor_geom_id:
                counts['foot_floor' if robot_geom in self._foot_geom_ids else 'unwanted_floor'] += 1
            elif other in self._ped_geom_ids:
                counts['pedestrian'] += 1
            elif other in self._wall_geom_ids:
                counts['wall'] += 1
            elif other in self._object_geom_ids.values():
                counts['persistent_obstacle'] += 1
        return ContactCounts(**counts)

    def check_move(self, world, current, target, current_yaw=None, *, target_yaw=None):
        """Check a pivot sweep then translation; explicit target_yaw allows strafing."""
        old = self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7].copy()
        current_yaw = self.heading_yaw if current_yaw is None else float(current_yaw)
        wanted_yaw = (desired_heading(current, target, self.cell_size)
                      if target_yaw is None else float(target_yaw))
        if wanted_yaw is None:
            return False, ContactCounts(), current_yaw, None
        self._sync_environment(world)
        yaw_change = angle_delta(wanted_yaw, current_yaw)
        rotation_samples = max(1, math.ceil(abs(yaw_change)/0.05))
        for sample in range(1, rotation_samples+1):
            fraction = sample/rotation_samples
            yaw = current_yaw + yaw_change*fraction
            self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
            self.data.qpos[self.robot_qpos_adr+3:self.robot_qpos_adr+7] = yaw_quaternion(yaw)
            self.data.qvel[:] = 0
            self.mj.mj_forward(self.model, self.data)
            counts = self._contacts()
            if counts.environmental:
                self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
                self.data.qvel[:] = 0
                self.mj.mj_forward(self.model, self.data)
                return True, counts, current_yaw, 'rotation_collision'
        target_x, target_y = self.grid_to_world(target)
        distance = math.hypot(target_x-old[0], target_y-old[1])
        samples = max(1, math.ceil(distance / (self.cell_size/10)))
        for sample in range(1, samples+1):
            fraction = sample/samples
            self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
            self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+2] = (
                old[0] + (target_x-old[0])*fraction,
                old[1] + (target_y-old[1])*fraction)
            self.data.qpos[self.robot_qpos_adr+3:self.robot_qpos_adr+7] = yaw_quaternion(wanted_yaw)
            self.data.qvel[:] = 0
            self.mj.mj_forward(self.model, self.data)
            counts = self._contacts()
            if counts.environmental:
                self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
                self.data.qvel[:] = 0
                self.mj.mj_forward(self.model, self.data)
                return True, counts, current_yaw, 'translation_collision'
        self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
        self.data.qvel[:] = 0
        self.mj.mj_forward(self.model, self.data)
        return False, ContactCounts(), wanted_yaw, None

    def check_turn(self, world, position, current_yaw, target_yaw):
        """Check only an attempted in-place turn; do not probe other poses."""
        old = self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7].copy()
        current_yaw, target_yaw = float(current_yaw), float(target_yaw)
        self._sync_environment(world)
        yaw_change = angle_delta(target_yaw, current_yaw)
        samples = max(1, math.ceil(abs(yaw_change)/0.05))
        for sample in range(1, samples+1):
            yaw = current_yaw + yaw_change*sample/samples
            self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
            self.data.qpos[self.robot_qpos_adr+3:self.robot_qpos_adr+7] = yaw_quaternion(yaw)
            self.data.qvel[:] = 0
            self.mj.mj_forward(self.model, self.data)
            counts = self._contacts()
            if counts.environmental:
                self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
                self.data.qvel[:] = 0
                self.mj.mj_forward(self.model, self.data)
                return True, counts, current_yaw, 'rotation_collision'
        self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = old
        self.data.qvel[:] = 0
        self.mj.mj_forward(self.model, self.data)
        return False, ContactCounts(), target_yaw, None

    def update(self, world, frame):
        self._sync_environment(world)
        self._set_pose(frame['position'], frame.get('heading_yaw', 0.0))
        self.mj.mj_forward(self.model, self.data)
        current = self._contacts()
        # Attempt contacts are supplied by the single selected-action shield
        # check in run_episode. Rechecking here would be an unaccounted probe.
        attempted = ContactCounts()
        self.data.time = frame['step'] * self.timestep
        self._last_snapshot = dict(step=frame['step'], robot=frame['position'],
            pedestrians=sorted(world.people()), active_objects=sorted(world.objects), contacts=vars(current))
        return dict(g1_foot_floor_contact_pairs=current.foot_floor,
                    g1_unwanted_floor_contact_pairs=current.unwanted_floor,
                    g1_pedestrian_contact_pairs=current.pedestrian,
                    g1_wall_contact_pairs=current.wall,
                    g1_persistent_obstacle_contact_pairs=current.persistent_obstacle,
                    g1_self_contact_pairs=current.robot_self,
                    g1_attempt_pedestrian_contact_pairs=attempted.pedestrian,
                    g1_attempt_wall_contact_pairs=attempted.wall,
                    g1_attempt_persistent_obstacle_contact_pairs=attempted.persistent_obstacle,
                    g1_pedestrians=[path[world.step % len(path)] for path in self.scenario.pedestrians],
                    g1_active_objects=sorted(world.objects))

    def snapshot(self):
        return self._last_snapshot

    def render(self, width=960, height=720):
        renderer = self.mj.Renderer(self.model, height=height, width=width)
        try:
            camera = self.mj.MjvCamera()
            self.mj.mjv_defaultCamera(camera)
            camera.type = self.mj.mjtCamera.mjCAMERA_FIXED
            camera.fixedcamid = self.mj.mj_name2id(self.model, self.mj.mjtObj.mjOBJ_CAMERA, 'overview')
            renderer.update_scene(self.data, camera=camera)
            return renderer.render()
        finally:
            renderer.close()
