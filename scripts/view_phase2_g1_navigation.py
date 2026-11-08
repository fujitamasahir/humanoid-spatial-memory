"""Replay a saved G1 kinematic trajectory in the native MuJoCo Viewer."""
import argparse
import json
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import mujoco
import mujoco.viewer


# Presentation-only gait amplitudes (radians). The route remains a saved,
# kinematic trajectory; these values pose the rendered joints only.
GAIT_STRIDE_M = 1.5
GAIT_RAMP_SECONDS = 0.22
GAIT_AMPLITUDES = {
    'hip_pitch': 0.20, 'knee': 0.28, 'ankle_pitch': 0.12,
    'shoulder_pitch': 0.12, 'elbow': 0.08,
}


def interpolate_heading(a, b, fraction):
    """Interpolate yaw along the shortest arc, including wrap at +/- pi."""
    delta = (float(b) - float(a) + math.pi) % (2 * math.pi) - math.pi
    return float(a) + delta * min(1.0, max(0.0, float(fraction)))


def interpolate_frame(first, second, fraction):
    """Interpolate only rendered root pose; discrete world state stays saved."""
    f = min(1.0, max(0.0, float(fraction)))
    p0, p1 = first['position'], second['position']
    return {
        'position': (float(p0[0]) + (float(p1[0])-float(p0[0]))*f,
                     float(p0[1]) + (float(p1[1])-float(p0[1]))*f),
        'heading_yaw': interpolate_heading(first.get('heading_yaw', 0.0),
                                            second.get('heading_yaw', 0.0), f),
    }


def gait_joint_targets(model, phase, amplitude, travel_sign=1.0):
    """Return bounded display joint offsets for one deterministic gait pose."""
    motion_code = int(round(float(travel_sign)))
    phase = float(phase) * (-1.0 if motion_code == -1 else 1.0)
    amplitude = min(1.0, max(0.0, float(amplitude)))
    lateral = abs(motion_code) == 2
    limb_scale = 0.32 if lateral else (0.68 if motion_code == -1 else 1.0)
    lateral_sign = 1.0 if motion_code == 2 else -1.0
    targets = {}
    for side, offset in (('left', 0.0), ('right', math.pi)):
        leg = phase + offset
        swing = math.sin(leg)
        knee = max(0.0, math.sin(leg + 0.25))
        values = {
            f'{side}_hip_pitch_joint': GAIT_AMPLITUDES['hip_pitch'] * swing * amplitude * limb_scale,
            f'{side}_knee_joint': GAIT_AMPLITUDES['knee'] * knee * amplitude * limb_scale,
            f'{side}_ankle_pitch_joint': -GAIT_AMPLITUDES['ankle_pitch'] *
                (swing + 0.45 * knee) * amplitude * limb_scale,
            f'{side}_shoulder_pitch_joint': -GAIT_AMPLITUDES['shoulder_pitch'] *
                swing * amplitude,
            f'{side}_elbow_joint': GAIT_AMPLITUDES['elbow'] *
                max(0.0, swing) * amplitude,
            f'{side}_hip_roll_joint': (lateral_sign * (1 if side == 'left' else -1) *
                0.10 * swing * amplitude if lateral else 0.0),
            f'{side}_ankle_roll_joint': (-lateral_sign * (1 if side == 'left' else -1) *
                0.045 * swing * amplitude if lateral else 0.0),
        }
        for name, value in values.items():
            joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
            if joint < 0:
                continue
            low, high = map(float, model.jnt_range[joint])
            targets[name] = min(high, max(low, value))
    return targets


def smooth_gait_envelope(elapsed, moving, ramp=GAIT_RAMP_SECONDS):
    """Simple display envelope with a smooth start and return to stand."""
    if moving:
        x = min(1.0, max(0.0, float(elapsed) / ramp))
        return x*x*(3-2*x)
    x = min(1.0, max(0.0, 1.0-float(elapsed)/ramp))
    return x*x*(3-2*x)


def playback_samples(trajectory, speed, spacing, fps=30):
    """Yield display poses at fixed FPS while retaining saved scene states."""
    phase = 0.0
    if len(trajectory) == 1:
        yield interpolate_frame(trajectory[0], trajectory[0], 0), trajectory[0], phase, 0.0, 1.0
        return
    gait_amplitude = 0.0
    frame_dt = 1.0 / fps
    for first, second in zip(trajectory, trajectory[1:]):
        p0, p1 = first['position'], second['position']
        dx, dy = float(p1[0])-float(p0[0]), float(p1[1])-float(p0[1])
        distance = math.hypot(dx, dy) * spacing
        moving = distance > 1e-9
        heading = float(first.get('heading_yaw', 0.0))
        forward = dx * math.cos(heading) + dy * math.sin(heading)
        lateral = -dx * math.sin(heading) + dy * math.cos(heading)
        action = second.get('navigation_action')
        action_kind = action[0] if isinstance(action, (tuple, list)) and action else None
        if action_kind == 'sidestep':
            motion_code = 2 if lateral >= 0 else -2
        elif action_kind == 'retreat':
            motion_code = -1
        elif abs(forward) > abs(lateral):
            motion_code = -1 if forward < 0 else 1
        elif distance > 1e-9:
            motion_code = 2 if lateral >= 0 else -2
        else:
            motion_code = 0
        steps = max(1, int(math.ceil(speed * fps)))
        for tick in range(steps):
            t = min(1.0, tick / steps)
            root = interpolate_frame(first, second, t)
            env_frame = first if t < 1.0 else second
            yield root, env_frame, phase + (distance / GAIT_STRIDE_M) * (2*math.pi) * t, gait_amplitude, motion_code
            target_amplitude = 1.0 if moving else 0.0
            alpha = min(1.0, frame_dt / GAIT_RAMP_SECONDS)
            difference = target_amplitude - gait_amplitude
            gait_amplitude += min(alpha, difference) if difference > 0 else max(-alpha, difference)
        phase += distance / GAIT_STRIDE_M * (2*math.pi)
    last = trajectory[-1]
    settle_steps = max(1, int(math.ceil(GAIT_RAMP_SECONDS * fps)))
    for tick in range(settle_steps):
        yield interpolate_frame(last, last, 0), last, phase, gait_amplitude, 0.0
        gait_amplitude = max(0.0, gait_amplitude-frame_dt/GAIT_RAMP_SECONDS)
    yield interpolate_frame(last, last, 0), last, phase, 0.0, 0.0


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
    # The real environment is intentionally group 5 for MuJoCo ray filtering.
    # The stock standalone viewer hides group 5; remap only this derived
    # display scene to group 0 (visible by default). Never edit saved scene.xml.
    for geom in root.iter('geom'):
        if geom.get('group') == '5':
            geom.set('group', '0')
    return ET.tostring(root, encoding='unicode')


def replay(result_dir: Path, speed: float, *, viewer=True, camera='follow', loop=True,
           visual_gait=False, contact_audit=None):
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
    stand_pose = {}
    gait_addresses = {}
    for name in gait_joint_targets(model, 0, 0):
        jid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, name)
        if jid >= 0 and int(model.jnt_type[jid]) == int(mujoco.mjtJoint.mjJNT_HINGE):
            address = int(model.jnt_qposadr[jid])
            stand_pose[name] = float(data.qpos[address])
            gait_addresses[name] = (jid, address)
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

    def show_frame(frame, scene_frame=None, gait=None):
        scene_frame = frame if scene_frame is None else scene_frame
        x, y = frame['position']
        # Grid spacing and origin are encoded by the runner's documented 0.75 m convention.
        wx = (x-(cells['width']-1)/2)*spacing
        wy = (y-(cells['height']-1)/2)*spacing
        data.qpos[qadr:qadr+7] = qroot
        data.qpos[qadr:qadr+2] = (wx, wy)
        yaw = float(frame.get('heading_yaw', 0.0))
        data.qpos[qadr+3:qadr+7] = (math.cos(yaw/2), 0.0, 0.0, math.sin(yaw/2))
        for name, base in stand_pose.items():
            _, address = gait_addresses[name]
            data.qpos[address] = base
        if gait is not None:
            phase, amplitude, travel_sign = gait
            for name, offset in gait_joint_targets(model, phase, amplitude, travel_sign).items():
                jid, address = gait_addresses[name]
                low, high = map(float, model.jnt_range[jid])
                data.qpos[address] = min(high, max(low, stand_pose[name] + offset))
        data.qvel[:] = 0
        data.mocap_pos[:] = 0
        for cell, mocap in object_ids.items():
            cx, cy = cell
            data.mocap_pos[mocap] = ((cx-(cells['width']-1)/2)*spacing,
                                     (cy-(cells['height']-1)/2)*spacing,
                                     0 if list(cell) in scene_frame['active_objects'] else -1000)
        for index, mocap in pedestrian_ids.items():
            cell = scene_frame['people'][index] if index < len(scene_frame['people']) else None
            if cell is not None:
                cx, cy = cell
                data.mocap_pos[mocap] = ((cx-(cells['width']-1)/2)*spacing,
                                         (cy-(cells['height']-1)/2)*spacing, 0)
            else:
                data.mocap_pos[mocap] = (0, 0, -1000)
        data.time = float(frame.get('step', 0))*0.02
        mujoco.mj_forward(model, data)
        bad = 0
        for i in range(data.ncon):
            c = data.contact[i]
            a, b = int(c.geom1), int(c.geom2)
            if ((a in allowed_foot_geoms and b == floor) or
                (b in allowed_foot_geoms and a == floor)):
                if contact_audit is not None:
                    contact_audit['foot_floor_contact_pairs'] = \
                        contact_audit.get('foot_floor_contact_pairs', 0) + 1
                continue
            if a in g1_geoms or b in g1_geoms:
                bad += 1
                if contact_audit is not None:
                    contact_audit['unwanted_contact_pairs'] = \
                        contact_audit.get('unwanted_contact_pairs', 0) + 1
                    other = b if a in g1_geoms else a
                    name = mujoco.mj_id2name(model, mujoco.mjtObj.mjOBJ_GEOM, other) or ''
                    category = ('wall' if name.startswith('wall_') else
                                'pedestrian' if name.startswith('pedestrian_geom_') else
                                'persistent_obstacle' if name.startswith('object_geom_') else
                                'floor' if other == floor else 'other')
                    key = f'{category}_contact_pairs'
                    contact_audit[key] = contact_audit.get(key, 0) + 1
        if contact_audit is not None:
            contact_audit['rendered_poses'] = contact_audit.get('rendered_poses', 0) + 1
            if bad:
                contact_audit['unwanted_contact_frames'] = \
                    contact_audit.get('unwanted_contact_frames', 0) + 1
        return bad

    if not viewer:
        if visual_gait:
            results = []
            for frame, scene_frame, phase, amplitude, travel_sign in \
                    playback_samples(trajectory, speed, spacing, fps=30):
                results.append(show_frame(frame, scene_frame,
                    (phase, amplitude, travel_sign)))
            return results
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
            # MuJoCo only shows geom groups 0..2 by default. The walls,
            # pedestrian proxies and persistent obstacles are group 5 to
            # isolate 3D perception rays; turn them on in this *viewer*.
            handle.opt.geomgroup[5] = 1
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
        samples = (list(playback_samples(trajectory, speed, spacing, fps=30))
                   if visual_gait else None)
        while handle.is_running():
            poses = (samples if visual_gait else
                     [(frame, frame, None, 0.0, 1.0) for frame in trajectory])
            for frame, scene_frame, phase, amplitude, travel_sign in poses:
                if not handle.is_running():
                    break
                gait = ((phase, amplitude, travel_sign) if visual_gait else None)
                show_frame(frame, scene_frame, gait)
                if camera == 'follow':
                    with handle.lock():
                        handle.cam.lookat[:] = (
                            float(data.qpos[qadr]), float(data.qpos[qadr+1]), 0.9)
                handle.sync()
                time.sleep(1.0/30.0 if visual_gait else speed)
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
    parser.add_argument('--visual-gait', action='store_true',
                        help='Add a presentation-only procedural gait; saved route and world are unchanged')
    parser.add_argument('--portfolio-forward-demo', action='store_true',
                        help='Play a separately generated forward-facing portfolio route with visual gait')
    parser.add_argument('--export-view-scene', type=Path,
                        help='Save a derived display-only MJCF for testing in the standard MuJoCo viewer')
    args = parser.parse_args()
    if args.speed <= 0:
        parser.error('--speed must be positive')
    if args.visual_gait and args.portfolio_forward_demo:
        parser.error('Choose either --visual-gait or --portfolio-forward-demo')
    if args.portfolio_forward_demo:
        provenance_path = args.result_dir/'provenance.json'
        if not provenance_path.is_file():
            parser.error('--portfolio-forward-demo requires its provenance.json')
        provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
        if provenance.get('demo_type') != 'forward_facing_portfolio_only':
            parser.error('Result directory is not a forward-facing portfolio demonstration')
    if args.export_view_scene is not None:
        args.export_view_scene.parent.mkdir(parents=True, exist_ok=True)
        args.export_view_scene.write_text(display_scene_xml(args.result_dir.resolve()),
                                          encoding='utf-8')
        print(f'Display-only scene: {args.export_view_scene}', flush=True)
    contact_audit = {} if args.portfolio_forward_demo else None
    contacts = replay(args.result_dir.resolve(), args.speed,
                      viewer=not args.validate_only, camera=args.camera, loop=not args.once,
                      visual_gait=args.visual_gait or args.portfolio_forward_demo,
                      contact_audit=contact_audit)
    if args.validate_only:
        report = {'frames': len(contacts), 'unwanted_contact_frames': sum(n > 0 for n in contacts)}
        if contact_audit is not None:
            report['visual_only_contact_audit'] = contact_audit
        print(json.dumps(report))


if __name__ == '__main__':
    main()
