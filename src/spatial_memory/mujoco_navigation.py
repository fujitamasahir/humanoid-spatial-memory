"""3D MuJoCo scene adapter for Phase 2 kinematic grid navigation.

The included humanoid is a simple collision proxy, not a Unitree G1 model.
Grid movement, sensing, memory, and planning remain in the existing 2D code;
MuJoCo supplies the mapped 3D scene and contact geometry only.
"""
from dataclasses import dataclass
import math


PROXY_NAME = 'humanoid_collision_proxy'


@dataclass(frozen=True)
class ContactCounts:
    pedestrian: int = 0
    wall: int = 0
    persistent_obstacle: int = 0


class MujocoNavigationScene:
    """Build/update one MuJoCo scene for one existing 2D Scenario."""

    def __init__(self, scenario, *, cell_size=0.75, timestep=0.02):
        if not math.isfinite(cell_size) or cell_size <= 0:
            raise ValueError('cell_size must be positive and finite')
        if not math.isfinite(timestep) or timestep <= 0:
            raise ValueError('timestep must be positive and finite')
        try:
            import mujoco
        except ImportError as error:
            raise RuntimeError('Install the pinned mujoco dependency to run Phase 2') from error
        self.mj = mujoco
        self.scenario = scenario
        self.cell_size = float(cell_size)
        self.timestep = float(timestep)
        self.xml, self._object_names = self._make_xml()
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.model.opt.timestep = self.timestep
        self.data = mujoco.MjData(self.model)
        self.robot_body = self._body_id('robot_proxy')
        robot_joint = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_JOINT, 'robot_root')
        if robot_joint < 0:
            raise ValueError('Missing kinematic robot root joint')
        self.robot_qpos_adr = int(self.model.jnt_qposadr[robot_joint])
        self.robot_qvel_adr = int(self.model.jnt_dofadr[robot_joint])
        self.pedestrian_bodies = [self._body_id(f'pedestrian_{i}')
                                  for i in range(len(scenario.pedestrians))]
        self.pedestrian_mocaps = [int(self.model.body_mocapid[i]) for i in self.pedestrian_bodies]
        self._wall_geom_ids = {self._geom_id(f'wall_{x}_{y}') for x, y in scenario.walls}
        self._object_geom_ids = {cell: self._geom_id(f'object_geom_{cell[0]}_{cell[1]}')
                                 for cell in self._object_names}
        self._object_mocaps = {}
        for cell, name in self._object_names.items():
            body_id = self._body_id(name)
            self._object_mocaps[cell] = int(self.model.body_mocapid[body_id])
        self._robot_geom_ids = {i for i in range(self.model.ngeom)
                                if int(self.model.geom_bodyid[i]) == self.robot_body}
        self._pedestrian_geom_ids = [{i for i in range(self.model.ngeom)
                                      if int(self.model.geom_bodyid[i]) == body}
                                     for body in self.pedestrian_bodies]
        self._last_snapshot = None

    def _make_xml(self):
        scenario = self.scenario
        spacing = self.cell_size
        extent_x = max(2.0, scenario.width * spacing / 2 + spacing)
        extent_y = max(2.0, scenario.height * spacing / 2 + spacing)
        parts = [
            '<mujoco model="phase2_kinematic_navigation">',
            f'<option timestep="{self.timestep:.6g}" gravity="0 0 -9.81" integrator="implicitfast"/>',
            '<visual><global offwidth="960" offheight="720"/></visual>',
            '<worldbody>',
            '<light name="key" pos="0 -4 8" dir="0 0 -1" diffuse="0.8 0.8 0.8"/>',
            f'<camera name="overview" pos="0 {-extent_y * 1.9:.6g} {max(extent_x, extent_y) * 1.8:.6g}" '
            'xyaxes="1 0 0 0 0.85 0.53" fovy="50"/>',
            f'<geom name="floor" type="plane" size="{extent_x:.6g} {extent_y:.6g} 0.1" '
            'rgba="0.78 0.80 0.82 1" contype="1" conaffinity="1"/>',
        ]
        half = spacing * 0.505
        object_cells = set(scenario.obstacles)
        object_cells.update(tuple(event['cell']) for event in scenario.changes)
        object_cells.update(tuple(event['to']) for event in scenario.changes if 'to' in event)
        object_names = {}
        for x, y in sorted(scenario.walls):
            wx, wy = self.grid_to_world((x, y))
            parts.append(f'<geom name="wall_{x}_{y}" type="box" pos="{wx:.6g} {wy:.6g} 1.25" '
                         f'size="{half:.6g} {half:.6g} 1.25" rgba="0.23 0.25 0.29 1"/>')
        for x, y in sorted(object_cells):
            wx, wy = self.grid_to_world((x, y))
            name = f'object_body_{x}_{y}'
            object_names[(x, y)] = name
            active = (x, y) in scenario.obstacles
            base_z = 0 if active else -1000
            parts.append(f'<body name="{name}" mocap="true" pos="{wx:.6g} {wy:.6g} {base_z}">'
                         f'<geom name="object_geom_{x}_{y}" type="box" pos="0 0 0.45" '
                         f'size="{half:.6g} {half:.6g} 0.45" rgba="0.65 0.35 0.16 1" '
                         'contype="1" conaffinity="1"/></body>')
        parts.extend([
            '<body name="robot_proxy">',
            '<freejoint name="robot_root"/>',
            '<geom name="robot_left_leg" type="capsule" fromto="-0.12 -0.10 0.16 -0.12 -0.10 0.82" size="0.075" rgba="0.12 0.34 0.77 1"/>',
            '<geom name="robot_right_leg" type="capsule" fromto="0.12 -0.10 0.16 0.12 -0.10 0.82" size="0.075" rgba="0.12 0.34 0.77 1"/>',
            '<geom name="robot_torso" type="capsule" fromto="0 0 0.79 0 0 1.38" size="0.17" rgba="0.12 0.34 0.77 1"/>',
            '<geom name="robot_head" type="sphere" pos="0 0 1.53" size="0.105" rgba="0.85 0.70 0.55 1"/>',
            '<geom name="robot_left_arm" type="capsule" fromto="-0.17 0 1.28 -0.35 0 0.87" size="0.065" rgba="0.12 0.34 0.77 1"/>',
            '<geom name="robot_right_arm" type="capsule" fromto="0.17 0 1.28 0.35 0 0.87" size="0.065" rgba="0.12 0.34 0.77 1"/>',
            '</body>',
        ])
        for index in range(len(scenario.pedestrians)):
            parts.extend([
                f'<body name="pedestrian_{index}" mocap="true">',
                f'<geom name="pedestrian_geom_{index}" type="capsule" fromto="0 0 0.20 0 0 1.28" size="0.19" rgba="0.87 0.28 0.22 1"/>',
                '</body>',
            ])
        parts.extend(['</worldbody>', '</mujoco>'])
        return ''.join(parts), object_names

    def grid_to_world(self, cell):
        """Map grid (x,y) to MuJoCo world (X,Y); Z is vertical."""
        x, y = cell
        return ((x - (self.scenario.width - 1) / 2) * self.cell_size,
                (y - (self.scenario.height - 1) / 2) * self.cell_size)

    def world_to_grid(self, point):
        x, y = point
        gx = int(round(x / self.cell_size + (self.scenario.width - 1) / 2))
        gy = int(round(y / self.cell_size + (self.scenario.height - 1) / 2))
        return gx, gy

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

    def _contacts(self):
        pedestrian = wall = persistent = 0
        ped_bodies = set(self.pedestrian_bodies)
        for index in range(self.data.ncon):
            contact = self.data.contact[index]
            b1 = int(self.model.geom_bodyid[contact.geom1])
            b2 = int(self.model.geom_bodyid[contact.geom2])
            if self.robot_body not in (b1, b2):
                continue
            other_body = b2 if b1 == self.robot_body else b1
            other_geom = int(contact.geom2 if b1 == self.robot_body else contact.geom1)
            if other_body in ped_bodies:
                pedestrian += 1
            elif other_geom in self._wall_geom_ids:
                wall += 1
            elif other_geom in self._object_geom_ids.values():
                persistent += 1
        return ContactCounts(pedestrian, wall, persistent)

    def update(self, world, frame):
        """Synchronize evaluator-owned truth into MuJoCo, never into the agent."""
        robot_x, robot_y = self.grid_to_world(frame['position'])
        self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = (robot_x, robot_y, 0, 1, 0, 0, 0)
        self.data.qvel[self.robot_qvel_adr:self.robot_qvel_adr+6] = 0
        for index, mocap_id in enumerate(self.pedestrian_mocaps):
            path = self.scenario.pedestrians[index]
            cell = path[world.step % len(path)]
            self.data.mocap_pos[mocap_id] = (*self.grid_to_world(cell), 0)
        for cell, geom_id in self._object_geom_ids.items():
            active = cell in world.objects
            wx, wy = self.grid_to_world(cell)
            self.data.mocap_pos[self._object_mocaps[cell]] = (wx, wy, 0 if active else -1000)
        self.mj.mj_forward(self.model, self.data)
        current = self._contacts()
        attempt = ContactCounts()
        planned = frame.get('planned') or []
        if frame.get('blocked') and len(planned) > 1:
            target_x, target_y = self.grid_to_world(planned[1])
            self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = (target_x, target_y, 0, 1, 0, 0, 0)
            self.data.qvel[self.robot_qvel_adr:self.robot_qvel_adr+6] = 0
            self.mj.mj_forward(self.model, self.data)
            attempt = self._contacts()
            self.data.qpos[self.robot_qpos_adr:self.robot_qpos_adr+7] = (robot_x, robot_y, 0, 1, 0, 0, 0)
            self.data.qvel[self.robot_qvel_adr:self.robot_qvel_adr+6] = 0
            self.mj.mj_forward(self.model, self.data)
        self.data.time = frame['step'] * self.timestep
        self._last_snapshot = dict(step=frame['step'], robot=frame['position'],
            pedestrians=sorted(world.people()), active_objects=sorted(world.objects),
            contacts=vars(current), attempted_target_contacts=vars(attempt))
        return dict(mujoco_pose_pedestrian_contact_pairs=current.pedestrian,
                    mujoco_pose_wall_contact_pairs=current.wall,
                    mujoco_pose_persistent_obstacle_contact_pairs=current.persistent_obstacle,
                    mujoco_attempt_pedestrian_overlap_checks=attempt.pedestrian,
                    mujoco_attempt_wall_overlap_checks=attempt.wall,
                    mujoco_attempt_persistent_obstacle_overlap_checks=attempt.persistent_obstacle)

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
