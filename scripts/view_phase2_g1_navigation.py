"""Replay a saved G1 kinematic trajectory in the native MuJoCo Viewer."""
import argparse
import json
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import mujoco
import mujoco.viewer


def display_scene_xml(result_dir: Path):
    """Return a view-only scene with sane camera bounds (never edit evidence).

    Inactive obstacle mocap bodies are parked at Z=-1000 in the saved MJCF.
    Their *initial* positions inflate the model's inferred extent, resulting
    in a far-away free camera and an enormous near clipping distance. Only
    override the rendering statistic, not any geom/pose/physics parameters.
    """
    scene_path = result_dir / 'scene.xml'
    root = ET.parse(scene_path).getroot()
    settings = json.loads((result_dir / 'scenario.json').read_text(encoding='utf-8'))
    extent = 1.5 * max(settings['width'], settings['height']) * settings['cell_size_m']
    if extent <= 0:
        raise ValueError('Invalid scenario dimensions or scale')
    statistic = root.find('statistic')
    if statistic is None:
        statistic = ET.Element('statistic')
        root.insert(0, statistic)
    statistic.set('center', '0 0 1.25')
    statistic.set('extent', f'{extent:.8g}')
    # from_xml_string cannot infer the source file's relative mesh directory.
    compiler = root.find('compiler')
    if compiler is not None and compiler.get('meshdir'):
        meshdir = Path(compiler.get('meshdir'))
        if not meshdir.is_absolute():
            compiler.set('meshdir', str((scene_path.parent / meshdir).resolve()))
    return ET.tostring(root, encoding='unicode')


def replay(result_dir: Path, speed: float, *, viewer=True, camera='follow', loop=True):
    model = mujoco.MjModel.from_xml_string(display_scene_xml(result_dir))
    print(f'View-only model extent: {model.stat.extent:.2f} m, '
          f'near clip: {model.vis.map.znear * model.stat.extent:.3f} m',
          flush=True)
    data = mujoco.MjData(model)
    key = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_KEY, 'stand')
    joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, 'floating_base_joint')
    if key < 0 or joint < 0:
        raise ValueError('Replay scene is missing G1 stand key or floating_base_joint')
    mujoco.mj_resetDataKeyframe(model, data, key)
    qadr = int(model.jnt_qposadr[joint])
    qroot = data.qpos[qadr:qadr+7].copy()
    with (result_dir/'trajectory.json').open(encoding='utf-8') as handle:
        trajectory = json.load(handle)
    if not trajectory:
        raise ValueError('Saved G1 trajectory is empty')
    cells = json.loads((result_dir/'scenario.json').read_text(encoding='utf-8'))
    spacing = cells['cell_size_m']
    object_ids = {}
    pedestrian_ids = {}
    for body in range(model.nbody):
        name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body) or ''
        if name.startswith('object_body_'):
            object_ids[tuple(map(int, name.removeprefix('object_body_').split('_')))] = int(model.body_mocapid[body])
        elif name.startswith('pedestrian_'):
            pedestrian_ids[int(name.removeprefix('pedestrian_'))] = int(model.body_mocapid[body])
    floor = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, 'floor')
    g1_geoms = set()
    allowed_foot_geoms = set()
    for geom in range(model.ngeom):
        body = int(model.geom_bodyid[geom])
        while body > 0:
            if (mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY, body) or '') == 'pelvis':
                g1_geoms.add(geom)
                body_name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_BODY,
                                              int(model.geom_bodyid[geom])) or ''
                if ('ankle_roll_link' in body_name and
                    int(model.geom_type[geom]) == int(mujoco.mjtGeom.mjGEOM_SPHERE) and
                    float(model.geom_size[geom, 0]) <= 0.0051):
                    allowed_foot_geoms.add(geom)
                break
            body = int(model.body_parentid[body])

    def show_frame(frame):
        x, y = frame['position']
        # Grid spacing and origin are encoded by the runner's documented 0.75 m convention.
        wx = (x-(cells['width']-1)/2)*spacing
        wy = (y-(cells['height']-1)/2)*spacing
        data.qpos[qadr:qadr+7] = qroot
        data.qpos[qadr:qadr+2] = (wx, wy)
        yaw = float(frame.get('heading_yaw', 0.0))
        data.qpos[qadr+3:qadr+7] = (math.cos(yaw/2), 0.0, 0.0, math.sin(yaw/2))
        data.qvel[:] = 0
        data.mocap_pos[:] = 0
        for cell, mocap in object_ids.items():
            cx, cy = cell
            data.mocap_pos[mocap] = ((cx-(cells['width']-1)/2)*spacing,
                                     (cy-(cells['height']-1)/2)*spacing,
                                     0 if list(cell) in frame['active_objects'] else -1000)
        for index, mocap in pedestrian_ids.items():
            cell = frame['people'][index] if index < len(frame['people']) else None
            if cell is not None:
                cx, cy = cell
                data.mocap_pos[mocap] = ((cx-(cells['width']-1)/2)*spacing,
                                         (cy-(cells['height']-1)/2)*spacing, 0)
            else:
                data.mocap_pos[mocap] = (0, 0, -1000)
        data.time = frame['step']*0.02
        mujoco.mj_forward(model, data)
        bad = 0
        for i in range(data.ncon):
            c = data.contact[i]
            a, b = int(c.geom1), int(c.geom2)
            if ((a in allowed_foot_geoms and b == floor) or
                (b in allowed_foot_geoms and a == floor)):
                continue
            if a in g1_geoms or b in g1_geoms:
                bad += 1
        return bad

    if not viewer:
        return [show_frame(frame) for frame in trajectory]

    # Prime the state before creating the viewer; the default MuJoCo free camera
    # may otherwise look away from the robot in a large (25 x 25) indoor scene.
    show_frame(trajectory[0])
    overview = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_CAMERA, 'overview')
    if camera == 'overview' and overview < 0:
        raise ValueError('The saved scene has no overview camera')
    print(f'Opening G1 playback: {len(trajectory)} frames, camera={camera}. '
          'Close the viewer window to stop.', flush=True)
    with mujoco.viewer.launch_passive(model, data) as handle:
        with handle.lock():
            if camera == 'overview':
                handle.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
                handle.cam.fixedcamid = int(overview)
            else:
                handle.cam.type = mujoco.mjtCamera.mjCAMERA_FREE
                handle.cam.distance = 6.0
                handle.cam.azimuth = 135.0
                handle.cam.elevation = -55.0
                handle.cam.lookat[:] = (
                    float(data.qpos[qadr]), float(data.qpos[qadr+1]), 0.9)
        handle.sync()
        # Allow the native window to render the first frame before replay.
        time.sleep(1.0)
        while handle.is_running():
            for frame in trajectory:
                if not handle.is_running():
                    break
                show_frame(frame)
                if camera == 'follow':
                    with handle.lock():
                        handle.cam.lookat[:] = (
                            float(data.qpos[qadr]), float(data.qpos[qadr+1]), 0.9)
                handle.sync()
                time.sleep(speed)
            if not loop:
                break
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result-dir', type=Path, required=True)
    parser.add_argument('--speed', type=float, default=0.25, help='Seconds per saved frame')
    parser.add_argument('--validate-only', action='store_true', help='Headless replay/contact consistency check')
    parser.add_argument('--camera', choices=('follow', 'overview'), default='follow',
                        help='Follow G1 or use the fixed whole-scene overview')
    parser.add_argument('--once', action='store_true',
                        help='Play only once; otherwise replay until the viewer is closed')
    parser.add_argument('--export-view-scene', type=Path,
                        help='Save a derived display-only MJCF for testing in the standard MuJoCo viewer')
    args = parser.parse_args()
    if args.speed <= 0:
        parser.error('--speed must be positive')
    if args.export_view_scene is not None:
        args.export_view_scene.parent.mkdir(parents=True, exist_ok=True)
        args.export_view_scene.write_text(display_scene_xml(args.result_dir.resolve()),
                                          encoding='utf-8')
        print(f'Display-only scene: {args.export_view_scene}', flush=True)
    contacts = replay(args.result_dir.resolve(), args.speed,
                      viewer=not args.validate_only, camera=args.camera, loop=not args.once)
    if args.validate_only:
        print(json.dumps({'frames': len(contacts), 'unwanted_contact_frames': sum(n > 0 for n in contacts)}))


if __name__ == '__main__':
    main()
