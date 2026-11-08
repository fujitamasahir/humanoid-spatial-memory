"""Create a separate forward-facing G1 portfolio demo from a saved fit world."""
import argparse
import json
import math
import os
import platform
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from phase2_mujoco_navigation import admitted_worlds, sha, verify_preserved_prefix
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import HEADINGS, heading_index, plan_g1_forward_facing
from spatial_memory.phase15_bprime import VERSION
from spatial_memory.simulation import scenario_from_bprime


DEFAULT_IDENTITY = f'{VERSION}:fit:BP:80010010'
DEFAULT_OUTPUT = ROOT / 'results/phase2_mujoco/g1_forward_facing_portfolio_fit_BP_80010010_schedule0'


def asset_inventory():
    return [{'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
             'sha256': sha(path.read_bytes())}
            for path in sorted((ROOT/'third_party/unitree_g1').rglob('*')) if path.is_file()]


def screen_initial_routes(worlds):
    """Screen admitted worlds using one authorized 3D ray observation each."""
    records = []
    for payload in worlds:
        scenario = scenario_from_bprime(payload, 0)
        scene = MujocoNavigationScene(scenario, cell_size=0.75, timestep=0.02)
        sensor = MujocoRayPerception(scene, range_m=6.0, horizontal_fov_deg=120.0,
                                     ray_count=61, sample_spacing_m=0.075)
        observed = sensor.observe(World(scenario), scenario.start, 0.0)
        route = plan_g1_forward_facing(observed, scenario.start, scenario.goal,
            heading=0, unknown='optimistic',
            local_extents=scene.footprint_half_extents_local, cell_size=scene.cell_size)
        records.append({
            'identity': payload['identity'], 'start': list(scenario.start),
            'goal': list(scenario.goal), 'initial_occupied_observed_cells': int((observed == 1).sum()),
            'initial_observation_ray_count': sensor.ray_count,
            'initial_forward_route_found': bool(route),
            'initial_route_action_count': len(route),
            'initial_route_first_action': route[0] if route else None,
            'selection_inputs': 'initial 3D ray observation, public start/goal, public G1 extents; no MuJoCo collision shield probes',
        })
    return records


def run(output, *, max_steps=240, environment_id=DEFAULT_IDENTITY):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite portfolio output: {output}')
    worlds = admitted_worlds()
    screening = screen_initial_routes(worlds)
    payload = next((item for item in worlds if item['identity'] == environment_id), None)
    if payload is None:
        raise ValueError(f'Required already-admitted fit environment is missing: {environment_id}')
    screen_record = next(record for record in screening if record['identity'] == environment_id)
    if not screen_record['initial_forward_route_found']:
        raise ValueError(f'Initial observed map has no forward route for {environment_id}')
    preservation = verify_preserved_prefix()
    run_commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    run_status = subprocess.run(['git', 'status', '--short', '--branch'], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    output.mkdir(parents=True)
    with (output/'run.lock').open('x', encoding='utf-8') as handle:
        json.dump({'pid': os.getpid(), 'mode': 'forward_facing_portfolio_only',
                   'source_commit': run_commit}, handle, sort_keys=True)
        handle.flush()
    (output/'initial_observation_route_screen.json').write_text(
        json.dumps({'selection_policy': 'screen admitted fit worlds by one initial 3D ray observation and forward-only observed-map route availability; no simulator occupancy or collision probes',
                    'worlds': screening}, sort_keys=True, indent=2)+'\n')
    scenario = scenario_from_bprime(payload, 0)
    scene = MujocoNavigationScene(scenario, cell_size=0.75, timestep=0.02)
    perception = MujocoRayPerception(scene, range_m=6.0, horizontal_fov_deg=120.0,
                                     ray_count=61, sample_spacing_m=0.075)
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0),
                  update_interval=4, unknown='optimistic', max_steps=max_steps,
                  observation_cost=1, max_observations=20,
                  common_horizon_metrics=False,
                  mujoco_cell_size_m=scene.cell_size,
                  mujoco_timestep_seconds=scene.timestep,
                  mujoco_ray_sensor=dict(range_m=6.0, horizontal_fov_deg=120.0,
                      ray_count=61, sample_spacing_m=0.075),
                  navigation_mode='forward_facing_portfolio_only',
                  planner_inputs='ternary 3D ray observation memory, public map bounds, public G1 collision bounds, attempted-action feedback',
                  rejected_action_history=True)
    shield_queries = []

    def planner(grid, position, goal, unknown, yaw, blocked):
        return plan_g1_forward_facing(grid, position, goal,
            heading=heading_index(yaw), unknown=unknown,
            local_extents=scene.footprint_half_extents_local,
            cell_size=scene.cell_size, blocked_actions=blocked)

    def checker(world, position, action, yaw):
        # This callback is invoked once for the selected action only. MuJoCo
        # geometry is used as an action shield, never for route enumeration.
        shield_queries.append((tuple(position), action[0]))
        kind, value = action
        if kind == 'turn':
            return scene.check_turn(world, position, yaw, HEADINGS[int(value)])
        return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)

    metrics, frames = run_episode(scenario, config, 'periodic', seed=42,
        _frame_callback=scene.update, _observation_provider=perception.observe,
        _g1_planner=planner, _action_checker=checker)
    translations = 0
    orientation_violations = []
    previous = scenario.start
    for index, frame in enumerate(frames):
        position = tuple(frame['position'])
        if frame['moved']:
            translations += 1
            dx, dy = position[0]-previous[0], position[1]-previous[1]
            yaw = float(frame['heading_yaw'])
            forward = dx*math.cos(yaw) + dy*math.sin(yaw)
            lateral = -dx*math.sin(yaw) + dy*math.cos(yaw)
            if forward < 1-1e-7 or abs(lateral) > 1e-7:
                orientation_violations.append(index)
        previous = position
    action_count = sum(frame.get('navigation_action') is not None for frame in frames)
    actual_contact_metrics = {
        'g1_unwanted_floor_contact_pairs': sum(f.get('g1_unwanted_floor_contact_pairs', 0) for f in frames),
        'g1_pedestrian_contact_pairs': sum(f.get('g1_pedestrian_contact_pairs', 0) for f in frames),
        'g1_wall_contact_pairs': sum(f.get('g1_wall_contact_pairs', 0) for f in frames),
        'g1_persistent_obstacle_contact_pairs': sum(f.get('g1_persistent_obstacle_contact_pairs', 0) for f in frames),
        'g1_self_contact_pairs': sum(f.get('g1_self_contact_pairs', 0) for f in frames),
    }
    actual_safety = {
        'status': 'PASS' if metrics['success'] and not orientation_violations
                  and not any(actual_contact_metrics.values()) else 'FAIL',
        'goal_reached': bool(metrics['success']),
        'successful_translations': translations,
        'forward_orientation_violations': orientation_violations,
        'actual_navigation_contact_metrics': actual_contact_metrics,
        'blocked_attempts': metrics['blocked_movement_attempts'],
        'selected_action_count': action_count,
        'actual_muJoCo_action_shield_queries': len(shield_queries),
        'unattempted_collision_queries': 0,
        'shield_query_count_matches_selected_action_count': len(shield_queries) == action_count,
    }
    if not actual_safety['shield_query_count_matches_selected_action_count']:
        actual_safety['status'] = 'FAIL'

    portable_xml = scene.xml.replace(str((ROOT/'third_party/unitree_g1/assets').resolve()),
                                     '../../../third_party/unitree_g1/assets')
    (output/'scene.xml').write_text(portable_xml, encoding='utf-8')
    scenario_record = {'width': scenario.width, 'height': scenario.height,
        'cell_size_m': scene.cell_size, 'name': scenario.name, 'split': scenario.split,
        'start': list(scenario.start), 'goal': list(scenario.goal)}
    (output/'scenario.json').write_text(json.dumps(scenario_record, sort_keys=True, indent=2)+'\n')
    trajectory = [{
        'step': frame['step'], 'position': list(frame['position']),
        'heading_yaw': float(frame['heading_yaw']),
        'heading_changed': bool(frame.get('heading_changed', False)),
        'navigation_action': frame.get('navigation_action'), 'moved': frame['moved'],
        'blocked': frame['blocked'], 'blocked_reason': frame.get('blocked_reason'),
        'observation_count': frame['observation_count'],
        'memory_grid': frame['memory'].tolist(),
        'observation_stats': frame.get('observation_stats', {}),
        'people': frame.get('g1_pedestrians', []),
        'active_objects': frame.get('g1_active_objects', []),
        'g1_foot_floor_contact_pairs': frame.get('g1_foot_floor_contact_pairs', 0),
        'g1_unwanted_floor_contact_pairs': frame.get('g1_unwanted_floor_contact_pairs', 0),
        'g1_pedestrian_contact_pairs': frame.get('g1_pedestrian_contact_pairs', 0),
        'g1_wall_contact_pairs': frame.get('g1_wall_contact_pairs', 0),
        'g1_persistent_obstacle_contact_pairs': frame.get('g1_persistent_obstacle_contact_pairs', 0),
    } for frame in frames]
    (output/'trajectory.json').write_text(json.dumps(trajectory, indent=2)+'\n')
    (output/'navigation_safety.json').write_text(json.dumps(actual_safety, sort_keys=True, indent=2)+'\n')
    (output/'summary.json').write_text(json.dumps(metrics, sort_keys=True, indent=2)+'\n')

    viewer_path = ROOT/'scripts/view_phase2_g1_navigation.py'
    import importlib.util
    spec = importlib.util.spec_from_file_location('phase2_g1_viewer_for_portfolio', viewer_path)
    viewer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(viewer)
    visual_audit = {}
    visual_contact_frames = viewer.replay(output, 0.18, viewer=False,
        visual_gait=True, contact_audit=visual_audit)
    visual_audit['status'] = 'PASS' if not sum(count > 0 for count in visual_contact_frames) else 'FAIL'
    visual_audit['interpretation'] = 'Visual-only gait collision audit; separate from navigation safety metrics.'
    (output/'visual_only_contact_audit.json').write_text(
        json.dumps(visual_audit, sort_keys=True, indent=2)+'\n')
    preserved_after = verify_preserved_prefix()
    provenance = {
        'demo_type': 'forward_facing_portfolio_only',
        'purpose': 'separate presentation demonstration; not an experimental comparison or locomotion result',
        'git_commit_at_run': run_commit, 'git_status_at_run': run_status,
        'python': sys.version, 'platform': platform.platform(), 'architecture': platform.machine(),
        'mujoco_version': __import__('mujoco').__version__,
        'environment_identity': payload['identity'], 'mechanism': payload['mechanism'],
        'fit_index': payload['index'], 'schedule_index': 0, 'seed': 42,
        'environment_source': 'existing admitted Phase 1.5 fit checkpoint; no environment regeneration',
        'environment_selection': 'selected from initial-ray-only screen; selected identity must have an observed-memory forward route; screen contains no hidden occupancy or shield query results',
        'initial_observation_route_screen_file': 'initial_observation_route_screen.json',
        'navigation_mode': 'forward-only cardinal translations after separately selected in-place cardinal turns',
        'perception': 'existing MuJoCo 3D ray sensor; planner receives only ternary observation memory',
        'route_planning': 'A* over position and heading using observed occupied cells, unknown policy, public footprint bounds and prior attempted-action feedback',
        'actual_action_clearance': 'selected turn sweeps use MujocoNavigationScene.check_turn; selected translation sweeps use check_move with current heading; no unattempted MuJoCo collision queries',
        'visual_gait': 'presentation-only procedural joint poses; not physically simulated locomotion',
        'grid_scale_m_per_cell': scene.cell_size, 'grid_scale_calibrated': False,
        'config': config, 'navigation_safety': actual_safety,
        'visual_only_contact_audit_file': 'visual_only_contact_audit.json',
        'preserved_phase15_files_checked_before_and_after': [preservation['files_checked'], preserved_after['files_checked']],
        'preservation_manifest_sha256': preserved_after['manifest_sha256'],
        'robot_model_files': asset_inventory(),
        'source_hashes': {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in (
            ROOT/'scripts/phase2_g1_forward_portfolio.py', ROOT/'scripts/phase2_mujoco_navigation.py',
            ROOT/'scripts/view_phase2_g1_navigation.py', ROOT/'src/spatial_memory/navigation.py',
            ROOT/'src/spatial_memory/evaluation.py', ROOT/'src/spatial_memory/mujoco_navigation.py',
            ROOT/'src/spatial_memory/mujoco_perception.py')},
        'reproduction_command': '.venv/bin/python scripts/phase2_g1_forward_portfolio.py --output <new-empty-directory>',
        'viewer_command': ('.venv/bin/mjpython scripts/view_phase2_g1_navigation.py '
            f'--result-dir {output.relative_to(ROOT)} --camera overview '
            '--portfolio-forward-demo --speed 0.18 --once'),
    }
    (output/'provenance.json').write_text(json.dumps(provenance, sort_keys=True, indent=2)+'\n')
    inventory = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != 'artifact_manifest.json':
            raw = path.read_bytes()
            inventory.append({'path': path.name, 'bytes': len(raw), 'sha256': sha(raw)})
    (output/'artifact_manifest.json').write_text(json.dumps(inventory, sort_keys=True, indent=2)+'\n')
    return {'output': str(output), 'identity': payload['identity'], 'summary': metrics,
            'navigation_safety': actual_safety, 'visual_only_contact_audit': visual_audit}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--max-steps', type=int, default=240)
    parser.add_argument('--environment-id', default=DEFAULT_IDENTITY)
    args = parser.parse_args()
    if args.max_steps < 1:
        parser.error('--max-steps must be positive')
    output = args.output if args.output.is_absolute() else ROOT/args.output
    print(json.dumps(run(output, max_steps=args.max_steps,
                         environment_id=args.environment_id), sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
