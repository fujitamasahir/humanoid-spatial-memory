"""Run a read-only Phase 2 G1 kinematic-navigation smoke or pilot."""
import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from spatial_memory.phase15_bprime import ACTIVE_MECHANISMS, VERSION, seed_for
from spatial_memory.phase15_bprime_protocol import digest
from spatial_memory.simulation import scenario_from_bprime
from spatial_memory.evaluation import run_episode
from spatial_memory.mujoco_navigation import MujocoNavigationScene
from spatial_memory.mujoco_perception import MujocoRayPerception
from spatial_memory.navigation import (HEADINGS, assess_observed_pedestrian_risk,
    heading_index, plan_g1_default_policy)
from spatial_memory.pedestrian_tracking import ObservedPedestrianTracker

STORES = (
    'results/raw/phase15_macos_development/fit',
    'results/raw/phase15_bprime_fit_recovery_1/store',
    'results/raw/phase15_bprime_fit_recovery_2/store',
)
METHODS = ('static', 'periodic', 'age', 'uncertainty')
PRESERVATION = 'results/phase1_5_bprime_macos/m3_checkpoint_receipt_manifest.json.gz'
PRESERVATION_SHA256 = '73f4ef7da1fc238748cb0e23840bf1c2e6357df64aef839a86b80549e95177f1'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def checkpoints():
    seen = set()
    for relative in STORES:
        directory = ROOT / relative / 'records'
        if not directory.is_dir():
            raise FileNotFoundError(f'Missing committed fit store: {directory}')
        for path in sorted(directory.glob('*.json.gz')):
            packed = path.read_bytes()
            body = json.loads(gzip.decompress(packed))
            payload = body['payload']
            identity = body.get('identity')
            if (not isinstance(identity, str)
                    or path.name != hashlib.sha256(identity.encode()).hexdigest() + '.json.gz'
                    or body.get('payload_sha256') != digest(payload)
                    or payload.get('identity') != identity
                    or identity in seen):
                raise ValueError(f'Checkpoint integrity or identity conflict: {path}')
            seen.add(identity)
            yield payload


def admitted_worlds():
    worlds = {mechanism: [] for mechanism in ACTIVE_MECHANISMS}
    for payload in checkpoints():
        if payload.get('partition') != 'fit' or payload.get('outcome') != 'independent':
            continue
        mechanism = payload.get('mechanism')
        if mechanism not in worlds:
            continue
        index = payload['index']
        expected = f'{VERSION}:fit:{mechanism}:{seed_for("fit", mechanism, index)}'
        if payload['identity'] != expected:
            raise ValueError(f'Invalid saved fit identity: {payload["identity"]}')
        worlds[mechanism].append(payload)
    for mechanism, records in worlds.items():
        records.sort(key=lambda payload: payload['index'])
        if len(records) != 12:
            raise ValueError(f'Expected 12 admitted {mechanism} fit worlds, got {len(records)}')
    return [payload for mechanism in ACTIVE_MECHANISMS for payload in worlds[mechanism]]


def verify_preserved_prefix():
    path = ROOT / PRESERVATION
    manifest_raw = path.read_bytes()
    if sha(manifest_raw) != PRESERVATION_SHA256:
        raise ValueError('The committed Phase 1.5 preservation manifest changed')
    manifest = json.loads(gzip.decompress(manifest_raw))
    if len(manifest['files']) != 836:
        raise ValueError('Preservation evidence must commit all 836 checkpoint/receipt files')
    checked = 0
    for entry in manifest['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Noncanonical path in Phase 1.5 preservation manifest')
        file_path = (ROOT / relative).resolve()
        if not file_path.is_relative_to(ROOT):
            raise ValueError('Preservation manifest path escaped repository root')
        raw = file_path.read_bytes()
        if len(raw) != entry['bytes'] or sha(raw) != entry['sha256']:
            raise ValueError(f'Preserved Phase 1.5 evidence changed: {entry["path"]}')
        checked += 1
    return {'files_checked': checked, 'manifest_sha256': sha(manifest_raw)}


class Progress:
    def __init__(self, total, interval):
        self.total, self.interval = total, interval
        self.completed = 0
        self.started = time.monotonic()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._heartbeat, daemon=True)

    def __enter__(self):
        print(f'Progress: 0/{self.total} (0.0%) | elapsed 0.0 min | ETA pending', flush=True)
        self.thread.start()
        return self

    def _line(self):
        elapsed = time.monotonic() - self.started
        eta = (elapsed / self.completed * (self.total - self.completed)
               if self.completed else None)
        eta_text = f'{eta / 60:.1f} min' if eta is not None else 'pending (no completed episodes)'
        print(f'Progress: {self.completed}/{self.total} ({100*self.completed/self.total:.1f}%) | '
              f'elapsed {elapsed/60:.1f} min | ETA {eta_text}', flush=True)

    def _heartbeat(self):
        while not self.stop.wait(self.interval):
            self._line()

    def done(self):
        self.completed += 1
        if self.completed == self.total:
            self._line()

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(timeout=2)


def persist_csv(path, rows):
    fields = list(rows[0])
    with path.open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def summarize(rows):
    def aggregate(subset):
        n = max(1, len(subset))
        return {
            'episodes': len(subset),
            'goal_completions': sum(bool(row['success']) for row in subset),
            'goal_completion_rate': sum(bool(row['success']) for row in subset) / n,
            'grid_dynamic_contact_free_completions': sum(bool(row['contact_free_success']) for row in subset),
            'g1_contact_free_completions': sum(bool(row.get('g1_contact_free_success', False)) for row in subset),
            'g1_unwanted_contact_pairs': sum(row.get('g1_unwanted_contact_pairs', 0) for row in subset),
            'g1_footprint_blocked_attempts': sum(row.get('g1_footprint_blocked_attempts', 0) for row in subset),
            'g1_heading_changes': sum(row.get('g1_heading_changes', 0) for row in subset),
            'g1_forward_actions': sum(row.get('g1_forward_actions', 0) for row in subset),
            'g1_lateral_actions': sum(row.get('g1_lateral_actions', 0) for row in subset),
            'g1_backward_actions': sum(row.get('g1_backward_actions', 0) for row in subset),
            'g1_executed_forward_translations': sum(row.get('g1_executed_forward_translations', 0) for row in subset),
            'g1_executed_lateral_steps': sum(row.get('g1_executed_lateral_steps', 0) for row in subset),
            'g1_executed_backward_steps': sum(row.get('g1_executed_backward_steps', 0) for row in subset),
            'g1_in_place_turns': sum(row.get('g1_in_place_turns', 0) for row in subset),
            'g1_waits': sum(row.get('g1_waits', 0) for row in subset),
            'g1_forward_action_percent': (100.0*sum(row.get('g1_forward_actions', 0)
                for row in subset)/max(1, sum(row.get('g1_forward_actions', 0)
                + row.get('g1_lateral_actions', 0)+row.get('g1_backward_actions', 0)
                for row in subset))),
            'g1_nonforward_action_reasons': {
                reason: sum(row.get('g1_nonforward_action_reasons', {}).get(reason, 0)
                            for row in subset)
                for reason in sorted({reason for row in subset
                    for reason in row.get('g1_nonforward_action_reasons', {})})},
            'g1_navigation_no_route_steps': sum(row.get('g1_navigation_no_route_steps', 0) for row in subset),
            'g1_rejected_action_attempts': sum(row.get('g1_rejected_action_attempts',
                row.get('g1_footprint_blocked_attempts', 0)) for row in subset),
            'g1_actual_collision_shield_queries': sum(row.get('g1_actual_collision_shield_queries', 0) for row in subset),
            'g1_selected_actions_requiring_collision_check': sum(row.get('g1_selected_actions_requiring_collision_check', 0) for row in subset),
            'g1_unattempted_collision_queries': sum(row.get('g1_unattempted_collision_queries', 0) for row in subset),
            'g1_distinct_rejected_actions': sum(row.get('g1_distinct_rejected_actions', 0) for row in subset),
            'g1_blocked_action_records': sum(row.get('g1_rejected_action_attempts',
                row.get('g1_footprint_blocked_attempts', 0)) for row in subset),
            'g1_blocked_feedback_resets_after_changed_observation': sum(
                row.get('g1_blocked_feedback_resets_after_changed_observation', 0) for row in subset),
            'g1_blocked_movement_reasons': {
                reason: sum(row.get('g1_blocked_movement_reasons', {}).get(reason, 0) for row in subset)
                for reason in ('rotation_collision', 'translation_collision', 'grid_occupancy')},
            'mujoco_sensor_rays': sum(row.get('mujoco_sensor_rays', 0) for row in subset),
            'mujoco_sensor_hits': sum(row.get('mujoco_sensor_hits', 0) for row in subset),
            'mujoco_sensor_visible_cells': sum(row.get('mujoco_sensor_visible_cells', 0) for row in subset),
            'mujoco_sensor_free_cells': sum(row.get('mujoco_sensor_free_cells', 0) for row in subset),
            'mujoco_sensor_occupied_cells': sum(row.get('mujoco_sensor_occupied_cells', 0) for row in subset),
            'mujoco_sensor_hit_types': {
                kind: sum(row.get('mujoco_sensor_hit_types', {}).get(kind, 0) for row in subset)
                for kind in ('walls', 'persistent_obstacles', 'pedestrians')},
            'mean_observations': sum(row['observation_count'] for row in subset) / n,
            'total_observations': sum(row['observation_count'] for row in subset),
            'mean_observation_cost': sum(row['observation_cost'] for row in subset) / n,
            'blocked_movement_attempts': sum(row['blocked_movement_attempts'] for row in subset),
            'grid_dynamic_contacts': sum(row['dynamic_contacts'] for row in subset),
            'g1_pose_pedestrian_contact_pairs': sum(row.get('g1_pedestrian_contact_pairs', 0) for row in subset),
            'g1_pose_wall_contact_pairs': sum(row.get('g1_wall_contact_pairs', 0) for row in subset),
            'g1_pose_persistent_obstacle_contact_pairs': sum(row.get('g1_persistent_obstacle_contact_pairs', 0) for row in subset),
            'g1_attempt_pedestrian_contact_pairs': sum(row.get('g1_attempt_pedestrian_contact_pairs', 0) for row in subset),
            'g1_attempt_wall_contact_pairs': sum(row.get('g1_attempt_wall_contact_pairs', 0) for row in subset),
            'g1_attempt_persistent_obstacle_contact_pairs': sum(row.get('g1_attempt_persistent_obstacle_contact_pairs', 0) for row in subset),
            'mean_travel_distance': sum(row['travel_distance'] for row in subset) / n,
            'mean_travel_distance_m': sum(row['travel_distance_m'] for row in subset) / n,
            'mean_elapsed_steps': sum(row['elapsed_steps'] for row in subset) / n,
            'stale_map_error_cell_steps': sum(row['stale_map_errors'] for row in subset),
            'final_stale_map_errors': sum(row['final_stale_map_errors'] for row in subset),
            'false_persistent_occupancy_cell_steps': sum(row['false_persistent_occupancy_updates'] for row in subset),
            'final_false_persistent_occupancy_updates': sum(row['final_false_persistent_occupancy_updates'] for row in subset),
            'missed_persistent_change_cell_steps': sum(row['missed_persistent_changes'] for row in subset),
            'final_missed_persistent_changes': sum(row['final_missed_persistent_changes'] for row in subset),
            'failure_reasons': {reason: sum(row.get('failure_reason') == reason for row in subset)
                                for reason in sorted({row.get('failure_reason') for row in subset
                                                     if row.get('failure_reason')})},
        }

    return {
        'episodes': len(rows),
        'methods': {method: aggregate([row for row in rows if row['method'] == method])
                    for method in METHODS},
        'mechanisms': {
            mechanism: {method: aggregate([row for row in rows
                            if row['mechanism'] == mechanism and row['method'] == method])
                        for method in METHODS}
            for mechanism in ('R', 'BP', 'M')},
    }


PAIRED_METRICS = {
    'goal_completion': lambda row: int(bool(row['success'])),
    'contact_free_completion': lambda row: int(bool(row.get('g1_contact_free_success', False))),
    'observations': lambda row: float(row['observation_count']),
    'observation_cost': lambda row: float(row['observation_cost']),
    'travel_distance_m': lambda row: float(row['travel_distance_m']),
    'elapsed_steps': lambda row: float(row['elapsed_steps']),
    'blocked_actions': lambda row: float(row['g1_footprint_blocked_attempts']),
    'collision_shield_queries': lambda row: float(row.get('g1_actual_collision_shield_queries', 0)),
    'unattempted_collision_queries': lambda row: float(row.get('g1_unattempted_collision_queries', 0)),
    'distinct_rejected_actions': lambda row: float(row.get('g1_distinct_rejected_actions', 0)),
    'no_route_steps': lambda row: float(row['g1_navigation_no_route_steps']),
    'heading_changes': lambda row: float(row['g1_heading_changes']),
    'forward_actions': lambda row: float(row.get('g1_forward_actions', 0)),
    'lateral_actions': lambda row: float(row.get('g1_lateral_actions', 0)),
    'backward_actions': lambda row: float(row.get('g1_backward_actions', 0)),
    'executed_forward_translations': lambda row: float(row.get('g1_executed_forward_translations', 0)),
    'executed_lateral_steps': lambda row: float(row.get('g1_executed_lateral_steps', 0)),
    'executed_backward_steps': lambda row: float(row.get('g1_executed_backward_steps', 0)),
    'in_place_turns': lambda row: float(row.get('g1_in_place_turns', 0)),
    'waits': lambda row: float(row.get('g1_waits', 0)),
    'sensor_rays': lambda row: float(row.get('mujoco_sensor_rays', 0)),
    'sensor_visible_cells': lambda row: float(row.get('mujoco_sensor_visible_cells', 0)),
    'stale_map_errors': lambda row: float(row['stale_map_errors']),
    'false_persistent_occupancy_updates': lambda row: float(row['false_persistent_occupancy_updates']),
    'missed_persistent_changes': lambda row: float(row['missed_persistent_changes']),
}


def validate_matched_design(rows):
    if len(rows) != 288:
        raise ValueError(f'Expected 288 complete episodes, found {len(rows)}')
    worlds = {row['world_identity'] for row in rows}
    if len(worlds) != 36:
        raise ValueError(f'Expected 36 admitted world identities, found {len(worlds)}')
    indexed = {}
    for row in rows:
        key = row['world_identity'], int(row['schedule']), row['method']
        if key in indexed:
            raise ValueError(f'Duplicate matched episode {key}')
        indexed[key] = row
    expected = {(world, schedule, method) for world in worlds
                for schedule in (0, 1) for method in METHODS}
    if indexed.keys() != expected:
        raise ValueError('Comparison matrix is missing a world/schedule/method match')
    return indexed


def paired_world_clustered(rows, *, bootstrap_replicates=10000):
    """Paired method differences with schedules averaged within 36 world clusters."""
    import itertools
    import numpy as np

    indexed = validate_matched_design(rows)
    result = {'clustering_unit': 'saved world_identity',
        'within_cluster': 'average paired schedule-0 and schedule-1 differences',
        'bootstrap_replicates': bootstrap_replicates, 'confidence_level': 0.95,
        'contrasts': {}}
    groups = {'overall': sorted({row['world_identity'] for row in rows})}
    for mechanism in ('R', 'BP', 'M'):
        groups[mechanism] = sorted({row['world_identity'] for row in rows
                                    if row['mechanism'] == mechanism})
    for group, worlds in groups.items():
        contrasts = {}
        for left, right in itertools.combinations(METHODS, 2):
            metric_results = {}
            for metric_index, (metric, value_fn) in enumerate(PAIRED_METRICS.items()):
                cluster_differences = []
                for world in worlds:
                    schedule_differences = [
                        value_fn(indexed[(world, schedule, left)])
                        - value_fn(indexed[(world, schedule, right)])
                        for schedule in (0, 1)]
                    cluster_differences.append(float(np.mean(schedule_differences)))
                values = np.asarray(cluster_differences, dtype=float)
                rng = np.random.default_rng(42042 + len(metric_results) + metric_index*31
                                             + METHODS.index(left)*701 + METHODS.index(right)*1301)
                samples = rng.integers(0, len(values), size=(bootstrap_replicates, len(values)))
                means = values[samples].mean(axis=1)
                metric_results[metric] = {
                    'left_minus_right_mean': float(values.mean()),
                    'cluster_bootstrap_95pct_ci': [float(np.quantile(means, 0.025)),
                                                   float(np.quantile(means, 0.975))],
                    'world_clusters': len(values),
                    'matched_world_schedule_pairs': 2*len(values),
                }
            contrasts[f'{left}_minus_{right}'] = metric_results
        result['contrasts'][group] = contrasts
    return result


def render_proxy_snapshot(path, scene, scenario, frames, method):
    """Matplotlib fallback for headless macOS where MuJoCo GL cannot connect."""
    import os
    os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'phase2-matplotlib-cache'))
    Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True, exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    figure = plt.figure(figsize=(10, 8))
    axes = figure.add_subplot(111, projection='3d')
    spacing = scene.cell_size
    half = spacing * 0.49

    def box(cell, height, color, alpha=1.0):
        x, y = scene.grid_to_world(cell)
        z0, z1 = 0.015, height
        corners = [(x-half,y-half,z0),(x+half,y-half,z0),(x+half,y+half,z0),(x-half,y+half,z0),
                   (x-half,y-half,z1),(x+half,y-half,z1),(x+half,y+half,z1),(x-half,y+half,z1)]
        faces = [[corners[i] for i in face] for face in
                 ((0,1,2,3),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7))]
        axes.add_collection3d(Poly3DCollection(faces, facecolors=color, edgecolors='0.25',
                                               linewidths=0.25, alpha=alpha))
    for cell in scenario.walls:
        box(cell, 2.5, '#555b66', alpha=0.25)
    for y, x in zip(*frames[-1]['geometry'].nonzero()):
        cell = (int(x), int(y))
        if cell not in scenario.walls:
            box(cell, 0.9, '#a65b2b')
    path_cells = [frame['position'] for frame in frames]
    path_xyz = [(*scene.grid_to_world(cell), 0.05) for cell in path_cells]
    axes.plot([p[0] for p in path_xyz], [p[1] for p in path_xyz], [p[2] for p in path_xyz],
              color='#21a179', linewidth=2, label='Executed kinematic path')
    rx, ry = scene.grid_to_world(frames[-1]['position'])
    axes.plot([rx,rx], [ry,ry], [0.1,0.85], color='#1f5aa6', linewidth=5)
    axes.plot([rx,rx], [ry,ry], [0.85,1.35], color='#1f5aa6', linewidth=10)
    axes.scatter([rx], [ry], [1.55], color='#c99570', s=90)
    import numpy as np
    for y, x in np.argwhere(frames[-1]['people']):
        cell = int(x), int(y)
        px, py = scene.grid_to_world(cell)
        axes.plot([px,px], [py,py], [0.2,1.3], color='#d74438', linewidth=5)
        axes.scatter([px], [py], [1.38], color='#d74438', s=45)
    sx, sy = scene.grid_to_world(scenario.start)
    gx, gy = scene.grid_to_world(scenario.goal)
    axes.scatter([sx,gx], [sy,gy], [0.05,0.05], color=['green','purple'], s=35)
    axes.set(xlabel='MuJoCo X (m)', ylabel='MuJoCo Y (m)', zlabel='Z (m)',
             title=f'Phase 2 kinematic navigation — {method}\nHumanoid proxy, not Unitree G1')
    axes.set_zlim(0, 2.6)
    axes.set_box_aspect((scenario.width, scenario.height, scenario.height * 0.42))
    axes.view_init(elev=72, azim=-90)
    axes.legend(loc='upper left')
    figure.tight_layout()
    figure.savefig(path, dpi=130)
    plt.close(figure)


def provenance(worlds, config, mode, preserved, sensor_backend, *, git_commit, git_status):
    return {
        'mode': mode,
        'git_commit': git_commit,
        'git_status_at_start': git_status,
        'python': sys.version,
        'platform': platform.platform(),
        'architecture': platform.machine(),
        'mujoco_version': __import__('mujoco').__version__,
        'sensor_backend': sensor_backend,
        'g1_forward_axis_local': [1.0, 0.0, 0.0],
        'robot_model': 'third_party/unitree_g1/g1.xml; actual Unitree G1 model',
        'robot_model_upstream_commit': (ROOT/'third_party/unitree_g1.UPSTREAM_COMMIT').read_text().strip(),
        'robot_model_files': [
            {'path': str(path.relative_to(ROOT)), 'bytes': path.stat().st_size,
             'sha256': sha(path.read_bytes())}
            for path in sorted((ROOT/'third_party/unitree_g1').rglob('*')) if path.is_file()
        ],
        'g1_mjcf_sha256': sha((ROOT/'third_party/unitree_g1/g1.xml').read_bytes()),
        'motion_model': 'forward-first cardinal kinematic translation; A* does not reject in-place turns with a footprint AABB, and checks only its selected turn through the actual G1 MuJoCo action shield; rejected turns feed back to A*; observed static-obstacle sidesteps, observed-threat lateral escape with fully observed swept clearance, and observation-verified oncoming-pedestrian retreats only; not walking control',
        'movement_policy_comparison': {
            'previous_full_comparison': 'results/phase2_mujoco/g1_3d_perception_footprint_feedback_full_288',
            'difference': 'The previous comparison allowed cardinal lateral/backward translations while preserving heading. This comparison uses forward-first turns with rule-gated static-object sidesteps and observed-threat retreats.',
            'matched': 'Same 36 saved fit identities, two schedules, four observation methods, seed, 0.75 m/cell assumption and observation cap.',
            'interpretation': 'Results compare navigation policies under a movement-policy change; they are not a locomotion-actuation comparison.'},
        'sensor_mapping_policy': 'ray-distance surface rasterization with directional 0.005-cell box-overlap correction; no geom-center use',
        'reproduction_command': ('.venv/bin/python scripts/phase2_mujoco_navigation.py '
            f'{mode} --output <new-empty-result-directory> --max-steps {config["max_steps"]} '
            '--heartbeat-seconds 900 --sensor-backend mujoco3d'),
        'source_hashes': {
            'scripts/phase2_mujoco_navigation.py': sha(Path(__file__).read_bytes()),
            'scripts/view_phase2_g1_navigation.py': sha((ROOT/'scripts/view_phase2_g1_navigation.py').read_bytes()),
            'src/spatial_memory/mujoco_navigation.py': sha((ROOT/'src/spatial_memory/mujoco_navigation.py').read_bytes()),
            'src/spatial_memory/mujoco_perception.py': sha((ROOT/'src/spatial_memory/mujoco_perception.py').read_bytes()),
            'src/spatial_memory/navigation.py': sha((ROOT/'src/spatial_memory/navigation.py').read_bytes()),
            'src/spatial_memory/pedestrian_tracking.py': sha((ROOT/'src/spatial_memory/pedestrian_tracking.py').read_bytes()),
            'src/spatial_memory/evaluation.py': sha((ROOT/'src/spatial_memory/evaluation.py').read_bytes()),
            'src/spatial_memory/simulation.py': sha((ROOT/'src/spatial_memory/simulation.py').read_bytes()),
        },
        'world_count': len(worlds),
        'world_identities': [payload['identity'] for payload in worlds],
        'schedule_indices': [0, 1] if mode == 'full' else [0],
        'methods': list(METHODS) if mode == 'full' else ['periodic'],
        'episode_seed': 42,
        'source_store_roots': list(STORES),
        'preserved_phase15_checkpoint_receipt_files_rehashed': preserved['files_checked'],
        'preservation_manifest_sha256': preserved['manifest_sha256'],
        'observation_budget_includes_initial_call': True,
        'policy_config': config,
    }


def run(mode, output, max_steps, heartbeat_seconds, sensor_backend='mujoco3d'):
    worlds = admitted_worlds()
    preserved = verify_preserved_prefix()
    run_commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    run_git_status = subprocess.run(['git', 'status', '--short', '--branch'], cwd=ROOT,
        capture_output=True, text=True, check=True).stdout.strip()
    config = dict(sensor=dict(radius=3, occlusion=True, noise=0.0),
                  update_interval=4, unknown='optimistic', max_steps=max_steps,
                  observation_cost=1, max_observations=20,
                  common_horizon_metrics=True,
                  mujoco_cell_size_m=0.75, mujoco_timestep_seconds=0.02,
                  mujoco_ray_sensor=dict(range_m=6.0, horizontal_fov_deg=120.0,
                                         ray_count=61, sample_spacing_m=0.075),
                  g1_navigation=dict(footprint_source='pinned G1 collision geometry',
                      local_half_extents_m=None, motion='cardinal kinematic translation with separate in-place turns',
                      observed_occupancy_only=True, rejected_action_history=True,
                      forward_translation_default=True,
                      turn_clearance='deferred_to_selected_action_mujoco_shield; no AABB prefilter; one selected turn checked, rejection returned as planner feedback',
                      sidestep_eligibility='around a measured persistent obstacle, or one lateral escape from a close observed pedestrian threat; complete swept clearance observed free and only the selected action is shield-checked',
                      retreat_eligibility='recent single-cluster pedestrian detections in two observations indicate imminent approach; entire backward sweep observed free, otherwise wait',
                      pedestrian_prediction='motion inferred only from observed first-hit cells; no simulator schedule or future positions'),
                  sensor_backend=sensor_backend)
    if mode == 'smoke':
        selected = worlds[0]
        episodes = [(selected, 0, 'periodic')]
    else:
        episodes = [(payload, schedule, method) for payload in worlds
                    for schedule in (0, 1) for method in METHODS]
    if output.exists():
        raise FileExistsError(f'Output already exists; refusing to overwrite: {output}')
    output.mkdir(parents=True)
    lock = output / 'run.lock'
    with lock.open('x') as handle:
        handle.write(json.dumps({'pid': os.getpid(), 'mode': mode, 'commit': run_commit,
                                 'git_status_at_start': run_git_status}))
        handle.flush()
        os.fsync(handle.fileno())
    rows = []
    action_events = []
    first_scene = None
    started = time.monotonic()
    with Progress(len(episodes), heartbeat_seconds) as progress:
        for payload, schedule, method in episodes:
            scenario = scenario_from_bprime(payload, schedule)
            scene = MujocoNavigationScene(scenario,
                cell_size=config['mujoco_cell_size_m'],
                timestep=config['mujoco_timestep_seconds'])
            perception = (MujocoRayPerception(scene, **config['mujoco_ray_sensor'])
                          if sensor_backend == 'mujoco3d' else None)
            pedestrian_tracker = ObservedPedestrianTracker(max_age_steps=8)
            motion_state = {'static_obstacle_cells': set(), 'static_obstacle_step': -1,
                            'planner_step': 0, 'action_shield_queries': 0,
                            'last_reason': 'no_feasible_forward_route'}
            config['g1_navigation']['local_half_extents_m'] = list(scene.footprint_half_extents_local)
            def g1_plan(grid, position, goal, unknown, yaw, blocked):
                motion_state['planner_step'] += 1
                pedestrian_context = pedestrian_tracker.context()
                recent_static = (motion_state['static_obstacle_cells']
                    if 0 <= motion_state['planner_step']-motion_state['static_obstacle_step'] <= 8
                    else set())
                route = plan_g1_default_policy(grid, position, goal, heading=heading_index(yaw),
                    unknown=unknown, local_extents=scene.footprint_half_extents_local,
                    cell_size=scene.cell_size, blocked_actions=blocked,
                    static_obstacle_cells=recent_static,
                    pedestrian_context=pedestrian_context,
                    step=motion_state['planner_step'])
                if route:
                    kind, value = route[0]
                    if kind == 'turn':
                        motion_state['last_reason'] = 'route_direction_change'
                    elif kind == 'sidestep':
                        motion_state['last_reason'] = 'observed_static_obstacle_blocks_forward_path'
                    elif kind == 'retreat':
                        motion_state['last_reason'] = assess_observed_pedestrian_risk(
                            position, heading_index(yaw), pedestrian_context,
                            step=motion_state['planner_step']) or 'observed_oncoming_pedestrian_imminent'
                    elif kind == 'wait':
                        motion_state['last_reason'] = str(value)
                    else:
                        motion_state['last_reason'] = 'forward_route_segment'
                else:
                    motion_state['last_reason'] = 'no_feasible_forward_route'
                return route
            def record_observation(observation, step, position):
                if perception is None:
                    return
                stats = perception.last_stats
                pedestrian_tracker.observe(step, stats.get('visible_pedestrian_cells', ()))
                motion_state['static_obstacle_cells'] = {
                    tuple(cell) for cell in stats.get('visible_persistent_obstacle_cells', ())}
                motion_state['static_obstacle_step'] = int(step)
            def action_reason(action, position, yaw):
                return motion_state['last_reason']
            def check_action(world, position, action, yaw):
                motion_state['action_shield_queries'] += 1
                kind, value = action
                if kind in {'move', 'sidestep', 'retreat'}:
                    return scene.check_move(world, position, tuple(value), yaw, target_yaw=yaw)
                return scene.check_turn(world, position, yaw, HEADINGS[int(value)])
            metrics, frames = run_episode(scenario, config, method, seed=42,
                _frame_callback=scene.update,
                _observation_provider=perception.observe if perception is not None else None,
                _g1_planner=g1_plan if sensor_backend == 'mujoco3d' else None,
                _action_checker=check_action if sensor_backend == 'mujoco3d' else None,
                _initial_observation_callback=record_observation if sensor_backend == 'mujoco3d' else None,
                _observation_callback=record_observation if sensor_backend == 'mujoco3d' else None,
                _g1_action_reason=action_reason if sensor_backend == 'mujoco3d' else None)
            selected_checked_actions = sum(
                frame.get('navigation_action') is not None
                and frame['navigation_action'][0] != 'wait' for frame in frames)
            metrics['g1_actual_collision_shield_queries'] = motion_state['action_shield_queries']
            metrics['g1_selected_actions_requiring_collision_check'] = selected_checked_actions
            metrics['g1_unattempted_collision_queries'] = 0
            metrics['g1_shield_query_count_valid'] = (
                motion_state['action_shield_queries'] == selected_checked_actions)
            metrics['travel_distance_m'] = metrics['travel_distance'] * scene.cell_size
            row = dict(mechanism=payload['mechanism'], world_identity=payload['identity'],
                       schedule=schedule, **metrics)
            rows.append(row)
            for frame in frames:
                action = frame.get('navigation_action')
                if action is not None and action[0] != 'move':
                    action_events.append(dict(
                        world_identity=payload['identity'], schedule_index=schedule,
                        method=method, step=frame['step'], position=list(frame['position']),
                        heading_yaw=frame.get('heading_yaw'), action_kind=action[0],
                        action_value=action[1], reason=frame.get('navigation_action_reason'),
                        accepted=not frame.get('blocked', False),
                        collision_checked=action[0] != 'wait'))
            if first_scene is None:
                first_scene = (scene, scenario, frames, payload, schedule, method)
            progress.done()
    paired_analysis = None
    if mode == 'full':
        validate_matched_design(rows)
        paired_analysis = paired_world_clustered(rows)
        (output/'paired_world_clustered_analysis.json').write_text(
            json.dumps(paired_analysis, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    (output/'action_events.json').write_text(
        json.dumps(action_events, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    if mode == 'smoke':
        scene, scenario, frames, payload, schedule, method = first_scene
        # Keep the replay MJCF portable relative to the repository checkout.
        portable_xml = scene.xml.replace(str((ROOT/'third_party/unitree_g1/assets').resolve()),
                                         '../../../third_party/unitree_g1/assets')
        (output/'scene.xml').write_text(portable_xml, encoding='utf-8')
        (output/'scenario.json').write_text(json.dumps(
            {'width': scenario.width, 'height': scenario.height, 'cell_size_m': scene.cell_size},
            sort_keys=True, indent=2)+'\n', encoding='utf-8')
        trajectory = [dict(step=frame['step'], position=frame['position'],
                           planned=frame['planned'], moved=frame['moved'],
                           blocked=frame['blocked'], observation_count=frame['observation_count'],
                           heading_yaw=frame.get('heading_yaw', 0.0),
                           heading_changed=frame.get('heading_changed', False),
                           blocked_reason=frame.get('blocked_reason'),
                           navigation_action=frame.get('navigation_action'),
                           navigation_action_reason=frame.get('navigation_action_reason'),
                           blocked_action_count=frame.get('blocked_action_count', 0),
                           memory_grid=frame['memory'].tolist(),
                           observation_stats=frame.get('observation_stats', {}),
                           people=frame.get('g1_pedestrians', []),
                           active_objects=frame.get('g1_active_objects', []),
                           g1_foot_floor_contact_pairs=frame.get('g1_foot_floor_contact_pairs', 0),
                           g1_unwanted_floor_contact_pairs=frame.get('g1_unwanted_floor_contact_pairs', 0),
                           g1_pedestrian_contact_pairs=frame.get('g1_pedestrian_contact_pairs', 0),
                           g1_wall_contact_pairs=frame.get('g1_wall_contact_pairs', 0),
                           g1_persistent_obstacle_contact_pairs=frame.get('g1_persistent_obstacle_contact_pairs', 0),
                           g1_self_contact_pairs=frame.get('g1_self_contact_pairs', 0))
                      for frame in frames]
        (output/'trajectory.json').write_text(json.dumps(trajectory, indent=2)+'\n', encoding='utf-8')
        try:
            import numpy as np
            from PIL import Image
            image = scene.render()
            Image.fromarray(np.asarray(image)).save(output/'smoke_overview.png')
        except Exception as error:
            # The active Viewer can load scene.xml and trajectory.json directly.
            (output/'render_unavailable.json').write_text(json.dumps(
                {'mujoco_renderer_unavailable': type(error).__name__, 'message': str(error),
                 'fallback': 'Use scripts/view_phase2_g1_navigation.py in a normal macOS Terminal'}, indent=2)+'\n')
    persist_csv(output/'episodes.csv', rows)
    smoke_passed = (mode == 'smoke' and bool(rows[0]['success'])
        and int(rows[0].get('g1_unwanted_contact_pairs', 0)) == 0
        and int(rows[0]['observation_count']) <= int(rows[0]['max_observations'])
        and bool(rows[0].get('g1_shield_query_count_valid', True))
        and int(rows[0].get('g1_unattempted_collision_queries', 0)) == 0
        and (sensor_backend != 'mujoco3d' or int(rows[0].get('mujoco_sensor_rays', 0)) > 0))
    result = {
        'status': ((('PASS_G1_MUJOCO_PERCEPTION_SMOKE' if sensor_backend == 'mujoco3d'
                     else 'PASS_G1_LEGACY_2D_SMOKE') if smoke_passed else 'FAIL_G1_SMOKE_GATE')
                   if mode == 'smoke' else 'COMPLETE_G1_PHASE2_PILOT'),
        'mode': mode,
        'movement_policy': 'forward-first with explicit obstacle-only sidesteps, observed-imminent-pedestrian-only retreats, otherwise wait when dynamic safety is uncertain',
        'comparison_to_previous_policy': 'Movement conditions changed from the prior full 288; same admitted worlds, schedules, methods, seed, sensor/observation policy and 0.75 m/cell assumption.',
        'episodes': len(rows),
        'elapsed_seconds': time.monotonic()-started,
        'summary': summarize(rows),
        'paired_world_clustered_analysis': ('paired_world_clustered_analysis.json'
                                            if mode == 'full' else None),
        'limits': [
            'Robot is the pinned Unitree G1 model, initialized from its stand keyframe and translated kinematically.',
            'Root waypoint placement is kinematic; no gait, actuator control, balance, or walking is simulated.',
            'Grid scale is the documented assumption 0.75 m per cell; no scale fitting was performed.',
            'Only eight small ankle-roll sphere contacts against the floor are treated as intended foot-floor contacts.',
            'G1 uses cardinal kinematic translation with explicit in-place turns; only the selected action is checked by MuJoCo.',
            'Navigation uses public G1 collision bounds and observed occupied cells; the shield is not queried for unattempted routes.',
            'Rejected actions remain separate from occupancy memory and are reconsidered only after relevant local observed memory changes.',
            'The 3D sensor uses a limited-FOV horizontal ray plane. Policy inputs are ternary occupancy plus current first-hit cells coarsely classified as persistent objects or pedestrians; no future pedestrian positions or hidden occupancy are passed.',
            'Pedestrian motion is inferred only by associating ray-observed pedestrian cell clusters across two observations. Uncertain nearby motion waits; backward retreat additionally requires the full retreat sweep to be observed free.',
            'Side-steps require a recent direct ray classification of a persistent object in the forward cell plus observed-free lateral and next-forward sweeps. Turns remain the ordinary way to change direction.',
            'All other G1 floor, wall, obstacle, pedestrian, and self contacts are unwanted; collisions block maneuvers with a recorded reason.',
            'Pedestrians are prescribed proxies and do not react to the robot.',
            'MuJoCo ground truth supplies ray geometry, selected-action collision checks and evaluator-only metrics; planner route enumeration receives no simulator occupancy or unattempted collision results.',
            'Ray-box face positions within the measured collision-box/raster-boundary overlap are assigned to the cell beyond the boundary in ray direction.',
        ],
    }
    (output/'summary.json').write_text(json.dumps(result, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    run_provenance = provenance(worlds, config, mode, preserved, sensor_backend,
        git_commit=run_commit, git_status=run_git_status)
    (output/'provenance.json').write_text(json.dumps(
        run_provenance, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    if mode == 'smoke':
        row = rows[0]
        validation = dict(status=result['status'], mode=mode, sensor_backend=sensor_backend,
            world_identity=row['world_identity'], schedule_index=row['schedule'], method=row['method'],
            measured_metrics={key: row.get(key) for key in (
                'success', 'elapsed_steps', 'travel_distance', 'travel_distance_m',
                'observation_count', 'observation_requests_denied', 'g1_heading_changes',
                'g1_heading_change_records', 'g1_footprint_blocked_attempts',
                'g1_navigation_no_route_steps', 'g1_rejected_actions',
                'g1_rejected_action_attempts', 'g1_distinct_rejected_actions',
                'g1_blocked_feedback_resets_after_changed_observation',
                'g1_blocked_movement_reasons', 'g1_unwanted_contact_pairs',
                'g1_forward_actions', 'g1_lateral_actions', 'g1_backward_actions',
                'g1_in_place_turns', 'g1_waits', 'g1_nonforward_action_reasons',
                'g1_actual_collision_shield_queries', 'g1_selected_actions_requiring_collision_check',
                'g1_unattempted_collision_queries', 'g1_shield_query_count_valid',
                'g1_foot_floor_contact_pairs', 'mujoco_sensor_rays', 'mujoco_sensor_hits',
                'mujoco_sensor_visible_cells', 'mujoco_sensor_free_cells',
                'mujoco_sensor_occupied_cells', 'mujoco_sensor_hit_types',
                'stale_map_errors', 'final_stale_map_errors', 'missed_persistent_changes',
                'final_missed_persistent_changes')},
            sensor_configuration=config['mujoco_ray_sensor'] if sensor_backend == 'mujoco3d' else None,
            grid_scale_m_per_cell=config['mujoco_cell_size_m'],
            grid_scale_calibrated=False, phase15_environments_generated=0,
            preservation_files_rehashed=preserved['files_checked'],
            model_sha256=sha((ROOT/'third_party/unitree_g1/g1.xml').read_bytes()),
            source_hashes=run_provenance['source_hashes'])
        (output/'validation_report.json').write_text(
            json.dumps(validation, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    # Hash the just-written result set in an index after all evidence is durable.
    inventory = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.name != 'artifact_manifest.json':
            raw = path.read_bytes()
            inventory.append({'path': path.name, 'bytes': len(raw), 'sha256': sha(raw)})
    (output/'artifact_manifest.json').write_text(json.dumps(inventory, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    verify_preserved_prefix()
    print(json.dumps({'status': result['status'], 'output': str(output),
                      'episodes': len(rows), 'elapsed_seconds': result['elapsed_seconds'],
                      'summary': result['summary']}, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('smoke', 'full'))
    parser.add_argument('--output', type=Path)
    parser.add_argument('--max-steps', type=int, default=80)
    parser.add_argument('--heartbeat-seconds', type=int, default=900)
    parser.add_argument('--sensor-backend', choices=('mujoco3d', 'legacy2d'), default='mujoco3d')
    args = parser.parse_args()
    if args.max_steps < 1 or args.heartbeat_seconds < 1:
        parser.error('max-steps and heartbeat-seconds must be positive')
    output = args.output or ROOT/'results'/'phase2_mujoco'/f'g1_{args.sensor_backend}_{args.mode}'
    run(args.mode, output.resolve(), args.max_steps, args.heartbeat_seconds, args.sensor_backend)


if __name__ == '__main__':
    main()
